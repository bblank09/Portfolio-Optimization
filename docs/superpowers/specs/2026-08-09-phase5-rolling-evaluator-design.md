# Phase 5 sub-project 2: Rolling Out-of-Sample Evaluator — Design

Status: **approved, not yet implemented.** Second of three ordered sub-projects in Phase
5 (backend optimizer core → **rolling out-of-sample evaluator** → frontend integration).
Sub-project 1 (`backend/app/optimizer/`: real riskfolio-lib solvers for all 7
objectives, frontier, diagnostics, Black-Litterman, `POST /api/optimize`) is complete
and merged to `main`.

## Purpose

`docs/optimization-assumptions.md`'s decided methodology pairs every "optimal weights"
result with an out-of-sample rolling-window backtest, not just an in-sample point:
"re-optimize on a trailing window, test on the next unseen period, repeat forward" —
mirroring PortfolioVisualizer's rolling-optimization tool. The frontend's
`OptimizeResult.rolling: RollingFold[]` field and `OptimizeConstraints.optimizationFrequency`
request field already exist in `frontend/src/types/optimize.ts` and
`backend/app/domain/optimize_schemas.py` for exactly this purpose, but sub-project 1's
`service.run_optimize` never populates `rolling` with anything real — it stays whatever
the caller passed (empty, in practice, since the mock is what fills it today). This
sub-project makes that field real.

## Scope

**In scope:** walk-forward re-optimization and out-of-sample scoring for a single
`/api/optimize` request, across all 7 objectives (mean-variance ×4, risk parity, HRP,
Black-Litterman), synchronously in the same request/response cycle.

**Out of scope:** any frontend change (sub-project 3); a separate endpoint or background
job for rolling evaluation; changing the rolling-fold frontend contract shape
(`periodLabel`/`realizedReturnPct`/`realizedVolatilityPct`/`realizedSharpe` stays as
defined); a rolling/trailing (fixed-lookback) window mode — only expanding windows.

## Architecture

Same endpoint, synchronous. No new route, no job queue, no polling. `service.run_optimize`
gains one more step after its existing full-history solve: build the fold schedule from
the request's real testable range and `optimizationFrequency`, then for each fold, re-run
the same per-goal solve path sub-project 1 already built
(`build_returns_panel` → `build_mu_sigma` → `solve_mean_variance` /
`solve_risk_parity` / `solve_hrp` / BL blend), sliced to that fold's training window
instead of the full range, then score the resulting weights against the fold's held-out
test window using `backend/app/engine/metrics.py`'s real return/volatility/Sharpe
functions — never re-derived math.

New module: `backend/app/optimizer/rolling.py`, matching the existing "orchestrator +
pure functions per concern" shape of the rest of `optimizer/`:

