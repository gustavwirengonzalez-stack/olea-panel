"""
factors.py — Fama-French 3-Factor model for European stocks.

The Fama-French 3-factor model extends the CAPM by adding two additional risk
factors beyond the market:

  R_i - RF = alpha_i
            + beta_mkt_i  * (Mkt-RF)   ← market excess return (systematic risk)
            + beta_smb_i  * SMB        ← Small Minus Big (size premium)
            + beta_hml_i  * HML        ← High Minus Low (value premium)
            + epsilon_i

Interpretation of each coefficient:
  alpha    — abnormal return not explained by the three factors; if consistently
             positive, the stock earns more than the model predicts (rare in
             efficient markets)
  beta_mkt — market sensitivity (same as CAPM beta); >1 means more volatile
             than the market, <1 means more defensive
  beta_smb — loading on the size factor; positive = tilts toward small-cap
             behaviour (higher expected return but also higher risk);
             negative = large-cap tilt
  beta_hml — loading on the value factor; positive = value stock (high
             book-to-market ratio, often cheap/cyclical); negative = growth
             stock (low book-to-market, e.g. tech/quality)

Expected return under the model:
  E[R_i] = RF + beta_mkt * E[Mkt-RF] + beta_smb * E[SMB] + beta_hml * E[HML]

where the expected factor premiums E[·] are estimated from historical averages.
"""

import io
import zipfile
import urllib3
import requests
import numpy as np
import pandas as pd

from metrics import daily_returns, TRADING_DAYS, RISK_FREE_RATE

# Fama-French Europe 3-Factor daily data (Ken French's data library)
FF3_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/"
    "ftp/Europe_3_Factors_daily_CSV.zip"
)

# Local cache to avoid re-downloading on every run
FF3_CACHE = "ff3_europe_daily.csv"


# ── Download and parse ────────────────────────────────────────────────────────

def _download_ff3_raw() -> str:
    """Download the FF3 zip and return the CSV contents as a string.

    Uses requests with SSL verification disabled to work around Mac Python 3.13
    certificate issues. Falls back to pandas_datareader if the download fails.
    """
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("Downloading Fama-French 3-factor data from Ken French's library...")
    try:
        resp = requests.get(FF3_URL, verify=False, timeout=30)
        resp.raise_for_status()

        # The zip contains a single CSV file; extract it regardless of its name
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                return f.read().decode("latin-1")

    except Exception as exc:
        print(f"  Download failed ({exc}); falling back to pandas_datareader...")
        return _fetch_ff3_via_datareader()


def _fetch_ff3_via_datareader() -> str:
    """Fetch FF3 Europe daily factors via pandas_datareader and return CSV text.

    Used as a fallback when the direct Ken French zip download fails.
    pandas_datareader wraps the same data library with its own HTTP session,
    which may succeed when a bare urllib/requests call cannot (e.g. different
    proxy or certificate handling).
    """
    from pandas_datareader.famafrench import get_available_datasets
    import pandas_datareader.data as web

    dataset = "Europe_3_Factors_Daily"
    available = get_available_datasets()
    if dataset not in available:
        raise RuntimeError(
            f"pandas_datareader does not list '{dataset}'. "
            f"Available datasets: {[d for d in available if 'Europe' in d]}"
        )

    print(f"  Fetching '{dataset}' via pandas_datareader...")
    # get() returns a dict; key 0 is the daily DataFrame (in percent)
    data = web.DataReader(dataset, "famafrench")
    df = data[0]  # daily table

    # Normalise column names to match our expected format
    df = df.rename(columns={
        "Mkt-RF": "Mkt-RF",
        "SMB":    "SMB",
        "HML":    "HML",
        "RF":     "RF",
    })
    # Convert percent → CSV text that _parse_ff3_csv can ingest
    df_pct = df.copy()
    df_pct.index = df_pct.index.to_timestamp()          # PeriodIndex → DatetimeIndex
    df_pct.index = df_pct.index.strftime("%Y%m%d")      # → YYYYMMDD strings

    lines = []
    for date_str, row in df_pct.iterrows():
        try:
            lines.append(
                f"{date_str},{row['Mkt-RF']:.4f},{row['SMB']:.4f},"
                f"{row['HML']:.4f},{row['RF']:.4f}"
            )
        except KeyError:
            continue
    return "\n".join(lines)


