"""
metrics.py — Risk and return statistics for a universe of stocks.

All annualization uses 252 trading days, which is the standard convention
for equity markets. The risk-free rate is set to 3%, approximating the
ECB deposit rate over the lookback period.
"""

import pandas as pd
import numpy as np

# Annualization constant: equity markets have ~252 trading days per year
TRADING_DAYS = 252

# Risk-free rate used in Sharpe ratio calculations (annualized, decimal form)
RISK_FREE_RATE = 0.03


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute simple (arithmetic) daily percentage returns.

    pct_change() produces NaN for the very first row because there is no
    prior price to compare against. dropna() removes that row so downstream
    calculations don't need to handle it.

    Returns a DataFrame with the same columns as prices and one fewer row.
    """
    return prices.pct_change().dropna()


def annualized_return(returns: pd.DataFrame) -> pd.Series:
    """
    Compute the compound annualized growth rate (CAGR) per ticker.

    We use the geometric formula: multiply all (1 + daily_return) factors
    together, then raise to the power of (252 / number_of_observations).
    This correctly accounts for compounding and is preferred over simply
    multiplying the arithmetic mean by 252, which overstates returns when
    volatility is high.
    """
    return (1 + returns).prod() ** (TRADING_DAYS / len(returns)) - 1


def annualized_volatility(returns: pd.DataFrame) -> pd.Series:
    """
    Compute annualized standard deviation of daily returns per ticker.

    Daily volatility is scaled to annual by multiplying by sqrt(252).
    This follows from the assumption that daily returns are independent
    and identically distributed — a simplification, but standard practice.
    """
    return returns.std() * np.sqrt(TRADING_DAYS)


def sharpe_ratio(returns: pd.DataFrame, risk_free: float = RISK_FREE_RATE) -> pd.Series:
    """
    Compute the annualized Sharpe ratio per ticker.

    Sharpe = (annualized_return - risk_free_rate) / annualized_volatility

    The ratio measures how much excess return (above the risk-free rate) an
    asset delivers per unit of risk taken. Higher is better; a value above 1.0
    is generally considered good for a long-only equity position.
    """
    ann_ret = annualized_return(returns)
    ann_vol = annualized_volatility(returns)
    return (ann_ret - risk_free) / ann_vol


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the Pearson correlation matrix of daily returns.

    Values range from -1 (perfect inverse movement) to +1 (perfect co-movement).
    A value near 0 means the two assets move independently, which is what
    portfolio diversification relies on.
    """
    return returns.corr()


def summary(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Produce a single summary table of return, volatility, and Sharpe per ticker.

    Convenience wrapper that computes all three metrics in one call.
    Results are rounded to 4 decimal places for readability.
    """
    rets = daily_returns(prices)
    df = pd.DataFrame(
        {
            "Annualized Return": annualized_return(rets),
            "Annualized Volatility": annualized_volatility(rets),
            "Sharpe Ratio": sharpe_ratio(rets),
        }
    )
    df.index.name = "Ticker"
    return df.round(4)


if __name__ == "__main__":
    from data import load_prices

    prices = load_prices()
    print("\n=== Per-Ticker Summary ===")
    print(summary(prices).to_string())
    print("\n=== Correlation Matrix ===")
    rets = daily_returns(prices)
    print(correlation_matrix(rets).round(3).to_string())
