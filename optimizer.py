"""
optimizer.py — Mean-variance portfolio optimization via scipy.

The goal is to find the combination of asset weights that maximizes the
portfolio Sharpe ratio subject to:
  1. Weights sum to exactly 1.0  (fully invested)
  2. No short selling            (each weight is between 0 and 1)

We also provide efficient_frontier(), which sweeps a range of target returns
and finds the minimum-variance portfolio at each level, tracing the frontier
curve used in the visualization.

Two sources of expected returns are supported:

  Historical (use_ff=False, default)
      Mean daily returns from the price history, annualized by ×252.
      Simple and data-driven but backward-looking; can be noisy for short
      lookback windows.

  Fama-French 3-factor (use_ff=True)
      Expected returns derived from OLS factor loadings.  Each stock's
      expected return is:
          E[R_i] = RF + β_mkt·E[Mkt-RF] + β_smb·E[SMB] + β_hml·E[HML]
      This is more theoretically grounded and less sensitive to sample-period
      return noise, but relies on factor model assumptions being valid.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from dataclasses import dataclass

from metrics import (
    daily_returns,
    TRADING_DAYS,
    RISK_FREE_RATE,
)


@dataclass
class Portfolio:
    """Container for the results of a single optimized portfolio."""
    weights: np.ndarray       # array of floats, one per ticker
    tickers: list[str]        # ticker labels matching the weights array
    expected_return: float    # annualized expected return (decimal)
    volatility: float         # annualized volatility (decimal)
    sharpe: float             # annualized Sharpe ratio

    def summary(self) -> pd.Series:
        """Return a labeled Series combining weights and portfolio-level stats."""
        s = pd.Series(self.weights, index=self.tickers).rename("Weight")
        s["Expected Return"] = self.expected_return
        s["Volatility"] = self.volatility
        s["Sharpe Ratio"] = self.sharpe
        return s.round(4)


def _portfolio_stats(
    weights: np.ndarray,
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free: float = RISK_FREE_RATE,
) -> tuple[float, float, float]:
    """
    Compute annualized return, volatility, and Sharpe for a given weight vector.

    Portfolio return  = w · μ  (dot product of weights and mean daily returns)
                        scaled up by 252 trading days

    Portfolio variance = w^T · Σ · w  (quadratic form with covariance matrix)
    Portfolio volatility = sqrt(variance) scaled by sqrt(252)

    Sharpe = (return - risk_free) / volatility
    """
    # Weighted average of mean daily returns, annualized
    ret = float(weights @ mean_returns) * TRADING_DAYS

    # Portfolio variance via the covariance quadratic form, then annualized vol
    vol = float(np.sqrt(weights @ cov_matrix @ weights)) * np.sqrt(TRADING_DAYS)

    sharpe = (ret - risk_free) / vol
    return ret, vol, sharpe


def maximize_sharpe(
    prices: pd.DataFrame,
    risk_free: float = RISK_FREE_RATE,
    use_ff: bool = False,
    _ff_expected_returns: pd.Series | None = None,
) -> Portfolio:
    """
    Find the portfolio weights that maximize the Sharpe ratio (tangency portfolio).

    Parameters
    ----------
    prices : pd.DataFrame
        Historical adjusted close prices; columns are ticker symbols.
    risk_free : float
        Annualized risk-free rate (default 3%).
    use_ff : bool
        If True, use Fama-French 3-factor expected returns instead of
        historical mean returns.  The covariance matrix is always estimated
        from historical data regardless of this flag.
    _ff_expected_returns : pd.Series or None
        Pre-computed FF3 expected returns (annualized).  If None and use_ff
        is True, they will be fetched automatically.  Pass this to avoid
        re-downloading FF data when calling both methods in sequence.

    Notes
    -----
    Uses scipy's SLSQP (Sequential Least Squares Programming) method, which
    handles both equality constraints (weights sum to 1) and box bounds
    (each weight between 0 and 1) efficiently.

    The objective function is negative Sharpe because scipy minimizes, so
    minimizing -Sharpe is equivalent to maximizing Sharpe.

    Starting point (x0) is the equal-weight portfolio — a neutral, feasible
    initial guess that avoids biasing the optimizer toward any single stock.

    ftol=1e-12 sets a tight convergence tolerance to avoid stopping early
    at a local near-optimum.
    """
    rets = daily_returns(prices)
    cov_matrix = rets.cov().values      # shape: (n_assets, n_assets)
    n = len(prices.columns)

    if use_ff:
        # Use Fama-French factor model to set expected returns.
        # The covariance structure still comes from the historical data because
        # the FF model describes expected returns, not the variance-covariance
        # matrix of residuals (which would require a full factor-model covariance).
        if _ff_expected_returns is None:
            from factors import run_ff3_regression
            _, _ff_expected_returns = run_ff3_regression(prices)
        # FF returns are already annualized; convert back to daily for _portfolio_stats
        mean_returns = (_ff_expected_returns.reindex(prices.columns).values
                        / TRADING_DAYS)
    else:
        mean_returns = rets.mean().values   # shape: (n_assets,)

    # Objective: minimize negative Sharpe (= maximize Sharpe)
    def neg_sharpe(w):
        _, _, sh = _portfolio_stats(w, mean_returns, cov_matrix, risk_free)
        return -sh

    # Constraint: weights must sum to exactly 1 (fully invested, no cash)
    constraints = {"type": "eq", "fun": lambda w: w.sum() - 1.0}

    # Bounds: no short selling — each weight is in [0, 1]
    bounds = [(0.0, 1.0)] * n

    # Start from the equal-weight portfolio
    x0 = np.full(n, 1.0 / n)

    result = minimize(
        neg_sharpe,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )

    if not result.success:
        raise RuntimeError(f"Optimization failed: {result.message}")

    weights = result.x
    ret, vol, sh = _portfolio_stats(weights, mean_returns, cov_matrix, risk_free)
    return Portfolio(
        weights=weights,
        tickers=list(prices.columns),
        expected_return=ret,
        volatility=vol,
        sharpe=sh,
    )


def compare_methods(prices: pd.DataFrame, risk_free: float = RISK_FREE_RATE) -> pd.DataFrame:
    """
    Run optimization under both return estimation methods and print a side-by-side
    comparison table of weights, expected return, volatility, and Sharpe ratio.

    Returns a DataFrame with one row per ticker plus three summary rows, and
    two column groups: "Historical" and "Fama-French".

    Downloading the FF3 data only once and sharing it between both calls avoids
    a second network request.
    """
    from factors import run_ff3_regression, load_ff3_factors

    print("  Loading Fama-French factor data...")
    ff_factors = load_ff3_factors()
    _, ff_rets = run_ff3_regression(prices, ff_factors)

    print("  Optimizing with historical mean returns...")
    opt_hist = maximize_sharpe(prices, risk_free=risk_free, use_ff=False)

    print("  Optimizing with Fama-French expected returns...")
    opt_ff = maximize_sharpe(prices, risk_free=risk_free, use_ff=True,
                             _ff_expected_returns=ff_rets)

    tickers = list(prices.columns)

    # Build comparison DataFrame
    comparison = pd.DataFrame(index=tickers)
    comparison["Historical Weight"]    = (opt_hist.weights * 100).round(1)
    comparison["FF3 Weight"]           = (opt_ff.weights   * 100).round(1)

    # Summary rows appended below the per-ticker weights
    summary_rows = pd.DataFrame(
        {
            "Historical Weight": [
                f"{opt_hist.expected_return * 100:.2f}%",
                f"{opt_hist.volatility      * 100:.2f}%",
                f"{opt_hist.sharpe:.4f}",
            ],
            "FF3 Weight": [
                f"{opt_ff.expected_return * 100:.2f}%",
                f"{opt_ff.volatility      * 100:.2f}%",
                f"{opt_ff.sharpe:.4f}",
            ],
        },
        index=["Expected Return", "Volatility", "Sharpe Ratio"],
    )

    full_table = pd.concat([comparison.astype(str), summary_rows])

    # Pretty-print with column headers renamed for clarity
    display = full_table.rename(columns={
        "Historical Weight": "Historical (%)",
        "FF3 Weight":        "FF3 (%)",
    })

    print("\n" + "─" * 48)
    print(f"{'Ticker':<14}  {'Historical (%)':>15}  {'FF3 (%)':>10}")
    print("─" * 48)
    for idx, row in full_table.iterrows():
        hist_val = row["Historical Weight"]
        ff_val   = row["FF3 Weight"]
        print(f"  {str(idx):<12}  {str(hist_val):>15}  {str(ff_val):>10}")
    print("─" * 48)

    return full_table


def efficient_frontier(
    prices: pd.DataFrame,
    n_portfolios: int = 500,
    risk_free: float = RISK_FREE_RATE,
) -> pd.DataFrame:
    """
    Trace the efficient frontier by solving a minimum-variance problem at
    each of n_portfolios evenly spaced target return levels.

    For each target return, we minimize portfolio volatility subject to:
      - weights sum to 1
      - portfolio return equals the target
      - no short selling

    The result is a DataFrame of (Return, Volatility, Sharpe) triples that
    can be plotted as the frontier curve. Points where the solver fails to
    converge (e.g., infeasible target returns near the extremes) are silently
    dropped, which is why we check res.success before appending.
    """
    rets = daily_returns(prices)
    mean_returns = rets.mean().values
    cov_matrix = rets.cov().values
    n = len(prices.columns)

    # The lowest and highest achievable annualized returns are bounded by
    # the worst and best individual asset mean returns (since we're long-only)
    min_ret = mean_returns.min() * TRADING_DAYS
    max_ret = mean_returns.max() * TRADING_DAYS
    target_returns = np.linspace(min_ret, max_ret, n_portfolios)

    records = []
    for target in target_returns:
        constraints = [
            # Fully invested
            {"type": "eq", "fun": lambda w: w.sum() - 1.0},
            # Portfolio return must equal this specific target
            # The default argument t=target captures the loop variable correctly
            {"type": "eq", "fun": lambda w, t=target: float(w @ mean_returns) * TRADING_DAYS - t},
        ]
        bounds = [(0.0, 1.0)] * n
        x0 = np.full(n, 1.0 / n)

        # Objective: minimize annualized volatility at the given return level
        res = minimize(
            lambda w: float(np.sqrt(w @ cov_matrix @ w)) * np.sqrt(TRADING_DAYS),
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-12, "maxiter": 1000},
        )

        if res.success:
            vol = res.fun
            sh = (target - risk_free) / vol if vol > 0 else np.nan
            records.append({"Return": target, "Volatility": vol, "Sharpe": sh})

    return pd.DataFrame(records)


if __name__ == "__main__":
    from data import load_prices

    prices = load_prices()
    opt = maximize_sharpe(prices)
    print("\n=== Optimal Portfolio ===")
    print(opt.summary().to_string())