- `build_fold_schedule(request, testable_range) -> list[FoldSpec]` — pure function,
  no I/O, no solver calls. Takes the real testable date range (from the same
  `align_nav_panel`-backed logic sub-project 1's `inputs.py` already uses) and the
  request's `optimization_frequency`, returns an ordered list of
  `(train_start, train_end, test_start, test_end)` tuples.
- `run_rolling_evaluation(request, testable_range) -> tuple[list[RollingFold], str | None]`
  — calls `build_fold_schedule`, then for each fold: slices `build_returns_panel`'s
  output to `[train_start, train_end]`, runs `build_mu_sigma` + the goal's solve
  function on that slice, applies the resulting weights to the `[test_start, test_end]`
  return series, and scores it via `engine/metrics.py`. Returns the fold list (only
  successful folds) plus an optional note string for `robustNote` describing any
  skipped folds.
- `service.py` calls `run_rolling_evaluation` once, after its existing single-shot
  solve, and assigns the two return values to `OptimizeResult.rolling` and
  `OptimizeResult.robustNote`.

## Data Flow & Fold Construction

1. **Expanding window**: every fold's training window starts at the testable range's
   earliest date; each fold's training-window end (and the following test window) steps
   forward by one `optimizationFrequency` unit (monthly/quarterly/annually). This is the
   standard walk-forward pattern this project's own methodology doc specifies — not a
   fixed-length rolling/trailing lookback (out of scope, no lookback-length parameter
   exists anywhere in this project yet).
2. **Fold count and test-window length are derived, not fixed**: replacing the
   frontend mock's hardcoded 12/8/5-fold counts, the real fold count is
   `floor((testable_range_end - testable_range_start) / frequency_step) - 1` (minus one
   because the first window is training-only, with no preceding period to have been
   "out of sample" against). The last fold's test window runs to the testable range's
   end even if that's a partial period.
3. **Minimum training window**: `inputs.py` only rejects an empty/all-NaN window today,
   not one that's merely too short for a stable covariance estimate — no such floor
   exists yet to reuse. This sub-project introduces a new, fixed floor
   (covariance estimation needs enough rows relative to fund count) and drops any fold
   whose training window falls short of it before attempting a solve. If the testable
   range can't produce at least 2 folds meeting that floor at the selected frequency,
   raise `ValueError("INSUFFICIENT_ROLLING_HISTORY")` (new `ErrorCode`, same raise-bare-
   name convention `inputs.py`/`solvers.py` already use), which `optimize.py`'s existing
   dynamic `getattr(ErrorCode, ...)` lookup already resolves correctly with no route
   change needed.
4. **Per fold**: re-run the exact single-goal solve path from sub-project 1 on the
   training-window slice → get weights → apply those weights to the *test*-window return
   series (buy-and-hold within the test window, no interim rebalancing — rebalancing
   only happens at the next fold boundary, which is what `optimizationFrequency` already
   means per its existing docstring) → score realized return/volatility/Sharpe via
   `engine/metrics.py` → emit one `RollingFold`.
5. **All 7 objectives** go through this uniformly, including Black-Litterman — its
   equilibrium returns and posterior blend are recomputed from scratch on each fold's
   own training-window mu/Sigma (using the same `BlackLittermanInputs`/views from the
   request, replayed against each fold's own equilibrium baseline), exactly as a live
   single-shot BL request would compute them, just repeated per fold.

## Error Handling

- **`INSUFFICIENT_ROLLING_HISTORY`** (new `ErrorCode`): testable range too short for
  ≥2 folds at the selected frequency. Same 422-family treatment as sub-project 1's other
  input-validation errors, via the existing dynamic `ValueError`-name lookup in
  `optimize.py` — no route code change needed, only the new enum member.
- **A single fold's solve failing** (e.g. `SOLVER_NON_CONVERGENCE` on a thin training
  window, even though the full-history solve and other folds succeeded) does **not**
  fail the request. That fold is dropped from the returned `rolling[]` list, and
  `run_rolling_evaluation` returns a note describing how many folds were skipped and why
  (e.g. "Rolling validation: 9 of 12 folds converged; 3 skipped due to solver
  non-convergence on thin training windows"). `service.py` assigns this note to
  `OptimizeResult.robustNote` — a field that exists today and is always `null` from
  sub-project 1, so this gives it its first real use. If ALL folds fail (0 successful),
  `rolling` is an empty list and `robustNote` explains that rolling validation could not
  produce any result, but the main (full-history) solve result is still returned
  successfully — a rolling-evaluation failure never blocks the primary weights result.

## Testing

- **Unit tests for `build_fold_schedule`**: fold boundaries, derived count, expanding-
  window growth, and the last-fold partial-period behavior, against synthetic date
  ranges — no solver, no NAV cache involved.
- **Integration tests for `run_rolling_evaluation`**: against the real NAV cache fixture
  already used by sub-project 1's tests. Assert: fold count matches the derived
  expectation for a known date range/frequency; realized stats come from real
  `engine/metrics.py` calls on the actual test-window return series (verified against
  hand-computed expected values on the fixture, not just "a number came back" — this is
  exactly the class of bug the final review caught in sub-project 1's
  `performanceSummary`); a deliberately-thin fixture produces the skip-and-note behavior
  rather than a hard failure; a testable range too short for 2 folds raises
  `INSUFFICIENT_ROLLING_HISTORY`.
- **Smoke coverage**: extend sub-project 1's enum-driven 7-goal × 4-risk-measure smoke
  matrix (`test_optimizer_smoke_matrix.py`) to also assert `rolling` is non-empty (or
  correctly empty-with-note) for each combination against the standard fixture, the same
  pattern that caught two Critical cross-module bugs in sub-project 1's final review.

## Open items carried forward (not blocking, noted for implementation)

- Black-Litterman's per-fold equilibrium recomputation reuses sub-project 1's
  `compute_equilibrium_returns`/`blend_posterior` as-is; no new BL-specific rolling logic
  is being designed here beyond "call the existing functions per fold."
- Performance cost: an expanding-window monthly cadence over an ~11-year fund history
  (per `docs/optimization-assumptions.md`'s universe-size finding) could mean ~130+
  folds in the worst case. No explicit fold-count cap is being added in this design;
  if real-fixture testing during implementation shows response times become
  unreasonable, that's a fold-count-cap or frequency-floor decision for the
  implementation plan to flag back, not something to guess at now.
