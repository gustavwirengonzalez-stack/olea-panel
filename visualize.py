"""
visualize.py — Charts for the European portfolio optimizer.

Produces four PNG files saved to ./charts/:
  1. efficient_frontier.png  — scatter of random portfolios + frontier curve + optimal star
  2. optimal_weights.png     — horizontal bar chart of the max-Sharpe weights
  3. correlation_heatmap.png — lower-triangle annotated correlation heatmap
  4. factor_loadings.png     — grouped bar chart of each stock's FF3 factor betas
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # non-interactive backend; safe for scripts and servers
                        # swap to "TkAgg" or "Qt5Agg" if you want a live window
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.colors import Normalize
import seaborn as sns
from pathlib import Path

from data import load_prices
from metrics import daily_returns, correlation_matrix
from optimizer import maximize_sharpe, efficient_frontier

OUTPUT_DIR = Path("charts")
OUTPUT_DIR.mkdir(exist_ok=True)  # create ./charts/ if it doesn't exist yet

# Shared style constants
FRONTIER_CMAP = "viridis"    # colormap for Sharpe-coded scatter points
OPTIMAL_COLOR = "#e63946"    # red star marking the max-Sharpe portfolio
GRID_ALPHA = 0.25            # subtle grid lines — visible but not distracting


def _savefig(fig: plt.Figure, name: str) -> None:
    """Save a figure to the charts directory and close it to free memory."""
    path = OUTPUT_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved → {path}")
    plt.close(fig)


# ── 1. Efficient frontier ─────────────────────────────────────────────────────

def plot_efficient_frontier(
    prices: pd.DataFrame,
    n_portfolios: int = 500,
    n_random: int = 3_000,
) -> None:
    """
    Plot the efficient frontier with three layers:

    Layer 1 — Random portfolio cloud (background scatter)
        We sample 3,000 random weight vectors from a Dirichlet distribution.
        Dirichlet is the natural distribution over simplex (sums-to-one) weight
        vectors, so every sample is a valid long-only portfolio. Each point is
        coloured by its Sharpe ratio to show how risk-adjusted quality varies
        across the feasible space.

    Layer 2 — Efficient frontier curve
        The blue line traces the minimum-variance portfolio at each return level,
        computed by optimizer.efficient_frontier(). Points on this curve are
        optimal — no other portfolio offers lower volatility for the same return.

    Layer 3 — Maximum-Sharpe portfolio (star marker)
        The single point on the frontier with the highest Sharpe ratio, which
        is the tangency point between the frontier and the Capital Market Line.
    """
    rets = daily_returns(prices)
    mean_r = rets.mean().values
    cov = rets.cov().values
    n = len(prices.columns)
    TRADING_DAYS = 252
    RF = 0.03

    # --- Layer 1: random portfolio cloud ---
    # dirichlet(ones) samples uniformly from the weight simplex
    rng = np.random.default_rng(42)  # seed for reproducibility
    rand_weights = rng.dirichlet(np.ones(n), size=n_random)

    # Vectorized return calculation: (n_random, n) @ (n,) → (n_random,)
    rand_ret = rand_weights @ mean_r * TRADING_DAYS

    # Volatility must be computed per-portfolio (no simple vectorization for quadratic form)
    rand_vol = np.array(
        [np.sqrt(w @ cov @ w) * np.sqrt(TRADING_DAYS) for w in rand_weights]
    )
    rand_sh = (rand_ret - RF) / rand_vol

    # --- Layer 2 & 3: frontier line and optimal point ---
    ef = efficient_frontier(prices, n_portfolios=n_portfolios)
    opt = maximize_sharpe(prices)

    fig, ax = plt.subplots(figsize=(10, 6))

    # Scatter: x=volatility%, y=return%, colour=Sharpe
    norm = Normalize(vmin=rand_sh.min(), vmax=rand_sh.max())
    sc = ax.scatter(
        rand_vol * 100,
        rand_ret * 100,
        c=rand_sh,
        cmap=FRONTIER_CMAP,
        norm=norm,
        s=6,
        alpha=0.5,
        linewidths=0,
        zorder=1,
    )
    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Sharpe Ratio", fontsize=10)

    # Frontier line — draw white first (slightly thicker) for a glow effect
    ax.plot(ef["Volatility"] * 100, ef["Return"] * 100,
            color="white", linewidth=2.5, zorder=2, label="Efficient frontier")
    ax.plot(ef["Volatility"] * 100, ef["Return"] * 100,
            color="#2196f3", linewidth=1.5, zorder=3)

    # Optimal portfolio star
    ax.scatter(
        opt.volatility * 100,
        opt.expected_return * 100,
        marker="*",
        s=300,
        color=OPTIMAL_COLOR,
        zorder=5,
        label=f"Max Sharpe  ({opt.sharpe:.2f})",
        edgecolors="white",
        linewidths=0.8,
    )

    ax.set_xlabel("Annualised Volatility (%)", fontsize=11)
    ax.set_ylabel("Annualised Return (%)", fontsize=11)
    ax.set_title("Efficient Frontier — European Portfolio", fontsize=13, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(alpha=GRID_ALPHA, linestyle="--")

    # Dark theme styling
    ax.set_facecolor("#0d1117")
    fig.patch.set_facecolor("#0d1117")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

    _savefig(fig, "efficient_frontier.png")


# ── 2. Optimal weights bar chart ──────────────────────────────────────────────

def plot_weights(prices: pd.DataFrame) -> None:
    """
    Horizontal bar chart of the maximum-Sharpe portfolio weights.

    Stocks are sorted ascending so the largest allocation appears at the top.
    Weights are displayed as percentages with inline labels on each bar.
    Stocks with ~0% weight (excluded by the optimizer) are still shown so
    the full universe is visible and the exclusions are explicit.
    """
    opt = maximize_sharpe(prices)

    # Sort ascending so largest bar is at the top of a horizontal chart
    weights = pd.Series(opt.weights, index=opt.tickers).sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(8, 5))

    # Map each bar to a position along the viridis colormap for visual variety
    colors = cm.viridis(np.linspace(0.2, 0.85, len(weights)))
    bars = ax.barh(weights.index, weights.values * 100, color=colors, edgecolor="none")

    # Inline percentage labels just to the right of each bar
    for bar, val in zip(bars, weights.values * 100):
        ax.text(
            val + 0.3,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}%",
            va="center",
            fontsize=9,
            color="white",
        )

    ax.set_xlabel("Weight (%)", fontsize=11)
    ax.set_title(
        f"Optimal Portfolio Weights  |  Sharpe {opt.sharpe:.2f}",
        fontsize=12,
        fontweight="bold",
    )
    # Add 20% padding to the right so the inline labels don't get clipped
    ax.set_xlim(0, weights.max() * 100 * 1.2)
    ax.grid(axis="x", alpha=GRID_ALPHA, linestyle="--")

    # Dark theme styling
    ax.set_facecolor("#0d1117")
    fig.patch.set_facecolor("#0d1117")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.title.set_color("white")

    _savefig(fig, "optimal_weights.png")


# ── 3. Correlation heatmap ────────────────────────────────────────────────────

def plot_correlation(prices: pd.DataFrame) -> None:
    """
    Lower-triangle annotated heatmap of pairwise return correlations.

    Only the lower triangle is shown (mask=upper triangle) to avoid
    redundant information — the matrix is symmetric, so the upper half
    would be a mirror image of the lower half.

    RdYlGn colormap: red = negative correlation, yellow = ~0, green = positive.
    Center=0 anchors the neutral colour at zero correlation rather than at the
    midpoint of the data range.
    """
    rets = daily_returns(prices)
    corr = correlation_matrix(rets)

    fig, ax = plt.subplots(figsize=(9, 7))

    # Mask the upper triangle (k=1 keeps the diagonal; k=0 would mask it too)
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)

    sns.heatmap(
        corr,
        ax=ax,
        mask=mask,
        annot=True,        # show numeric values in each cell
        fmt=".2f",         # two decimal places
        cmap="RdYlGn",
        center=0,          # neutral colour at correlation = 0
        vmin=-1,
        vmax=1,
        linewidths=0.4,    # thin grid lines between cells
        linecolor="#1a1a2e",
        annot_kws={"size": 8},
        cbar_kws={"shrink": 0.75, "label": "Pearson r"},
    )

    ax.set_title("Return Correlation Matrix — European Stocks", fontsize=12, fontweight="bold")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=35, ha="right", fontsize=9)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=9)

    # Dark theme styling
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    ax.tick_params(colors="white")
    ax.title.set_color("white")

    _savefig(fig, "correlation_heatmap.png")


# ── 4. Fama-French factor loadings ───────────────────────────────────────────

def plot_factor_loadings(prices: pd.DataFrame) -> None:
    """
    Grouped bar chart of each stock's Fama-French 3-factor betas.

    Each stock gets three bars — one for each factor loading:
      beta_mkt (blue)  — market sensitivity; almost always positive for equities
      beta_smb (green) — positive = small-cap behaviour, negative = large-cap
      beta_hml (orange)— positive = value stock (cheap), negative = growth stock

    Reading the chart:
      - Stocks with tall blue bars are highly correlated with the overall market
        (cyclicals, financials, industrials).
      - Stocks with positive orange bars (HML) are value tilts — often banks,
        utilities, and energy companies that trade at low price-to-book ratios.
      - Stocks with negative orange bars are growth tilts — tech, luxury, and
        quality businesses that trade at premium valuations.
      - The SMB bar distinguishes large-caps (negative) from mid/small-caps
        (positive) — most major European blue-chips have negative SMB loadings
        because they behave like large-caps.
    """
    from factors import run_ff3_regression

    loadings, _ = run_ff3_regression(prices)

    tickers = loadings.index.tolist()
    n = len(tickers)
    x = np.arange(n)

    # Bar width and offsets for 3 grouped bars per stock
    width = 0.25
    offsets = [-width, 0, width]

    # Factor colours chosen for accessibility and visual contrast on a dark background
    factor_colors = {
        "beta_mkt": "#4fc3f7",   # light blue — market factor
        "beta_smb": "#81c784",   # light green — size factor
        "beta_hml": "#ffb74d",   # amber — value factor
    }
    factor_labels = {
        "beta_mkt": "β Market (Mkt-RF)",
        "beta_smb": "β Size (SMB)",
        "beta_hml": "β Value (HML)",
    }

    fig, ax = plt.subplots(figsize=(13, 6))

    for (factor, color), offset in zip(factor_colors.items(), offsets):
        values = loadings[factor].values
        bars = ax.bar(
            x + offset,
            values,
            width=width,
            color=color,
            label=factor_labels[factor],
            edgecolor="none",
            alpha=0.85,
        )
        # Inline value labels on bars that are tall enough to label
        for bar, val in zip(bars, values):
            if abs(val) > 0.03:   # skip near-zero bars to reduce clutter
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + (0.015 if val >= 0 else -0.04),
                    f"{val:.2f}",
                    ha="center",
                    va="bottom" if val >= 0 else "top",
                    fontsize=7,
                    color="white",
                )

    # Zero line for visual reference (positive = above-average exposure)
    ax.axhline(0, color="#888", linewidth=0.8, linestyle="--")

    ax.set_xticks(x)
    ax.set_xticklabels(tickers, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("Factor Loading (β)", fontsize=11)
    ax.set_title(
        "Fama-French 3-Factor Loadings — European Stocks\n"
        "Positive HML = value tilt  |  Negative HML = growth tilt  |  "
        "Positive SMB = small-cap tilt",
        fontsize=11,
        fontweight="bold",
    )
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(axis="y", alpha=GRID_ALPHA, linestyle="--")

    # Dark theme styling
    ax.set_facecolor("#0d1117")
    fig.patch.set_facecolor("#0d1117")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")

    _savefig(fig, "factor_loadings.png")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    prices = load_prices()

    print("Plotting efficient frontier...")
    plot_efficient_frontier(prices)

    print("Plotting optimal weights...")
    plot_weights(prices)

    print("Plotting correlation heatmap...")
    plot_correlation(prices)

    print("Plotting factor loadings...")
    plot_factor_loadings(prices)

    print("\nAll charts saved to ./charts/")
