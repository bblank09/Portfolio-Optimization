# Optimization Assumptions & Methodology

Status: **decided, not yet implemented.** This is the Phase 1–3 output of forking this
project from `Backtest Portfolio Webull:SEC OPENAI`. It records what will be built and
why, sourced against external references, before any optimizer code is written.

## Scope vs. the parent backtester

The parent project answers "what happened to a *given* portfolio historically." This
project answers "what allocation would have been *optimal* under a stated objective,
and how robust is that answer out-of-sample." The parent's `backend/app/engine/`
(returns/risk/drawdown/rebalancing) has **no optimizer code** — this project adds a new
`backend/app/optimizer/` module rather than modifying the reused engine, and reuses the
engine to score candidate weight sets during rolling-window validation.

## Data

Same SEC Thailand Open Data mutual fund NAV universe and cached parquet pipeline as the
parent project (`backend/app/sec/`, `data/sec/`). No new data source in this phase.

## Core engine

**[riskfolio-lib](https://riskfolio-lib.readthedocs.io/en/latest/)** (Python), covering:

- **Models:** mean-risk (min risk / max return / max utility / max risk-adjusted
  ratio), risk parity, hierarchical clustering (HRP, HERC), Black-Litterman (standard,
  Bayesian, Augmented), Worst-Case mean-variance.
- **Risk measures:** standard deviation, semi-variance, CVaR, CDaR, EVaR, Ulcer Index,
  max drawdown, and 20+ others — chosen per objective, not fixed to variance.
- **Inputs:** historical return series (from the existing NAV cache), a covariance
  estimator, an expected-return estimator, and constraints (weight bounds, turnover,
  cardinality).
- **Outputs:** portfolio weights, an efficient frontier per risk measure, a
  risk-contribution breakdown, and standard performance metrics.

Secondary reference (not a dependency): [nutdnuy/AssetManagementToolkit](https://github.com/nutdnuy/AssetManagementToolkit),
an independent Python implementation of the same method family plus shrinkage/EWMA/
spectral covariance estimators and walk-forward validation patterns — useful for
cross-checking riskfolio-lib's output on synthetic data and for borrowing covariance-
shrinkage/rolling-window patterns if riskfolio-lib's built-ins are awkward to wire into
FastAPI. Its code has not yet been read line-by-line; treat as reference only until it is.

## Default objective (decision, with rationale)

**Default to Black-Litterman or a shrinkage-covariance mean-variance objective, not
naive mean-variance**, and pair every "optimal weights" result with an out-of-sample
rolling-window backtest rather than showing only an in-sample efficient-frontier point.

Rationale: naive mean-variance optimization is well-documented as highly sensitive to
estimation error in expected returns and the covariance matrix — Michaud (1989) called
it an "error maximizer," and this risk is worse on a thin, less-liquid fund universe
like SEC Thailand's than on a broad US index set. Riskfolio-lib's Black-Litterman and
shrinkage-covariance options exist specifically to dampen this. The rolling-window /
walk-forward pattern (re-optimize on a trailing window, test on the next unseen period,
repeat forward) is the standard way to show whether a proposed optimal weighting held up
historically rather than only fitting the sample it was estimated from — this mirrors
[PortfolioVisualizer's rolling-optimization tool](https://www.portfoliovisualizer.com/rolling-optimization)
that the user cited as a reference.

## Results/output shape to design toward

Based on standard portfolio-optimization tooling (riskfolio-lib, PortfolioVisualizer):
efficient frontier chart, optimal weights table, expected return/volatility/Sharpe,
per-asset risk-contribution breakdown, and a rolling out-of-sample performance chart —
these should shape the future mock-UI "Results" tab design.

## Open gaps (not yet resolved — revisit before implementation)

- Black-Litterman input mechanics were corroborated via riskfolio-lib's own model
  documentation, not verified directly against portfoliovisualizer.com/black-litterman-model
  (that page returned HTTP 403 to automated fetch). Standard and well-established
  enough to proceed, but worth a manual look before implementing the BL view-input UI.
- `AssetManagementToolkit`'s code/tests have not been read in detail.
- Fund-universe size/history depth (`data/sec/mvp_fund_universe.csv`) has not yet been
  checked for whether it's large/long enough for stable covariance estimation — small-N
  portfolios are exactly where MVO's estimation-error problem is worst. Check before
  committing to a default objective in the actual implementation.

## Sources

- https://riskfolio-lib.readthedocs.io/en/latest/ (fetched during this session)
- https://www.portfoliovisualizer.com/efficient-frontier
- https://www.portfoliovisualizer.com/optimize-portfolio
- https://www.portfoliovisualizer.com/black-litterman-model (fetch blocked, HTTP 403)
- https://www.portfoliovisualizer.com/rolling-optimization
- https://github.com/nutdnuy/AssetManagementToolkit (user-supplied)
- Michaud, R. (1989), "The Markowitz Optimization Enigma: Is 'Optimized' Optimal?"
  (via SSRN abstract: "Estimation Error and Portfolio Optimization: A Resampling
  Solution")
- https://breakingdownfinance.com/finance-topics/finance-basics/criticisms-of-mean-variance-optimization/
- https://blog.quantinsti.com/walk-forward-optimization-introduction/

Full findings table with per-claim confidence levels: see the research-synthesizer
output from this session (not copied verbatim here to keep this doc action-oriented).