def _parse_ff3_csv(content: str) -> pd.DataFrame:
    """
    Parse the Ken French CSV format into a clean DataFrame.

    The file starts with several free-text description lines, then the
    column header (optional), then daily data rows in one of two layouts:

      Comma-delimited:    19900703,   -0.36,   -0.17,   -0.35,   0.03
      Whitespace-delimited: 19900703  -0.36  -0.17  -0.35  0.03

    Values are in *percent* and must be divided by 100 to get decimals.

    Strategy: scan line by line, tokenise each line (trying comma first,
    then whitespace), and skip any line whose first token is not an 8-digit
    integer date. This is robust to header-row count changes and to the
    presence of trailing monthly/annual sections that start with different
    date formats (e.g. 6-digit YYYYMM).
    """
    records = []
    for line in content.splitlines():
        # Try comma splitting first; fall back to whitespace splitting
        if "," in line:
            parts = [p.strip() for p in line.split(",")]
        else:
            parts = line.split()

        if len(parts) < 5:
            continue
        date_str = parts[0].strip()
        # Valid daily rows have exactly 8 numeric characters (YYYYMMDD)
        if not (date_str.isdigit() and len(date_str) == 8):
            continue
        try:
            row = {
                "Date":   pd.to_datetime(date_str, format="%Y%m%d"),
                "Mkt-RF": float(parts[1]) / 100,   # convert % → decimal
                "SMB":    float(parts[2]) / 100,   # Small Minus Big
                "HML":    float(parts[3]) / 100,   # High Minus Low
                "RF":     float(parts[4]) / 100,   # risk-free rate
            }
            records.append(row)
        except (ValueError, IndexError):
            # Skip malformed lines (e.g. section breaks between daily/monthly)
            continue

    if not records:
        raise ValueError(
            "Could not parse any daily rows from the FF3 CSV. "
            "The Ken French file format may have changed — inspect the raw file."
        )

    df = pd.DataFrame(records).set_index("Date")
    df.index = pd.to_datetime(df.index)
    return df


def load_ff3_factors() -> pd.DataFrame:
    """
    Return a clean DataFrame of daily Fama-French 3-factor returns.

    Columns (all in decimal form, i.e. 0.01 = 1%):
      Mkt-RF — daily excess return of the European market over the risk-free rate
      SMB    — daily Small-Minus-Big factor return
      HML    — daily High-Minus-Low (value) factor return
      RF     — daily risk-free rate

    Results are cached locally in ff3_europe_daily.csv so that subsequent
    runs don't re-download (the FF data is updated monthly, so this is fine
    for day-to-day development use).
    """
    from pathlib import Path

    cache = Path(FF3_CACHE)
    if cache.exists():
        print(f"Loading cached FF3 data from {FF3_CACHE}")
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        return df

    content = _download_ff3_raw()
    df = _parse_ff3_csv(content)
    df.to_csv(cache)
    print(f"FF3 data saved: {len(df)} daily observations, "
          f"{df.index[0].date()} → {df.index[-1].date()}")
    return df


# ── Regression ────────────────────────────────────────────────────────────────

