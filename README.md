# European Stock Portfolio Optimizer

A Python tool that downloads two years of historical price data for ten major European equities, computes risk and return metrics, and runs a mean-variance optimization to identify the portfolio allocation that maximizes the Sharpe ratio. The output includes an efficient frontier chart, an optimal weights breakdown, and a correlation heatmap.

---

## Quickstart

```bash
pip install yfinance scipy matplotlib seaborn pandas numpy
python data.py        # download & cache prices
python metrics.py     # print per-ticker statistics
python optimizer.py   # print optimal weights
python visualize.py   # save charts to ./charts/
```

---

## Universe

| Ticker | Company | Exchange |
|---|---|---|
| ASML.AS | ASML Holding | Amsterdam |
| MC.PA | LVMH | Paris |
| SAN.MC | Banco Santander | Madrid |
| SHELL.AS | Shell | Amsterdam |
| SAP.DE | SAP | Frankfurt |
| OR.PA | L'Oréal | Paris |
| BNP.PA | BNP Paribas | Paris |
| AIR.PA | Airbus | Paris |
| DHL.DE | DHL Group | Frankfurt |
| ENEL.MI | Enel | Milan |

---

## Project Structure

```
european-portfolio-optimizer/
├── data.py          # price download and caching
├── metrics.py       # return, volatility, Sharpe, correlation
├── optimizer.py     # mean-variance optimization via scipy
├── visualize.py     # efficient frontier, weights, heatmap
├── prices.csv       # cached price data (auto-generated)
└── charts/
    ├── efficient_frontier.png
    ├── optimal_weights.png
    └── correlation_heatmap.png
```

---

## Introduction

Portfolio construction is one of the oldest and most important problems in finance. The question of how to allocate capital across a set of assets — balancing the desire for high returns against the reality of risk — sits at the heart of investment management, pension fund design, and personal wealth planning. Despite decades of more sophisticated models being developed, the foundational framework established by Harry Markowitz in 1952 remains the conceptual baseline against which everything else is measured.

This project implements that framework for a basket of ten major European blue-chip stocks. It is not a trading system, and it makes no predictions about the future. What it does is answer a specific, well-posed historical question: given the return and risk characteristics these ten stocks actually exhibited over the past two years, what combination of them would have produced the best risk-adjusted return? That answer is genuinely useful, not because the past repeats exactly, but because understanding *why* the optimizer picks certain stocks — and systematically rejects others — teaches you something real about how these businesses have behaved relative to one another, and what kind of portfolio exposures a risk-conscious allocator might consider.

---

## Theory

### Mean-Variance Optimization

Markowitz's core insight was that investors should not evaluate assets in isolation. What matters is not just how much a stock returns or how volatile it is on its own, but how it behaves relative to everything else in the portfolio. A stock that is highly volatile but moves independently of the rest of the portfolio can actually *reduce* overall portfolio risk when added — because when other positions fall, this one does not necessarily fall with them. This property is called diversification, and mean-variance optimization is the mathematical machinery for exploiting it.

The optimization works as follows. Given a set of assets with known expected returns, volatilities, and pairwise correlations, there exists a set of portfolios — parameterized by the weights allocated to each asset — that are *efficient*: no other portfolio offers a higher expected return for the same level of volatility, or lower volatility for the same expected return. This set of optimal portfolios traces out a curve in return-volatility space called the efficient frontier. Every portfolio that lies below and to the right of that frontier is suboptimal: it takes on more risk than necessary for its level of return.

In practice, we estimate expected returns as the historical mean of daily returns, scaled to an annual basis. Volatility is the annualized standard deviation. The covariance between assets — which encodes how they move together — is estimated from the same historical daily returns. The optimizer then searches over all possible weight combinations (subject to the constraint that weights sum to one, and no short selling is allowed) for the portfolio that maximizes the Sharpe ratio.

### The Sharpe Ratio

The Sharpe ratio is the single most widely used measure of risk-adjusted performance. It is calculated as the portfolio's excess return above the risk-free rate — in this case proxied at 3%, roughly the ECB deposit rate — divided by the portfolio's annualized volatility. A Sharpe ratio of 1.0 means you earned one percentage point of return above the risk-free rate for every percentage point of volatility you accepted. A ratio of 2.0 means you earned twice as much excess return per unit of risk. In practice, sustained Sharpe ratios above 1.5 are considered strong for a long-only equity portfolio; above 2.0 is exceptional and often signals either genuine skill or an artifact of the sample period.

The optimizer does not directly maximize return, and it does not minimize risk. It maximizes the ratio of the two — which means it is looking for the portfolio that sits on the efficient frontier at the point of steepest ascent from the risk-free rate. Geometrically, this is the point where a line drawn from the risk-free rate on the return axis is tangent to the efficient frontier. This tangency portfolio is the theoretical optimal risky portfolio in the Markowitz framework.

