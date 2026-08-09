# Phase 5, Sub-project 1: Backend Optimizer Core + API — Design

## Stated goal

Replace the frontend's Phase 4 mock (`frontend/src/lib/mockOptimize.ts`) with a real
backend that wraps riskfolio-lib and computes actual portfolio optimizations against
the cached SEC NAV panel, exposed as `POST /api/optimize`. This is sub-project 1 of 3
in Phase 5 (backend optimizer core + API → rolling out-of-sample evaluator → frontend
integration), scoped and ordered by dependency: sub-projects 2 and 3 build on this one
and are out of scope for this spec.

## Current state

- `frontend/src/lib/mockOptimize.ts` deterministically fabricates every number in
  `OptimizeResult` from the request alone — no real return/covariance estimation, no
  real solver, no real efficient frontier. It has known, catalogued math defects
  (no covariance in risk calc, wrong risk-contribution formula, HRP/risk-parity/GMV
  all using the same inverse-vol heuristic, Black-Litterman's Π not from reverse
  optimization, relative BL views only touching one asset) — all deliberate, disclosed
  mock shortcuts, not bugs to port forward.
- `types/optimize.ts` (`OptimizeRequest`/`OptimizeResult`) already encodes a full
  field-by-field contract, refined over many rounds against PortfolioVisualizer's live
  tool and this project's own `docs/optimization-assumptions.md` methodology
  decisions. This spec treats that TypeScript contract as the source of truth for the
  Pydantic schema — not something to redesign from scratch.
- `backend/app/optimizer/` does not exist yet. `riskfolio-lib` and `cvxpy` are not yet
  project dependencies (confirmed via `pyproject.toml`).
- `backend/app/engine/`, `backend/app/sec/`, `backend/app/data/quality.py` are mature,
  tested, and must be reused where they already solve a problem this sub-project also
  faces (NAV panel loading/alignment, gap detection) — CLAUDE.md explicitly forbids
  deleting or bypassing this code.
- The sibling backtester's `POST /api/backtests` (`backend/app/api/backtests.py`,
  `domain/schemas.py`, `core/errors.py` + `domain/enums.py: ErrorCode`) is the
  established pattern for how this project turns a validated request into a computed,
  error-handled response — this spec follows that pattern rather than inventing a new
  one.

## Target state

- `POST /api/optimize` accepts a request shaped like `OptimizeRequest` (Pydantic
  mirror, hand-kept in sync the same way `types/backtest.ts` already mirrors
  `domain/schemas.py` by convention in this codebase) and returns a real
  `OptimizeResult` computed by riskfolio-lib against the cached NAV panel — no
  synthetic numbers anywhere in the response.
- All 7 objectives from the mock UI resolve to real riskfolio-lib calls: Maximize
  Sharpe, Minimize Volatility (at a target return), Max Return/Target Volatility,
  Minimize Variance (GMV), Risk Parity, Hierarchical Risk Parity, Black-Litterman.
- All 4 risk measures (Standard Deviation, Semi-Variance, CVaR, CDaR) are real
  riskfolio-lib risk measures (`rm` codes), each solvable with the free CLARABEL
  solver — confirmed via riskfolio-lib's own solver-requirement table (all 4 need only
  LP/QP/SOCP, no EXP/POW measures in this project's scope, so no MOSEK/GUROBI
  dependency).
