# Optimization Assumptions & Methodology

Status: **implemented decision record (updated 2026-08-17).** This document began as
the Phase 1–3 design output of forking the project from `Backtest Portfolio Webull:
SEC OPENAI`. The implementation now lives in `backend/app/optimizer/` and
`frontend/src/`; sections below remain the rationale and assumptions, while the
code and tests are the source of truth for current behavior.

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
FastAPI. Its code was read line-by-line during the research pass; it remains a reference
and is not imported by the production optimizer.

## Default objective (decision, with rationale)

**Design recommendation:** prefer Black-Litterman or a shrinkage-covariance
mean-variance objective over naive mean-variance, and pair every "optimal weights"
result with an out-of-sample rolling-window check rather than showing only an
in-sample efficient-frontier point. The current UI intentionally keeps the
PortfolioVisualizer-style defaults from `docs/mock-ui-spec.md` (Max Sharpe,
historical mean, sample covariance) for transparency and allows the user to switch
to Black-Litterman or shrinkage explicitly; this is a documented product trade-off,
not an undocumented implementation mismatch.

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

## Contract decisions enforced by the implementation

- `black_litterman_posterior` is valid only with the `black_litterman` objective;
  the Black-Litterman objective requires that return method. The frontend disables
  the incompatible option and the Pydantic request schema rejects direct API calls
  that do not satisfy the same rule.
- The testable-date-range endpoint accepts `frequency=daily|weekly|monthly` and
  uses the same alignment/completeness rules as the optimizer. Daily windows also
  require consecutive business-day observations, so a missing weekday cannot be
  hidden by a monthly preflight range.
- When every expected return is at or below the requested risk-free rate, direct
  riskfolio Sharpe optimization has a degenerate negative-excess branch. The solver
  therefore selects the highest request-risk-adjusted Sharpe point from the same
  constrained efficient-frontier sweep; if that sweep cannot produce a feasible
  point, the request fails as `SOLVER_NON_CONVERGENCE` instead of returning a
  numerically arbitrary interior allocation.

## Results/output shape to design toward

Based on standard portfolio-optimization tooling (riskfolio-lib, PortfolioVisualizer):
efficient frontier chart, optimal weights table, expected return/volatility/Sharpe,
per-asset risk-contribution breakdown, and a rolling out-of-sample performance chart —
these shape the current optimizer UI's "Results" tab design.

## Gaps — closure status (updated after a follow-up research pass)

Four gaps were originally flagged; all four are now closed (full findings in the
research-synthesizer output — see the file linked at the bottom):

1. **Academic sweep** — was skipped in the first pass. Closed via OpenAlex (Semantic
   Scholar rate-limited/no API key): confirmed Ledoit & Wolf (2003) shrinkage
   covariance as the standard academic fix for estimation error, and upgraded Michaud
   & Michaud's resampling paper from an SSRN-abstract citation to a verified
   peer-reviewed reference (85 citations).
2. **Black-Litterman mechanics** — the implementation and formula reference now record
   the chosen equilibrium anchor, relative-view convention, tau/Omega approximation,
   and numerical linear-solve behavior. The UI labels its client-side equilibrium
   values as illustrative; production values are computed server-side and returned
   in the result.
3. **riskfolio-lib vs. PyPortfolioOpt** — now compared, not assumed: riskfolio-lib has
   26 risk measures vs. PyPortfolioOpt's variance-centric scope, plus native
   constraint tooling and HRP/HERC that PyPortfolioOpt lacks. Confirms the choice on a
   comparative basis.
4. **Fund universe size** — checked directly:
   `data/sec/mvp_fund_universe.csv` has ~2,000 funds, longest history ~135-139 months
   (~11.3 years). This *reverses* the original concern — the universe isn't too thin
   for covariance estimation, it's too *wide* to optimize over directly. **Design
   implication for the implementation: the UI provides a fund shortlist/pre-selection
   step and the optimizer request schema caps the selected set at 30 funds; optimizing
   across all ~2,000 funds simultaneously is neither standard practice nor
   computationally sane.**
   This is a concrete requirement enforced by the current contract.

`AssetManagementToolkit`'s code has now been read line-by-line (cloned + its own test
suite run: 314 passed, 0 failed). Findings:

- **No LICENSE file, no license statement anywhere in the repo.** Under default
  copyright law that would normally mean all-rights-reserved. **Resolved:** the
  project owner (this project's user) confirmed directly in chat that they are the
  author/rights-holder of `AssetManagementToolkit` and has given explicit permission
  to use its code in full. Direct code reuse (not just running it as a test-time
  oracle) is therefore permitted going forward. The repo itself still has no LICENSE
  file committed — worth adding one there for the record, but not a blocker here.
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

**Updated stance on reuse (permission confirmed):** with the license question
resolved, the earlier "oracle only, not a dependency" restriction is lifted. Its
Black-Litterman, Markowitz, and HRP/HERC implementations are still recommended
*against* as the primary engine (riskfolio-lib remains the core, per the comparative
decision above — more risk measures, native constraint tooling), but `shrink_covariance`,
`walk_forward`, and other utility modules can now be imported/adapted directly where
useful in Phase 5, instead of being reimplemented from scratch.

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
