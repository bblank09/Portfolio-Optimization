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

## Gaps — closure status (updated after a follow-up research pass)

Four gaps were originally flagged; all four are now closed (full findings in the
research-synthesizer output — see the file linked at the bottom):

1. **Academic sweep** — was skipped in the first pass. Closed via OpenAlex (Semantic
   Scholar rate-limited/no API key): confirmed Ledoit & Wolf (2003) shrinkage
   covariance as the standard academic fix for estimation error, and upgraded Michaud
   & Michaud's resampling paper from an SSRN-abstract citation to a verified
   peer-reviewed reference (85 citations).
2. **Black-Litterman mechanics** — verified against Wikipedia (High confidence on the
   qualitative mechanism: implied equilibrium returns + investor views + confidence →
   posterior return estimate → standard mean-variance optimization). The exact tau/
   Omega formulas are still not sourced from a primary paper — before coding the BL
   view-input UI, pull He & Litterman (1999), "The Intuition Behind Black-Litterman
   Model Portfolios."
3. **riskfolio-lib vs. PyPortfolioOpt** — now compared, not assumed: riskfolio-lib has
   26 risk measures vs. PyPortfolioOpt's variance-centric scope, plus native
   constraint tooling and HRP/HERC that PyPortfolioOpt lacks. Confirms the choice on a
   comparative basis.
4. **Fund universe size** — checked directly:
   `data/sec/mvp_fund_universe.csv` has ~2,000 funds, longest history ~135-139 months
   (~11.3 years). This *reverses* the original concern — the universe isn't too thin
   for covariance estimation, it's too *wide* to optimize over directly. **Design
   implication for Phase 4/5: the UI needs a fund shortlist/pre-selection step (or the
   backend needs a pre-clustering step) before running MVO/BL — optimizing across all
   2,000 funds simultaneously is neither standard practice nor computationally sane.**
   This is a new, concrete requirement this closure pass surfaced.

`AssetManagementToolkit`'s code has now been read line-by-line (cloned + its own test
suite run: 314 passed, 0 failed). Findings:

- **No LICENSE file, no license statement anywhere in the repo.** Under default
  copyright law that means all-rights-reserved — reading and learning from it is fine,
  but **do not copy its source into this project without asking the author
  (github.com/nutdnuy) for explicit permission first.**
- Its Black-Litterman, Markowitz (min-vol/max-Sharpe/GMV/frontier), HRP/HERC, and
  risk-budgeting (ERC/target-risk) implementations are all correct, well-validated,
  and match the mechanisms verified against Wikipedia/riskfolio-lib docs earlier —
  useful as a **correctness oracle** to cross-check riskfolio-lib's numbers in Phase 5
  tests (run it as an installed test-time dependency, not by copying its source).
- Its `shrink_covariance` is a fixed-intensity blend toward constant-correlation, **not**
  Ledoit-Wolf's optimal-shrinkage estimator — don't treat it as "the" shrinkage
  implementation. Use riskfolio-lib's own covariance estimators for the actual engine.
- Its `walk_forward` validator solves a different problem (simulation-model
  calibration, not rolling portfolio-weight re-optimization) — only the
  expanding/rolling fold-splitting *pattern* is reusable, reimplemented from scratch,
  not the code itself.

Full line-by-line findings (per-module, with confidence levels): see the
research-synthesizer output from this session.

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
