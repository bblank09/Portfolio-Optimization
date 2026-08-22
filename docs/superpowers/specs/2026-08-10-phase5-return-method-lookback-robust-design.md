# Phase 5 sub-project 5: Return-Method Completion + Rolling Lookback + Robust Optimization — Design

Status: **implemented (updated 2026-08-17).** This is the historical design record for the fifth of an expanded set of ordered
Phase 5 sub-projects. Sub-projects 1 (backend optimizer core), 2 (rolling
out-of-sample evaluator), 3 (comparison features), and 4 (portfolio
constraint completion) are implemented in the current codebase; repository
merge state is tracked separately. This sub-project
merges what was originally planned as two separate sub-projects (5 and 6)
into one, per explicit decision — one spec, one implementation plan.

## Why this sub-project exists

Continuing the field-by-field audit of `OptimizeRequest`/`OptimizeConstraints`
fields the real backend never reads, three more gaps close here:

1. **`returnMethod: "capm_implied"`** — a UI-selectable expected-return
   estimation method the backend has always silently ignored, falling back
   to historical mean regardless of selection (except when `goal ==
   "black_litterman"`, which has its own separate BL-posterior path).
2. **`lookbackPeriodMonths`** — a field that has existed in the schema since
   before sub-project 2, described in the UI's own copy ("re-validated every
   [frequency] on a [N]-month lookback"), but never actually read anywhere.
   Sub-project 2 built the rolling evaluator as expanding-window-only
   because, at design time, this gap had not yet been discovered; it is
   closed here.
3. **`robustOptimization: bool`** — a checkbox that does nothing server-side.
   Confirmed via live research against the real PortfolioVisualizer tool
   (not assumed) that this maps to a genuine "Robust Optimization: Yes/No"
   toggle using Monte Carlo resampling (Michaud-style) to dampen estimation
   error — not riskfolio-lib's own Worst-Case mean-variance model, which is
   a different technique entirely.

## Scope

**In scope:** `returnMethod="capm_implied"` (backend), a new
`rollingWindowMode` request field + trailing-window support in the rolling
evaluator, `robustOptimization` (backend, main-solve-only, Monte Carlo
resampling).

**Out of scope:** any frontend change (a final sub-project, once every
backend gap is closed); robust optimization applied to the rolling
evaluator or the comparison portfolio (explicit decision — main solve
only, to avoid a resample × fold multiplication of solve cost);
`returnMethod` values other than `historical_mean` (already the default)
and `capm_implied` (`black_litterman_posterior` already has its own
dedicated path via `goal="black_litterman"`, not this field).

## 1. Return-Method: CAPM-Implied

`inputs.build_mu_sigma` gains a new branch: when `request.return_method ==
"capm_implied"` AND `request.goal.value != "black_litterman"` (which has
its own, separate BL-posterior computation already), `mu` is computed via
the EXISTING `black_litterman.compute_equilibrium_returns(sigma,
risk_aversion, market_weights)` (reused as-is, no new formula) instead of
the historical-mean branch. Since this return method can be selected
independently of Black-Litterman (no `blackLitterman` request block
required), `risk_aversion` and `market_weights` use standard defaults —
`risk_aversion=2.5` (a commonly-cited default in the Black-Litterman
literature, consistent with He & Litterman's own worked examples) and
equal-weight `market_weights` across the request's funds — per decision,
rather than requiring Black-Litterman inputs to be present.

## 2. Rolling Lookback Mode

New field `OptimizeConstraints.rolling_window_mode:
Literal["expanding","trailing"]`, defaulting to `"expanding"` — every
existing request continues to behave exactly as sub-project 2 built it,
with no behavior change for the default case. When `"trailing"`,
`rolling.build_fold_schedule` derives each fold's training window as a
FIXED-length window of `request.constraints.lookback_period_months`
months immediately preceding the fold's test period, sliding forward each
fold, instead of always starting at `index[0]` and growing. Calendar-period
fold boundaries (monthly/quarterly/annually, per
`optimization_frequency`) stay exactly as sub-project 2 built them — only
the training window's START point changes per mode; the schedule's shape
(one row per fold, `train_end`/`test_start`/`test_end`) is otherwise
unchanged, so `run_rolling_evaluation`'s consumption of `FoldSpec` doesn't
need to change, only how each `FoldSpec.train_end`'s WINDOW gets sliced
(`returns.loc[fold.train_start:fold.train_end]` instead of
`returns.loc[:fold.train_end]` — `FoldSpec` gains a `train_start` field,
`None`/unused in expanding mode, set in trailing mode).

## 3. Robust Optimization

`request.constraints.robust_optimization: bool` (exists, currently a
no-op) becomes real, applied ONLY to the main solve (per decision — not
the rolling evaluator's per-fold solves, not the comparison portfolio's
solve, to avoid a resample × fold multiplication of solve cost). New
module `backend/app/optimizer/robust.py`:

`robust.resample_and_solve(request, mu, sigma, returns) -> tuple[dict[str, float], str | None]`

1. Bootstrap-resample `returns`' rows (with replacement, same row count as
   the original panel) 500 times (per decision — the standard Michaud
   resampling count cited in the literature and matching PortfolioVisualizer's
   own real tool).
