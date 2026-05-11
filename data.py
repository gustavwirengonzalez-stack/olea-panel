"""
data.py — Downloads 2 years of historical price data for European stocks.

Pulls adjusted closing prices via yfinance and caches them locally so
subsequent runs don't re-hit the network. All other modules import
load_prices() from here as their data source.
"""

import yfinance as yf
import pandas as pd
from pathlib import Path

# Ten major European blue-chips across five exchanges.
# The suffix encodes the exchange: .AS=Amsterdam, .PA=Paris,
# .MC=Madrid, .DE=Frankfurt, .MI=Milan
TICKERS = [
    "ASML.AS",  # ASML Holding — semiconductor equipment (Amsterdam)
    "MC.PA",    # LVMH — luxury goods (Paris)
    "SAN.MC",   # Banco Santander — banking (Madrid)
    "SHELL.AS", # Shell — energy (Amsterdam)
    "SAP.DE",   # SAP — enterprise software (Frankfurt)
    "OR.PA",    # L'Oréal — cosmetics (Paris)
    "BNP.PA",   # BNP Paribas — banking (Paris)
    "AIR.PA",   # Airbus — aerospace (Paris)
    "DHL.DE",   # DHL Group — logistics (Frankfurt)
    "ENEL.MI",  # Enel — utilities (Milan)
]

# Local CSV cache — avoids repeated downloads during development
DATA_FILE = Path("prices.csv")


def download_prices(period: str = "2y") -> pd.DataFrame:
    """
    Fetch adjusted closing prices from Yahoo Finance and write them to CSV.

    auto_adjust=True applies corporate-action adjustments (splits, dividends)
    so that returns computed from these prices reflect actual investor experience.
    Rows where *all* tickers are NaN (e.g. holidays when every exchange is closed)
    are dropped; partial NaN rows (one exchange closed) are kept so we don't lose
    data for the other tickers.
    """
    print(f"Downloading {period} of data for {len(TICKERS)} tickers...")
    raw = yf.download(TICKERS, period=period, auto_adjust=True, progress=True)

    # yfinance returns a MultiIndex DataFrame; we only need the "Close" level
    prices = raw["Close"].dropna(how="all")

    prices.to_csv(DATA_FILE)
    print(f"Saved {len(prices)} rows to {DATA_FILE}")
    return prices


def load_prices() -> pd.DataFrame:
    """
    Return prices from the local CSV cache if it exists, otherwise download.

    Using parse_dates=True ensures the index is a DatetimeIndex rather than
    plain strings, which is required for any time-series operations downstream.
    """
    if DATA_FILE.exists():
        print(f"Loading cached prices from {DATA_FILE}")
        prices = pd.read_csv(DATA_FILE, index_col=0, parse_dates=True)
        return prices
    return download_prices()


if __name__ == "__main__":
    df = download_prices()
    print(df.tail())
