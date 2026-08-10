# Phase 5 sub-project 3: Comparison Features — Design

Status: **approved, not yet implemented.** Third of an expanded set of ordered
Phase 5 sub-projects. Sub-project 1 (backend optimizer core) and sub-project 2
(rolling out-of-sample evaluator) are complete and merged to `main`.

## Why this sub-project exists

An audit of every `OptimizeRequest`/`OptimizeConstraints` field against the
real backend (`backend/app/optimizer/*.py`) found several UI-selectable
fields the backend never reads at all — the mock (`mockOptimize.ts`)
implements every field because it's entirely fabricated, but sub-project 1's
scope only covered the 7 objectives + frontier + diagnostics + Black-Litterman,
not every Assumptions-step control. `compareAgainst` and `benchmarkProjId`
are two of these: selecting either currently does nothing — the real API
always returns `compareWeights: null` and `benchmarkComparison: null`, while
the UI (`OptimizeResults.tsx`) renders whole sections keyed on those fields.
This sub-project makes both fields real. (The remaining gaps — group
constraints, max holdings, return-method, rolling lookback, robust
optimization — are separate, later sub-projects; not this one's scope.)

## Scope

**In scope:** `compareAgainst` (all 6 enum values: `none`/`equal_weighted`/
`max_sharpe`/`inverse_volatility`/`risk_parity`/`current`) populating
`OptimizeResult.compareWeights`; `benchmarkProjId` populating
`OptimizeResult.benchmarkComparison`; a new `compareNote` field for
comparison-specific caveats.

**Out of scope:** group/asset constraints, max holdings, return-method
(CAPM-implied), rolling lookback mode, robust optimization (all separate,
later sub-projects); any frontend change (a final sub-project, after every
backend gap is closed).

## Architecture

Same endpoint, synchronous (per decision — matches sub-project 2's
precedent). New module `backend/app/optimizer/comparison.py`, same
orchestrator + pure functions shape as the rest of `optimizer/`:

- `build_comparison_weights(request, mu, sigma, returns) -> dict[str, float] | None`
  — dispatches on `request.constraints.compare_against`, called once from
  `service.run_optimize` after the main solve.
- `build_benchmark_comparison(request, optimal_weights, returns) -> BenchmarkComparison | None`
  — loads the benchmark fund's own NAV series and scores it against the
  optimized portfolio's realized return series, called once from the same
  place.

## `compareAgainst` — per-value computation

All five non-`none` values respect the same constraints as the main solve
(fund bounds, long-only) — per decision, an "equal weight" comparison under a
30%-cap constraint is genuinely a constrained equal-weight allocation (30%
capped fund, remainder split across the rest), not an unconstrained textbook
baseline, so the comparison is apples-to-apples with what the user actually
asked the main solve to respect.

- **`equal_weighted`**, **`max_sharpe`**, **`risk_parity`**: reuse
  `solvers.solve_for_goal` with the goal swapped to the corresponding value,
  passing the SAME `mu`/`sigma`/`returns`/`request.constraints` the main solve
  used — no new solving logic, pure reuse of sub-project 1/2's existing
  dispatch.
- **`inverse_volatility`**: new pure function — `w_i = (1/σ_i) / Σ_j(1/σ_j)`
  computed from `sigma`'s diagonal (already available, no new data needed),
  then clamped into the same fund bounds via the existing bounds-clamping
  logic `solvers.py` already has for per-fund bounds (reused, not
  reimplemented) — this formula does not exist anywhere in the backend yet
  and is the one genuinely new piece of math in this sub-project.
- **`current`**: `request.current_weight_pct` directly, no solve. If empty
  (a fresh portfolio with no existing holdings), `compareWeights` is `None`
  — there is nothing to compare against, not an error.

## `benchmarkProjId`

Loads the benchmark fund's own NAV series via the existing
`load_nav_panel`/`align_nav_panel` pipeline (same reuse mandate as every
prior sub-project), sliced to the SAME `time_period` as the main request,
independent of whether the benchmark fund is also one of the optimized
funds. Scores it against the optimized portfolio's own realized return
series (already computed by the main solve path) via
`backend/app/engine/metrics.py`'s real `annualized_return` (for
`excessReturnPct`) and `tracking_error` (for `trackingErrorPct`) — no new
formulas, both already exist and are already used elsewhere in this project.

## Error Handling

- **Benchmark data insufficient** (fund doesn't have NAV coverage for the
  full requested `time_period`) — **hard error, the whole request fails**
  (per decision). New `ErrorCode.BENCHMARK_DATA_UNAVAILABLE`, raised as
  `ValueError("BENCHMARK_DATA_UNAVAILABLE")` — the same bare-name convention
  every prior `ErrorCode` addition in this project uses, resolved by
  `api/optimize.py`'s existing dynamic `getattr(ErrorCode, ...)` lookup with
  no route code change needed.
- **`compareAgainst` solve failure** (e.g. `max_sharpe` infeasible on the
  comparison path even though the main solve succeeded) — **never fails the
  whole request** (same non-blocking-secondary-feature principle
  sub-project 2's final review established for rolling-evaluation failures).
  `compareWeights` is set to `None` and the reason goes into a **new,
  separate field** — `compareNote: string | null` on `OptimizeResult` (per
  decision) — kept distinct from `robustNote` (which already means
  "rolling-validation caveats" as of sub-project 2, and will separately mean
  "robust-optimization confirmation" once sub-project 6 lands; three
  meanings colliding in one string field is not acceptable, per the
  decision that led to this new field).

## Testing

- Unit test for `inverse_volatility`'s formula against a hand-computed
  3-asset case (known volatilities → known expected weights).
- Integration tests against the real NAV cache fixture, covering all 6
  `compareAgainst` values (including `current` both with and without
  existing holdings populated) — verifying `compareWeights` is genuinely
  computed (sums to ~100, respects fund bounds), not a placeholder.
- Integration test for `benchmarkProjId`'s success path (real
  `excessReturnPct`/`trackingErrorPct` cross-checked against a hand
  computation via `engine/metrics.py`'s functions directly, same pattern
  sub-project 2's reviewers used) and its hard-error path (benchmark fund
  with insufficient NAV coverage for the requested window raises
  `BENCHMARK_DATA_UNAVAILABLE`).
- Extend the existing 28-case (7 goals × 4 risk measures) smoke matrix
  (`test_optimizer_smoke_matrix.py`) with an additional assertion:
  requesting a non-`none` `compareAgainst` produces a non-null
  `compareWeights` for every goal/risk-measure combination — the same
  "don't let a weak pass-by-default assertion hide a real regression"
  lesson sub-project 2's final review learned the hard way (its original
  smoke-matrix assertion was too weak to catch a real fabricated-zeros bug).
