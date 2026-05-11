"""
main.py — Entry point for the European portfolio optimizer.

Runs the full pipeline in order:
  1. Load (or download) 2 years of historical price data
  2. Print per-ticker risk/return metrics and the correlation matrix
  3. Run mean-variance optimization — both historical and Fama-French methods
  4. Generate and save all four charts as PNGs to ./charts/

Run with:
    python main.py
"""

import time
from data import load_prices
from metrics import summary, daily_returns, correlation_matrix
from optimizer import maximize_sharpe, compare_methods
from visualize import plot_efficient_frontier, plot_weights, plot_correlation, plot_factor_loadings


def print_section(title: str) -> None:
    """Print a clearly visible section header to separate pipeline stages."""
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def main() -> None:
    start = time.time()

    # ── Step 1: Data ──────────────────────────────────────────────────────────
    # load_prices() returns the cached CSV if it exists, otherwise fetches from
    # Yahoo Finance and writes the cache. All subsequent steps use this DataFrame.
    print_section("Step 1 / 5 — Loading price data")
    prices = load_prices()
    print(f"  {len(prices)} trading days × {len(prices.columns)} tickers loaded")
    print(f"  Date range: {prices.index[0].date()} → {prices.index[-1].date()}")

    # ── Step 2: Metrics ───────────────────────────────────────────────────────
    # Print the per-ticker summary (annualized return, volatility, Sharpe) and
    # the full pairwise correlation matrix so the user can see the raw inputs
    # that the optimizer will act on.
    print_section("Step 2 / 5 — Per-ticker metrics")
    stats = summary(prices)
    print(stats.to_string())

    print_section("Correlation matrix")
    rets = daily_returns(prices)
    corr = correlation_matrix(rets)
    print(corr.round(3).to_string())

    # ── Step 3: Optimization ──────────────────────────────────────────────────
    # We run optimization under two different return models and compare results.
    # Both use the same historical covariance matrix; only the expected return
    # vector differs.
    print_section("Step 3 / 5 — Historical mean-variance optimization")
    opt_hist = maximize_sharpe(prices, use_ff=False)
    print(opt_hist.summary().to_string())

    allocated = [(t, w) for t, w in zip(opt_hist.tickers, opt_hist.weights) if w > 0.001]
    print(f"\n  Non-zero positions: {len(allocated)} of {len(opt_hist.tickers)}")
    for ticker, weight in sorted(allocated, key=lambda x: -x[1]):
        print(f"    {ticker:12s}  {weight * 100:.1f}%")

    # ── Step 3b: Fama-French optimization ─────────────────────────────────────
    # compare_methods() downloads FF3 data (or uses cache), runs both optimizers,
    # and prints a formatted side-by-side comparison of weights and portfolio stats.
    print_section("Step 3b / 5 — Fama-French 3-factor optimization")
    print("  Comparison of Historical vs Fama-French expected returns:\n")
    compare_methods(prices)

    # ── Step 4: Visualizations ────────────────────────────────────────────────
    # Each plot function recomputes what it needs from prices so they can also
    # be called independently. Charts are saved to ./charts/ as 150-dpi PNGs.
    print_section("Step 4 / 5 — Generating charts")

    print("  Efficient frontier (this takes ~30s — solving 500 optimizations)...")
    plot_efficient_frontier(prices)

    print("  Optimal weights bar chart...")
    plot_weights(prices)

    print("  Correlation heatmap...")
    plot_correlation(prices)

    print("  Factor loadings chart...")
    plot_factor_loadings(prices)

    # ── Done ──────────────────────────────────────────────────────────────────
    elapsed = time.time() - start
    print_section(f"Done  ({elapsed:.1f}s)")
    print("  Charts saved to ./charts/")
    print("    efficient_frontier.png")
    print("    optimal_weights.png")
    print("    correlation_heatmap.png")
    print("    factor_loadings.png\n")


if __name__ == "__main__":
    main()