- The efficient frontier, GMV point, and tangency point are real
  `efficient_frontier()` output, not interpolated/fabricated — the frontier's own
  points are internally consistent with the weights that produced them (closes the
  mock's most-cited math defect).
- Black-Litterman's equilibrium returns (Π) come from real reverse optimization
  (`blacklitterman_stats`), and a relative view ("A will outperform B by X%") affects
  both assets it names, not just one.
- Binding-constraint diagnostics reflect what the solver actually did, not what was
  merely configured (this project already fixed the equivalent frontend-only version
  of this bug for the mock's turnover check — this sub-project must not reintroduce
  the same class of bug at the backend layer).
- `GET /api/funds/testable-range`'s existing gap-aware validation becomes the backend
  safety net for time-period feasibility that the frontend-only mock never had (the
  session's own testable-range clamp fix patched the client-side symptom; this
  sub-project adds the server-side check that makes it actually safe, matching how the
  sibling backtester's `POST /api/backtests` already validates this).
- Mock is fully replaced, not kept as a fallback (per explicit decision) — sub-project
  3 (frontend integration, out of scope here) removes `mockOptimize.ts`'s call site.

## Decisions carried from brainstorming

- **Rollout**: replace the mock outright when the real backend ships (no dual
  mock/real mode, no feature flag). Simpler, no long-lived parallel-maintenance
  burden.
- **Solver**: CVXPY's default, CLARABEL — free, and sufficient for every risk measure
  this project exposes.
- **Module shape**: orchestrator + pure functions per concern, mirroring the existing
  `engine/backtest.py` pattern in this codebase, not a per-objective strategy-class
  hierarchy (7 classes for 7 objectives that mostly differ by a couple of riskfolio-lib
  kwargs would be over-engineering for this scope).

## Architecture

```
backend/app/optimizer/
├── __init__.py
├── service.py          # run_optimize(request) -> OptimizeResult -- the only
│                        # entry point the API route calls
├── inputs.py            # builds mu (expected return vector) and Sigma (covariance
│                        # matrix) from the aligned NAV panel, or from the user's
│                        # expectedReturnOverrides/volatilityOverrides/
│                        # correlationOverrides when useHistorical* is false
├── solvers.py            # one function per objective, each wrapping a specific
│                        # rp.Portfolio.optimization()/rp_optimization() call, or
│                        # rp.HCPortfolio.optimization() for HRP
├── black_litterman.py   # Pi (equilibrium, via blacklitterman_stats) + posterior
│                        # blending with the user's views -- feeds its posterior mu
│                        # back into solvers.py's optimization call when
│                        # goal == "black_litterman"
├── frontier.py           # wraps efficient_frontier(); extracts the GMV point
│                        # (leftmost) and tangency point (max Sharpe) from its
│                        # actual output, not a separate heuristic
├── diagnostics.py        # binding-constraint detection (compares solved weights
│                        # against the bounds that were actually set) and
│                        # feasibility pre-checks
└── report.py             # assembles the final OptimizeResult payload from the
                          # above modules' outputs
```

`service.py` is the only module the API route (`backend/app/api/optimize.py`, new)
imports from `optimizer/` — every other module is an internal collaborator, not a
public entry point. This keeps the same "thin route, real work lives in a dedicated
package" shape `api/backtests.py` → `engine/backtest.py` already establishes.

## Data flow

```
POST /api/optimize (OptimizeRequest schema)
  -> inputs.py:
       - load + align the NAV panel for request.funds via sec/cache.py +
         data/quality.py (reused, not reimplemented)
       - compute mu/Sigma per request.covarianceMethod (sample/shrinkage/EWMA),
         honoring per-fund expectedReturnOverrides/volatilityOverrides/
         correlationOverrides when the corresponding useHistorical* flag is false
  -> [if request.goal == "black_litterman"] black_litterman.py:
       - Pi = blacklitterman_stats(...) (real reverse optimization, not mu * 0.8)
       - blend Pi with request.blackLitterman.views (both assets of a relative view
         affected, matching Idzorek's method already cited in
         docs/optimization-assumptions.md)
       - posterior mu replaces inputs.py's mu for the optimization call below
  -> solvers.py: dispatch on request.goal
       - max_sharpe / min_volatility / max_return_target_vol / min_variance ->
         rp.Portfolio.optimization(obj=..., rm=request.riskMeasure's rm code, ...)
       - risk_parity -> rp.Portfolio.rp_optimization(...)
       - hrp -> rp.HCPortfolio.optimization(...)
  -> frontier.py: rp.Portfolio.efficient_frontier(rm=..., points=24) -- same point
     count as the mock, for continuity with the existing Frontier tab chart
  -> diagnostics.py: compare solved weights against fundBounds/constraints/
     maxTurnoverPct/maxTrackingErrorPct to report which ones actually bound
  -> report.py: assemble OptimizeResult (same shape frontend/src/types/optimize.ts
     already defines)
```

## Error handling

Extends the existing `AppHTTPException` (`core/errors.py`) + `ErrorCode`
(`domain/enums.py`) pattern rather than inventing a parallel one:

- `INSUFFICIENT_NAV_HISTORY` — reused as-is from the backtester's own error code;
  same meaning (requested time period isn't fully covered by cached NAV data for
  every selected fund).
- `SOLVER_NON_CONVERGENCE` (new) — CVXPY returns a non-optimal status that isn't
  outright infeasible (numerical failure, timeout).
- `INFEASIBLE_CONSTRAINTS` (new) — CVXPY reports the problem is genuinely infeasible
  (replaces the mock's heuristic pre-checks in `evaluateFeasibility` with the
  solver's own authoritative answer).
- `INDEFINITE_CORRELATION_MATRIX` (new) — fires when `useHistoricalCorrelations` is
  false and the user's entered pairwise overrides don't form a positive
  semi-definite matrix (flagged as a real gap during this project's earlier UI
  review; the frontend's correlation-matrix editor has no such validation today, and
  this is the first point in the system where checking it is possible).

## Testing

- **Unit** (`backend/tests/test_optimizer_solvers.py`, new): each `solvers.py`
  function against a small closed-form-checkable case (e.g. 2-asset GMV has a known
  analytical weight split) so a regression is caught without needing real market
  data.
- **Integration** (`backend/tests/test_optimizer_service.py`, new): full
  `run_optimize()` request against the real cached NAV parquet, following the same
  "verify against real cached data, not just synthetic fixtures" rule CLAUDE.md
  states for `engine/`-adjacent code (this module reads the same panel).
- **Property**: for every feasible request, solved weights sum to 100% within
  floating-point tolerance, and every weight respects its own bound.

## Out of scope for this sub-project

- Rolling out-of-sample evaluator (sub-project 2 — reuses `backend/app/engine/`,
  scheduled after this one).
- Frontend call-site changes, `mockOptimize.ts` removal, shareable-link redesign
  (sub-project 3).
- Turnover- and tracking-error-constrained optimization as true solver-level
  constraints (riskfolio-lib supports this per its own docs — "Portfolio optimization
  with constraints on tracking error and turnover" — but wiring it in is deferred
  to whichever sub-project actually exercises `maxTurnoverPct`/`maxTrackingErrorPct`
  end-to-end; this sub-project's `diagnostics.py` only *reports* on them using
  post-hoc comparison, matching the mock's existing scope for those two fields).
- Any UI change. This is backend-only.