2. For each resample: recompute `mu`/`sigma` from the resampled panel
   (reusing the SAME covariance/return-estimation logic
   `inputs.build_mu_sigma` already implements — no new estimation
   formula), then solve via the existing `solvers.solve_for_goal` with the
   request's actual goal.
3. A resample whose solve fails (`ValueError`/`RuntimeError`) is skipped,
   not fatal — consistent with this project's established
   non-blocking-secondary-computation pattern.
4. Average the WEIGHTS (not the mu/sigma) across every successfully-solved
   resample — this is the Michaud resampling method's defining step: the
   final portfolio is the average allocation across many perturbed solves,
   which is what dampens estimation-error sensitivity.
5. If fewer than half (250) of the 500 resamples solved successfully,
   fall back to the single-shot (non-resampled) solve on the ORIGINAL
   `mu`/`sigma`, and set the new `robustOptimizationNote` field explaining
   the fallback. Otherwise, the resampled-average weights ARE the final
   `optimalWeights`, and `robustOptimizationNote` states how many
   resamples succeeded (e.g. "Robust optimization: averaged 487 of 500
   resamples.").
6. `robustOptimizationNote` is a NEW, separate `OptimizeResult` field —
   NOT a reuse of the existing `robustNote` field (which sub-project 2
   already established as meaning "rolling-validation caveats"; a third,
   different meaning colliding into that field is exactly what this
   project's one-meaning-per-field rule exists to prevent).

**Performance note (explicit, not a blocking decision for this spec):**
500 sequential re-solves per robust-optimization-enabled request is a
real, not-yet-measured cost. Per decision, the implementation plan's
first robust-optimization task must measure real wall-clock time against
the committed NAV cache before the rest of the feature is considered
done — if it proves unreasonably slow (multi-second to unusable request
latency), that becomes a resample-count or architecture question to
raise back to the user, not something to guess about in this spec.

## Error Handling

- Return-method: no new error path — `capm_implied` reuses
  `compute_equilibrium_returns`, which has no failure mode of its own
  beyond what `build_mu_sigma`'s existing paths already handle.
- Rolling lookback: `"trailing"` mode with a `lookbackPeriodMonths` longer
  than the available history before a fold's test period is handled the
  same way sub-project 2 already handles "not enough training
  observations" — that fold is dropped, not fatal, same
  `INSUFFICIENT_ROLLING_HISTORY` threshold logic applies to the
  (now possibly shorter, fixed-length) training slice.
- Robust optimization: never a hard error for the whole request — a
  fully-failed resampling run degrades to the single-shot solve with an
  explanatory note, per the design above.

## Testing

- Unit test for CAPM-implied mu matching a hand-computed `δΣw_mkt` value
  on a synthetic 2-3 fund case; integration test against the real NAV
  cache confirming `capm_implied` produces a DIFFERENT mu than
  `historical_mean` for the same request (proving it's genuinely wired,
  not silently falling through to the old path).
- Unit tests for `build_fold_schedule`'s trailing-window boundaries
  (fixed-length window sliding forward, verified against hand-computed
  expected boundaries for a known date range/lookback combination);
  integration test against the real cache confirming `"expanding"` mode's
  behavior is byte-identical to before this sub-project (a real
  regression guard, not just a new-feature test).
- Unit test for `resample_and_solve`'s averaging logic against a
  synthetic case with a known expected distribution; integration test
  against the real cache measuring and logging real wall-clock time (the
  measurement decision above) and confirming the fallback path triggers
  correctly when resamples are made to fail (e.g. via a monkeypatched
  solver that fails >50% of the time).
- Extend the 112-case smoke matrix with `robust_optimization=True` and
  `rolling_window_mode="trailing"` variants to confirm both features
  don't break any of the 7 goals × 4 risk measures × 4 compareAgainst
  combinations — the same "would this smoke test have caught the bug" bar
  every prior sub-project's final review has applied.