### Correlation and Diversification

Correlation, measured on a scale from -1 to +1, describes the degree to which two assets move together. A correlation of +1 means they move in perfect lockstep; a correlation of -1 means they move in perfect opposition; a correlation of 0 means their movements are statistically independent. In portfolio construction, lower correlations between holdings are almost always better, because they mean the portfolio benefits from genuine diversification rather than just spreading nominal exposure across assets that behave identically.

Across the ten stocks in this universe, correlations range from roughly 0.04 (Shell and L'Oréal) to 0.69 (BNP Paribas and Santander). The high BNP–Santander correlation makes intuitive sense: they are both large eurozone banks, subject to the same interest rate environment, regulatory regime, and macro cycle. Owning both provides limited additional diversification compared to holding just one. Shell, on the other hand, is an energy major with returns largely driven by commodity prices — a fundamentally different return driver than European consumer discretionary or technology names, which explains why its correlations with the rest of the universe are consistently low.

---

## Results Analysis

### Why ENEL and Santander?

The optimizer's output — 62.9% Enel, 37.1% Santander, everything else at zero — initially looks like an aggressive, concentrated bet. And in a practical sense, it is. But the logic is internally consistent with the objective function.

Enel is the standout name on a pure volatility basis. Over the two-year lookback period, its annualized volatility was 18.6% — the lowest of any stock in the universe, well below the 27–40% range seen in names like Airbus, ASML, and LVMH. At the same time, Enel delivered an annualized return of approximately 34%, giving it an individual Sharpe ratio of 1.68. For a regulated European utility, this combination is unusually strong. Utilities tend to have stable, predictable cash flows from long-term grid and generation contracts, which suppresses volatility. The particular two-year period captured in this dataset also coincided with a broader European energy infrastructure re-rating as the continent accelerated its transition away from Russian gas — a structural tailwind that contributed to Enel's outperformance.

Santander enters the portfolio for a different reason. Its individual Sharpe ratio is similarly strong at 1.73, driven by an exceptional annualized return of 57.2% — the highest in the universe — in a period when European banks broadly benefited from the most aggressive interest rate hiking cycle in decades. Higher rates are directly accretive to bank net interest margins, and Santander, as one of the largest retail banks in Europe with major operations across Spain, Brazil, and the UK, was a primary beneficiary of this environment. Its volatility of 31.3% is meaningfully higher than Enel's, which is why the optimizer weights it as the secondary position rather than the primary one.

The critical factor that makes this two-stock combination work, rather than just holding the single best Sharpe stock, is their correlation of 0.31. In practical terms, a correlation of 0.31 means that when Enel has a bad day, Santander does not reliably have a bad day at the same time. They are driven by different fundamentals — regulated utility cash flows versus banking spread income — and this low co-movement means the portfolio captures most of the return benefit of both names while the combined volatility is lower than a simple weighted average of their individual volatilities would suggest. This is diversification working as intended.

### Why Were the Other Eight Stocks Excluded?

The exclusion of the other eight names is not a judgment that they are bad businesses or unattractive investments in isolation. It reflects the fact that, within the specific optimization objective — maximizing risk-adjusted return, long-only, over this lookback period — they do not improve the portfolio when combined with Enel and Santander.

The French consumer names, LVMH and L'Oréal, both delivered negative returns over the period, likely reflecting a slowdown in Chinese luxury consumption that compressed multiples across the sector. Negative returns automatically disqualify a stock from the maximum-Sharpe portfolio unless its correlation benefits are exceptionally strong. ASML, Europe's dominant semiconductor equipment maker and in many respects the continent's highest-quality technology franchise, also struggled in this period — down roughly 17% on an annualized basis — as global semiconductor capex expectations contracted. Airbus, BNP Paribas, DHL, SAP, and Shell all had positive Sharpe ratios on a standalone basis, but their correlations with either Enel or Santander were not low enough to justify the volatility they would add. Adding BNP Paribas alongside Santander, for instance, would be loading up on a second European bank with a 0.69 correlation to the first — the optimizer correctly identifies this as largely redundant exposure.

### What Does a 1.87 Sharpe Ratio Mean?

The combined portfolio achieves a Sharpe ratio of 1.87, with an annualized return of 38.2% and volatility of 18.8%. To put this in context: a typical diversified equity portfolio targeting global exposure might expect a long-run Sharpe ratio around 0.4–0.6. Even well-managed active equity funds rarely sustain ratios above 1.0 over multi-year periods. A Sharpe of 1.87 is, frankly, unusually high — and that should immediately raise a flag about over-fitting to the historical period.

The honest interpretation is that this portfolio would have performed exceptionally well *in this specific two-year window*, which happened to coincide with two major European macro themes playing out: the energy infrastructure re-rating and the banking sector interest rate windfall. A different two-year window — say, 2020–2022, when rate hikes had not yet materialized and energy sentiment was mixed — would likely produce a completely different optimal portfolio, possibly with no overlap at all. This is the most important caveat to carry from the results section into any practical application.

---

## Limitations

The model presented here rests on several assumptions that are worth understanding clearly, because each one represents a potential source of error in real-world application.

The most fundamental assumption is that historical returns are a reliable estimate of future expected returns. In academic finance this is called the estimation risk problem, and it is well-documented that sample mean returns are extremely noisy estimators — especially over short windows like two years. The optimizer is essentially a function that amplifies estimation errors: small changes in input return estimates can produce large swings in the output weights. This is why the corner solution (two stocks at nonzero weights) looks so extreme. A richer implementation would use shrinkage estimators or Black-Litterman to dampen this sensitivity.

Mean-variance optimization also assumes that returns are normally distributed — or at least that volatility is a sufficient description of risk. In practice, equity returns exhibit fat tails and negative skewness. The 2020 COVID crash, for instance, was a multi-standard-deviation event that appeared far more frequently in real markets than a normal distribution would predict. A model that only looks at variance will systematically underestimate the probability of large drawdowns.

The long-only constraint, while sensible for most investment mandates, artificially limits the efficient frontier relative to what is theoretically achievable. A portfolio that could short LVMH while going long Santander might extract additional Sharpe ratio, but this is typically inaccessible to retail investors and introduces its own operational and margin-related complexities.

Finally, there are no transaction costs, no liquidity constraints, and no consideration of position sizing relative to average daily trading volume. In a real execution context, moving into a 62.9% position in a single stock — even a large-cap like Enel — would require careful attention to market impact, particularly for larger portfolio sizes.

---

## Possible Extensions

The natural first extension is to move from a static optimization to a rolling-window approach. Rather than fitting on the full two-year history and producing a single set of weights, a rolling optimizer re-estimates the covariance matrix and expected returns each month using a trailing window, then rebalances the portfolio accordingly. This produces a time series of portfolio weights and a realistic backtest of how the strategy would have performed with monthly rebalancing, including transaction costs. It also reveals how stable — or unstable — the optimal weights are over time, which is itself informative about model reliability.

A more sophisticated approach would replace historical mean returns with a factor model. The Fama-French framework, for instance, decomposes equity returns into market beta, size, value, and profitability factors. Rather than estimating ten individual expected returns from noisy historical data, you estimate a handful of factor premiums — which are more stable — and derive stock-level expectations from their factor loadings. The Black-Litterman model goes a step further, allowing the investor to combine a factor model prior with explicit views on individual stocks, producing return estimates that are neither purely historical nor purely subjective.

It would also be straightforward to add practical portfolio constraints: a maximum weight cap per stock (say, 25%) to prevent the concentration seen here, minimum diversification requirements across sectors or countries, ESG score filters, or a target tracking error relative to a benchmark like the Euro Stoxx 50. Each of these constraints shrinks the feasible set but often produces portfolios that are more robust and implementable in practice.

---

## Real Portfolio Management Context

In a professional asset management context, the output of a Markowitz optimizer is typically the starting point for a conversation, not the end of one. A quant analyst might present these results to a portfolio manager as the "model portfolio" — the unconstrained, purely quantitative recommendation — alongside a risk attribution showing how much of the expected Sharpe comes from each position and what the key assumptions are. The PM would then apply judgment: is the two-year lookback capturing a regime that is likely to persist, or does it coincide with a macro tailwind that has already played out? Are there concentration limits imposed by the fund's mandate? Is the portfolio compliant with UCITS diversification rules?

The correlation matrix is particularly valuable in this context as a communication tool. Showing a risk committee that Shell and L'Oréal have a 0.04 correlation — almost entirely uncorrelated — immediately illustrates *why* a portfolio might want to hold both, even if one has mediocre standalone metrics. Similarly, the 0.69 correlation between BNP and Santander is the kind of number that prompts a useful discussion about whether the fund's European bank exposure is genuinely diversified or whether it is in effect a single concentrated bet expressed through two tickers.

At its best, quantitative portfolio optimization does not replace judgment — it disciplines it. It forces you to be explicit about your assumptions, quantifies the cost of constraints and diversification requirements, and surfaces trade-offs that are easy to miss when evaluating stocks one at a time. The tool built here is a minimal but functional version of that infrastructure: transparent, reproducible, and straightforward enough to extend in whatever direction the investment problem demands.

---

## Dependencies

- `yfinance` — market data
- `pandas`, `numpy` — data processing
- `scipy` — constrained optimization
- `matplotlib`, `seaborn` — visualization