def run_ff3_regression(
    prices: pd.DataFrame,
    ff_factors: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Regress each stock's excess returns on the three Fama-French factors.

    Returns
    -------
    loadings : pd.DataFrame  shape (n_stocks, 4)
        Columns: alpha, beta_mkt, beta_smb, beta_hml, r_squared
        Each row is one stock's regression coefficients.

    ff_expected_returns : pd.Series  shape (n_stocks,)
        Annualized expected return for each stock implied by the factor model.
        Computed as:
            E[R_i] = RF_annual
                   + beta_mkt * E[Mkt-RF] * 252
                   + beta_smb * E[SMB]    * 252
                   + beta_hml * E[HML]    * 252

    Notes
    -----
    We use numpy's least-squares solver (equivalent to OLS) to avoid requiring
    statsmodels. The design matrix X includes an intercept column (alpha).
    """
    if ff_factors is None:
        ff_factors = load_ff3_factors()

    stock_returns = daily_returns(prices)  # daily arithmetic returns

    # ── Align dates ───────────────────────────────────────────────────────────
    # Inner join on date index keeps only days that appear in BOTH datasets.
    # Stock exchanges and the FF data may have different holiday calendars, so
    # some mismatches are expected (typically <5% of observations).
    common_dates = stock_returns.index.intersection(ff_factors.index)
    stock_rets_aligned = stock_returns.loc[common_dates]
    ff_aligned = ff_factors.loc[common_dates]

    print(f"  FF3 regression: {len(common_dates)} overlapping trading days "
          f"({len(stock_returns) - len(common_dates)} dropped due to calendar mismatch)")

    # ── Build OLS inputs ──────────────────────────────────────────────────────
    # Excess return for each stock = raw return minus the daily risk-free rate.
    # This is the dependent variable y_i in the regression.
    rf_daily = ff_aligned["RF"].values          # shape: (T,)
    excess_returns = stock_rets_aligned.subtract(rf_daily, axis=0)  # y, shape: (T, N)

    # Independent variables: intercept column + three factor returns.
    # X has shape (T, 4): [1, Mkt-RF, SMB, HML]
    X = np.column_stack([
        np.ones(len(ff_aligned)),          # intercept → captures alpha
        ff_aligned["Mkt-RF"].values,       # market excess return
        ff_aligned["SMB"].values,          # size factor
        ff_aligned["HML"].values,          # value factor
    ])

    # ── Run OLS for each stock ────────────────────────────────────────────────
    # np.linalg.lstsq solves: min ||X @ beta - y||² for each column of y.
    # We solve all stocks at once by passing the full (T × N) matrix.
    betas, _, _, _ = np.linalg.lstsq(X, excess_returns.values, rcond=None)
    # betas shape: (4, N) → rows are [alpha, beta_mkt, beta_smb, beta_hml]

    # R² for each stock: 1 - SS_residual / SS_total
    y_hat = X @ betas                          # fitted values, shape (T, N)
    ss_res = ((excess_returns.values - y_hat) ** 2).sum(axis=0)
    ss_tot = ((excess_returns.values - excess_returns.values.mean(axis=0)) ** 2).sum(axis=0)
    r_squared = np.where(ss_tot > 0, 1 - ss_res / ss_tot, 0.0)

    tickers = list(prices.columns)
    loadings = pd.DataFrame(
        {
            "alpha":    betas[0],   # daily alpha (excess return unexplained by factors)
            "beta_mkt": betas[1],   # market beta — positive for all equity-like assets
            "beta_smb": betas[2],   # >0 = small-cap tilt; <0 = large-cap tilt
            "beta_hml": betas[3],   # >0 = value tilt; <0 = growth tilt
            "r_squared": r_squared, # fraction of variance explained by the 3 factors
        },
        index=tickers,
    )

    # ── Expected return under FF3 ─────────────────────────────────────────────
    # Use the historical mean of each factor as a proxy for the expected premium.
    # Annualize by multiplying by 252 (daily → annual).
    rf_annual     = rf_daily.mean() * TRADING_DAYS
    e_mkt_rf      = ff_aligned["Mkt-RF"].mean() * TRADING_DAYS  # ~4–8% for developed markets
    e_smb         = ff_aligned["SMB"].mean()     * TRADING_DAYS  # ~0–3% historically
    e_hml         = ff_aligned["HML"].mean()     * TRADING_DAYS  # ~2–5% historically

    # E[R_i] = RF + beta_mkt*E[Mkt-RF] + beta_smb*E[SMB] + beta_hml*E[HML]
    # Note: alpha is excluded — in an efficient market alpha is not expected to persist
    ff_expected_returns = pd.Series(
        rf_annual
        + loadings["beta_mkt"] * e_mkt_rf
        + loadings["beta_smb"] * e_smb
        + loadings["beta_hml"] * e_hml,
        index=tickers,
        name="FF3 Expected Return",
    )

    return loadings, ff_expected_returns


# ── Human-readable summary ────────────────────────────────────────────────────

def print_loadings(loadings: pd.DataFrame, ff_returns: pd.Series) -> None:
    """Print a formatted table of factor loadings and FF3 expected returns."""
    display = loadings[["beta_mkt", "beta_smb", "beta_hml", "alpha", "r_squared"]].copy()
    display["FF3 E[R]"] = ff_returns
    display = display.round(4)
    print(display.to_string())

    print("\n  Interpretation guide:")
    print("  beta_mkt > 1  : more volatile than the European market (aggressive)")
    print("  beta_smb > 0  : behaves like a small-cap stock (size premium exposure)")
    print("  beta_hml > 0  : value stock (high book-to-market, e.g. banks, utilities)")
    print("  beta_hml < 0  : growth stock (low book-to-market, e.g. tech, luxury)")


# ── Module smoke test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    from data import load_prices

    prices = load_prices()
    ff = load_ff3_factors()

    print(f"\nFF3 factor data: {len(ff)} rows")
    print(f"  Date range : {ff.index[0].date()} → {ff.index[-1].date()}")
    print(f"  Mean annual Mkt-RF: {ff['Mkt-RF'].mean() * 252 * 100:.2f}%")
    print(f"  Mean annual SMB   : {ff['SMB'].mean()    * 252 * 100:.2f}%")
    print(f"  Mean annual HML   : {ff['HML'].mean()    * 252 * 100:.2f}%")

    print("\n=== Fama-French 3-Factor Loadings ===")
    loadings, ff_rets = run_ff3_regression(prices, ff)
    print_loadings(loadings, ff_rets)
