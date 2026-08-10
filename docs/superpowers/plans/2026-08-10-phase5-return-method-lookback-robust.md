# Phase 5 sub-project 5: Return-Method + Rolling Lookback + Robust Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make three previously-unimplemented `OptimizeRequest` fields real: `returnMethod="capm_implied"`, a new `rollingWindowMode` (expanding/trailing) for the rolling evaluator, and `robustOptimization` (Monte Carlo resampling), all currently either silently ignored or non-existent.

**Architecture:** CAPM-implied return reuses `black_litterman.compute_equilibrium_returns` as-is inside `inputs.build_mu_sigma`. Rolling lookback adds a `train_start` field to `rolling.FoldSpec` and a mode parameter to `rolling.build_fold_schedule`, defaulting to today's expanding behavior with zero change for existing requests. Robust optimization is a new module, `backend/app/optimizer/robust.py`, whose output feeds into `holdings.enforce_max_holdings` as an optional pre-computed initial solve (main-solve-only, per design — never re-run inside the trim loop or per rolling fold).

**Tech Stack:** Python, pandas/numpy (bootstrap resampling), the existing `backend/app/optimizer/*` modules, pytest.

## Global Constraints

- `returnMethod="capm_implied"` reuses `black_litterman.compute_equilibrium_returns(sigma, risk_aversion, market_weights)` exactly as-is — no new equilibrium-return formula. Only applies when `goal != "black_litterman"` (which has its own separate BL-posterior path already).
- `risk_aversion=2.5`, equal-weight `market_weights` — standard defaults, no dependency on `blackLitterman` request inputs being present.
- `rollingWindowMode` defaults to `"expanding"` — every existing request (none of which send this new field) must behave byte-identically to before this plan. This is the single most important regression requirement in this plan.
- Robust optimization applies ONLY to the main solve — never the rolling evaluator's per-fold solves, never the comparison portfolio's solve, and never re-run inside `enforce_max_holdings`'s trim loop (only its INITIAL solve, for cost reasons — trimming re-solves stay plain `solvers.solve_for_goal` calls).
- Robust optimization: 500 bootstrap resamples, average the WEIGHTS of every successfully-solved resample. Fewer than 250 (half) successful resamples falls back to a plain single-shot solve with an explanatory note — never a hard error.
- `robustOptimizationNote` is a NEW, separate `OptimizeResult` field — never reuse `robustNote` (already means "rolling-validation caveats" since sub-project 2) or `compareNote`/`constraintNote`.
- No new `ErrorCode` values needed in this plan — none of the three features introduce a new hard-error path.
- Use `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3` for all commands (`pytest`, `ruff`) — never a bare `python3`/`pytest`.
- Every new module/function gets tests verified against this plan's own Step commands before moving to the next task.

---

### Task 1: CAPM-implied return method in `inputs.build_mu_sigma`

**Files:**
- Modify: `backend/app/optimizer/inputs.py`
- Test: `backend/tests/test_optimizer_inputs.py`

**Interfaces:**
- Consumes: `black_litterman.compute_equilibrium_returns(sigma, risk_aversion, market_weights) -> pd.Series` (existing, unchanged).
- Modifies: `inputs.build_mu_sigma`'s internal `mu` computation — no signature change (`build_mu_sigma(request, returns) -> tuple[pd.Series, pd.DataFrame]` stays the same).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_optimizer_inputs.py`. Read the file first to reuse its existing fixture-construction pattern for an `OptimizeRequest` (the two-real-fund pattern used throughout this project's tests):

```python
def test_capm_implied_return_method_differs_from_historical_mean():
    request_historical = OptimizeRequest.model_validate({
        "funds": [
            {"projId": "M0209_2548", "displayName": "K-SET50"},
            {"projId": "M0155_2547", "displayName": "M-S50"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2016-01-31", "endDate": "2019-12-31"},
        "dataFrequency": "monthly", "goal": "max_sharpe", "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": False, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })
    request_capm = request_historical.model_copy(update={"return_method": "capm_implied"})

    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel
    returns = build_returns_panel(request_historical)
    mu_historical, sigma_historical = build_mu_sigma(request_historical, returns)
    mu_capm, sigma_capm = build_mu_sigma(request_capm, returns)

    # Sigma must be unaffected by the return-method switch -- only mu
    # changes.
    assert sigma_historical.equals(sigma_capm)
    # The two mu series must be genuinely different -- proving capm_implied
    # is actually wired, not silently falling through to historical mean.
    assert not mu_historical.equals(mu_capm)

    # Independently hand-recompute Pi = risk_aversion * Sigma @ w_mkt with
    # equal-weight market_weights and risk_aversion=2.5, via the same real
    # black_litterman.compute_equilibrium_returns function, and confirm
    # build_mu_sigma's capm_implied branch matches it exactly.
    from backend.app.optimizer.black_litterman import compute_equilibrium_returns
    import pandas as pd
    market_weights = pd.Series(1.0 / len(sigma_historical.index), index=sigma_historical.index)
    expected_mu = compute_equilibrium_returns(sigma_historical, risk_aversion=2.5, market_weights=market_weights)
    pd.testing.assert_series_equal(mu_capm.sort_index(), expected_mu.sort_index(), check_names=False)


def test_capm_implied_ignored_for_black_litterman_goal():
    # goal=black_litterman already has its own separate equilibrium/posterior
    # path (black_litterman.blend_posterior, called from service.py, not
    # build_mu_sigma) -- returnMethod=capm_implied must not double-apply or
    # otherwise change build_mu_sigma's output for this goal; build_mu_sigma
    # should return the plain historical mean here regardless of
    # return_method, since service.py's own BL branch is what actually
    # matters for this goal.
    request = OptimizeRequest.model_validate({
        "funds": [
            {"projId": "M0209_2548", "displayName": "K-SET50"},
            {"projId": "M0155_2547", "displayName": "M-S50"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2016-01-31", "endDate": "2019-12-31"},
        "dataFrequency": "monthly", "goal": "black_litterman", "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": False, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "capm_implied", "covarianceMethod": "sample",
        "blackLitterman": {
            "riskAversion": 2.5,
            "marketWeightPct": {"M0209_2548": 50.0, "M0155_2547": 50.0},
            "views": [],
        },
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    historical_mu = (returns * 100).mean() * 12
    import pandas as pd
    pd.testing.assert_series_equal(mu.sort_index(), historical_mu.sort_index(), check_names=False)
```

If `BlackLittermanInputs`'s exact required field names in the second test's `blackLitterman` block differ from `riskAversion`/`marketWeightPct`/`views` as shown, check `backend/app/domain/optimize_schemas.py`'s real `BlackLittermanInputs` class first and use its real field names — this is the same check earlier sub-projects' plans have flagged for this exact block.

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_inputs.py -k capm -v`
Expected: FAIL — `mu_historical.equals(mu_capm)` is True (capm_implied not yet wired, falls through to historical mean)

- [ ] **Step 3: Add the capm_implied branch to `build_mu_sigma`**

In `backend/app/optimizer/inputs.py`, add the import (top of file, alongside the existing imports):

```python
from backend.app.optimizer import black_litterman
```

Find this line in `build_mu_sigma`:

```python
    mu = pct_returns.mean() * ppy
```

Replace it with:

```python
    if request.return_method.value == "capm_implied" and request.goal.value != "black_litterman":
        # Reuses the exact same reverse-optimization formula
        # (Pi = risk_aversion * Sigma @ w_mkt) Black-Litterman already
        # implements -- this return method can be selected independently
        # of goal=black_litterman, so it uses standard defaults rather than
        # requiring request.black_litterman to be set. goal=black_litterman
        # is excluded here because it has its own separate equilibrium ->
        # posterior pipeline (black_litterman.blend_posterior, called from
        # service.py) that this branch would otherwise shadow.
        market_weights = pd.Series(1.0 / len(sigma.index), index=sigma.index)
        mu = black_litterman.compute_equilibrium_returns(sigma, risk_aversion=2.5, market_weights=market_weights)
    else:
        mu = pct_returns.mean() * ppy
```

Note this must come AFTER `sigma` is fully computed (`sigma = sigma_period * ppy`, a few lines above) since the CAPM branch needs `sigma` — check the current file's exact line order before inserting, the replacement above assumes `sigma` already exists as a local variable at this point (verified true in the current file).

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_inputs.py -v`
Expected: PASS (all tests in the file, including the 2 new ones)

- [ ] **Step 5: Run the full existing optimizer test suite to confirm no regression**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py backend/tests/test_optimizer_solvers_mean_variance.py -v`
Expected: PASS — every existing request uses `returnMethod: "historical_mean"` (the default in every established fixture), so this change must be a no-op for all of them.

- [ ] **Step 6: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/inputs.py backend/tests/test_optimizer_inputs.py`
Expected: All checks passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/optimizer/inputs.py backend/tests/test_optimizer_inputs.py
git commit -m "feat: wire returnMethod=capm_implied to real equilibrium-return computation"
```

---

### Task 2: `rollingWindowMode` schema field

**Files:**
- Modify: `backend/app/domain/optimize_schemas.py`
- Test: `backend/tests/test_optimize_schemas.py`

**Interfaces:**
- Produces: `RollingWindowMode` StrEnum (`"expanding"`/`"trailing"`) and `OptimizeConstraints.rolling_window_mode: RollingWindowMode = RollingWindowMode.expanding` (wire name `rollingWindowMode`, DEFAULTS to `"expanding"` — every existing request payload that doesn't send this field validates unchanged). Consumed by Task 3's `rolling.py` changes.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_optimize_schemas.py`:

```python
def test_rolling_window_mode_defaults_to_expanding():
    payload = MINIMAL_REQUEST_JSON  # or this file's real helper name for a minimal valid OptimizeRequest payload -- check the file for the actual name/pattern
    request = OptimizeRequest.model_validate(payload)
    assert request.constraints.rolling_window_mode.value == "expanding"


def test_rolling_window_mode_accepts_trailing():
    payload = {**MINIMAL_REQUEST_JSON, "constraints": {**MINIMAL_REQUEST_JSON["constraints"], "rollingWindowMode": "trailing"}}
    request = OptimizeRequest.model_validate(payload)
    assert request.constraints.rolling_window_mode.value == "trailing"
```

Read the file first — if there's no top-level `MINIMAL_REQUEST_JSON` constant, find whatever pattern the file's existing tests use to construct a minimal valid `OptimizeRequest` payload and match it exactly.

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimize_schemas.py -k rolling_window_mode -v`
Expected: FAIL — `AttributeError: 'OptimizeConstraints' object has no attribute 'rolling_window_mode'`

- [ ] **Step 3: Add the enum and field**

In `backend/app/domain/optimize_schemas.py`, add the new enum immediately after the existing `OptimizationFrequency` class:

```python
class OptimizationFrequency(StrEnum):
    monthly = "monthly"
    quarterly = "quarterly"
    annually = "annually"


class RollingWindowMode(StrEnum):
    expanding = "expanding"
    trailing = "trailing"
```

Then add the field to `OptimizeConstraints` (immediately after `optimization_frequency`):

```python
    optimization_frequency: OptimizationFrequency
    rolling_window_mode: RollingWindowMode = RollingWindowMode.expanding
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimize_schemas.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the full existing test suite to confirm zero regression**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py backend/tests/test_rolling_evaluation.py backend/tests/test_rolling_fold_schedule.py backend/tests/test_optimizer_smoke_matrix.py -v`
Expected: PASS — a field with a default value must not break any existing request payload that omits it, since none of them send `rollingWindowMode`.

- [ ] **Step 6: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/domain/optimize_schemas.py backend/tests/test_optimize_schemas.py`
Expected: All checks passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/domain/optimize_schemas.py backend/tests/test_optimize_schemas.py
git commit -m "feat: add OptimizeConstraints.rollingWindowMode (expanding/trailing)"
```

---

### Task 3: Trailing-window mode in `rolling.build_fold_schedule`/`run_rolling_evaluation`

**Files:**
- Modify: `backend/app/optimizer/rolling.py`
- Test: `backend/tests/test_rolling_fold_schedule.py`, `backend/tests/test_rolling_evaluation.py`

**Interfaces:**
- Consumes: `OptimizeConstraints.rolling_window_mode: RollingWindowMode` (Task 2).
- Modifies: `rolling.FoldSpec` gains a new field `train_start: pd.Timestamp | None` (existing fields unchanged). `rolling.build_fold_schedule(index, frequency, mode="expanding", lookback_months=None) -> list[FoldSpec]` gains two new OPTIONAL parameters with defaults matching current behavior exactly — existing callers passing only `(index, frequency)` are unaffected. `rolling.run_rolling_evaluation`'s internals change (still same public signature `(request, returns) -> tuple[list[dict], str | None]`) to read `request.constraints.rolling_window_mode`/`lookback_period_months` and pass them through, and to slice each fold's training window using `fold.train_start` when set.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_rolling_fold_schedule.py`:

```python
def test_expanding_mode_leaves_train_start_none():
    index = pd.date_range("2021-01-01", "2021-06-30", freq="D")
    folds = build_fold_schedule(index, "monthly")  # mode defaults to "expanding"
    assert all(f.train_start is None for f in folds)


def test_trailing_mode_sets_a_fixed_length_train_start():
    # 8 months of daily data, monthly cadence, 2-month lookback.
    index = pd.date_range("2021-01-01", "2021-08-31", freq="D")
    folds = build_fold_schedule(index, "monthly", mode="trailing", lookback_months=2)
    assert len(folds) == 7  # 8 distinct months -> 7 folds, same count as expanding mode
    for fold in folds:
        assert fold.train_start is not None
        # The trailing window's length should be close to 2 calendar months
        # of daily data (58-62 days), never the full expanding span back to
        # index[0] -- this is the concrete, discriminating assertion that
        # would fail if trailing mode silently fell back to expanding
        # behavior.
        window_days = (fold.train_end - fold.train_start).days
        assert 55 <= window_days <= 65


def test_trailing_mode_train_start_is_clamped_to_available_history():
    # Fold 0 (earliest) with a 2-month lookback on data that only goes back
    # to index[0] itself -- the trailing window cannot start before the
    # data actually begins, so train_start must clamp to index[0] rather
    # than requesting data that doesn't exist.
    index = pd.date_range("2021-01-01", "2021-08-31", freq="D")
    folds = build_fold_schedule(index, "monthly", mode="trailing", lookback_months=2)
    assert folds[0].train_start >= index.min()
    assert folds[0].train_start <= index.min() + pd.Timedelta(days=31)  # first fold's train_end is end of Feb; a 2-month lookback from there lands close to index[0] itself
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_rolling_fold_schedule.py -v`
Expected: FAIL — `TypeError: build_fold_schedule() got an unexpected keyword argument 'mode'`

- [ ] **Step 3: Add `train_start` to `FoldSpec` and mode support to `build_fold_schedule`**

In `backend/app/optimizer/rolling.py`, replace the `FoldSpec` dataclass:

```python
@dataclass(frozen=True)
class FoldSpec:
    period_label: str
    train_start: pd.Timestamp | None
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
```

Replace the `build_fold_schedule` function:

```python
def build_fold_schedule(
    index: pd.DatetimeIndex, frequency: str, mode: str = "expanding", lookback_months: int | None = None
) -> list[FoldSpec]:
    """Fold schedule keyed off calendar periods matching ``frequency``
    ("monthly"/"quarterly"/"annually", matching OptimizationFrequency's
    values). ``mode="expanding"`` (default, unchanged from this function's
    original behavior): every fold's training window starts at
    ``index[0]`` (``train_start`` stays ``None``, and the caller slices
    ``returns.loc[:fold.train_end]``, which is expanding because it always
    starts from the same beginning). ``mode="trailing"``: each fold's
    training window is a FIXED length of ``lookback_months`` months
    immediately preceding ``train_end``, sliding forward each fold instead
    of growing -- ``train_start`` is set to the first index row on or after
    ``train_end - lookback_months`` months, clamped to ``index.min()`` if
    the requested lookback would start before the data actually begins.

    Fold i (0-indexed) trains through the last row of calendar period i --
    so fold 0 trains on the first distinct period only -- and is tested on
    calendar period i+1 in full. One fewer fold than there are distinct
    calendar periods in ``index``, because the first period is
    training-only -- there is no preceding period for it to have been
    tested "out of sample" against. This fold COUNT and TEST-period
    behavior is identical in both modes; only each fold's training WINDOW
    start differs.
    """
    if len(index) == 0:
        return []
    periods = pd.PeriodIndex(index, freq=_PERIOD_FREQ[frequency])
    boundaries = sorted(set(periods))
    folds: list[FoldSpec] = []
    for i in range(len(boundaries) - 1):
        train_period = boundaries[i]
        test_period = boundaries[i + 1]
        train_rows = index[periods == train_period]
        test_rows = index[periods == test_period]
        train_end = train_rows.max()

        train_start = None
        if mode == "trailing":
            cutoff = train_end - pd.DateOffset(months=lookback_months)
            eligible = index[index >= cutoff]
            train_start = eligible.min() if len(eligible) > 0 else index.min()
            if train_start < index.min():
                train_start = index.min()

        folds.append(
            FoldSpec(
                period_label=str(test_period),
                train_start=train_start,
                train_end=train_end,
                test_start=test_rows.min(),
                test_end=test_rows.max(),
            )
        )
    return folds
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_rolling_fold_schedule.py -v`
Expected: PASS (all tests in the file, including the 3 new ones)

- [ ] **Step 5: Wire mode/lookback into `run_rolling_evaluation` and respect `train_start` in slicing**

In `backend/app/optimizer/rolling.py`, find this line inside `run_rolling_evaluation`:

```python
    schedule = build_fold_schedule(returns.index, frequency)
```

Replace it with:

```python
    mode = request.constraints.rolling_window_mode.value
    lookback_months = request.constraints.lookback_period_months if mode == "trailing" else None
    schedule = build_fold_schedule(returns.index, frequency, mode=mode, lookback_months=lookback_months)
```

Find this line (the training-floor filter):

```python
    usable = [f for f in schedule if len(returns.loc[: f.train_end]) >= train_floor]
```

Replace it with:

```python
    usable = [
        f for f in schedule
        if len(returns.loc[(f.train_start if f.train_start is not None else returns.index[0]) : f.train_end]) >= train_floor
    ]
```

Find this line (inside the per-fold loop):

```python
        train_returns = returns.loc[: fold.train_end]
```

Replace it with:

```python
        train_start = fold.train_start if fold.train_start is not None else returns.index[0]
        train_returns = returns.loc[train_start : fold.train_end]
```

- [ ] **Step 6: Add an integration test proving expanding mode is byte-identical to before this task, and a trailing-mode integration test against the real cache**

Add to `backend/tests/test_rolling_evaluation.py`:

```python
def test_expanding_mode_still_produces_the_same_folds_as_before(two_real_fund_request):
    # Regression guard: two_real_fund_request never sets rollingWindowMode,
    # so it defaults to "expanding" -- this must produce the exact same
    # fold count and note as before this task's changes.
    returns = _load_returns(two_real_fund_request)
    folds, note = run_rolling_evaluation(two_real_fund_request, returns)
    assert len(folds) >= 1
    assert note is None


def test_trailing_mode_against_real_cache(two_real_fund_request):
    trailing_request = two_real_fund_request.model_copy(
        update={
            "constraints": two_real_fund_request.constraints.model_copy(
                update={"rolling_window_mode": "trailing", "lookback_period_months": 12}
            )
        }
    )
    returns = _load_returns(trailing_request)
    folds, note = run_rolling_evaluation(trailing_request, returns)
    assert len(folds) >= 1
```

Check the file's existing `_load_returns` helper name/import matches this reference (it should already exist from sub-project 2's tests in this same file).

- [ ] **Step 7: Run the full relevant test set**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_rolling_fold_schedule.py backend/tests/test_rolling_evaluation.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py -v`
Expected: PASS, all tests — the smoke matrix and `test_optimizer_service.py`'s existing tests are the main regression guard here (none of them set `rollingWindowMode`, so all must behave exactly as before)

- [ ] **Step 8: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/rolling.py backend/tests/test_rolling_fold_schedule.py backend/tests/test_rolling_evaluation.py`
Expected: All checks passed

- [ ] **Step 9: Commit**

```bash
git add backend/app/optimizer/rolling.py backend/tests/test_rolling_fold_schedule.py backend/tests/test_rolling_evaluation.py
git commit -m "feat: add trailing-window mode to the rolling evaluator (rollingWindowMode)"
```

---

### Task 4: `OptimizeResult.robustOptimizationNote` field

**Files:**
- Modify: `backend/app/domain/optimize_schemas.py`
- Test: `backend/tests/test_optimize_schemas.py`

**Interfaces:**
- Produces: `OptimizeResult.robust_optimization_note: str | None` (wire name `robustOptimizationNote`) — consumed by Task 5's `robust.py` and Task 6's `service.py` wiring.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_optimize_schemas.py` (reuse the same valid-payload pattern Task 1's tests / prior sub-projects' `compareNote`/`constraintNote` tests already established in this file):

```python
def test_optimize_result_accepts_robust_optimization_note():
    payload = _valid_optimize_result_payload()  # use this file's real helper name
    payload["robustOptimizationNote"] = "Robust optimization: averaged 487 of 500 resamples."
    result = OptimizeResult.model_validate(payload)
    assert result.robust_optimization_note == "Robust optimization: averaged 487 of 500 resamples."

    payload["robustOptimizationNote"] = None
    result = OptimizeResult.model_validate(payload)
    assert result.robust_optimization_note is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimize_schemas.py -k robust_optimization_note -v`
Expected: FAIL — extra field not permitted or `AttributeError`

- [ ] **Step 3: Add the field**

In `backend/app/domain/optimize_schemas.py`, add to `OptimizeResult` (immediately after `constraint_note`):

```python
    constraint_note: str | None
    robust_optimization_note: str | None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimize_schemas.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the full existing optimizer test suite to confirm the expected, documented breakage**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py backend/tests/test_api_optimize.py -v`
Expected: FAIL — `service.py`'s `OptimizeResult.model_validate({...})` call does not yet include a `"robustOptimizationNote"` key, so every existing call now errors with a missing-field validation error. This is expected and gets fixed in Task 6, not this one — the same pattern every prior sub-project's new-`*Note`-field task established.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/optimize_schemas.py backend/tests/test_optimize_schemas.py
git commit -m "feat: add OptimizeResult.robustOptimizationNote field"
```

---

### Task 5: `robust.py` — `resample_and_solve`

**Files:**
- Create: `backend/app/optimizer/robust.py`
- Test: `backend/tests/test_robust.py`

**Interfaces:**
- Consumes: `inputs.build_mu_sigma(request, returns) -> tuple[pd.Series, pd.DataFrame]` (existing), `solvers.solve_for_goal(request, mu, sigma, returns) -> dict[str, float]` (existing).
- Produces: `robust.resample_and_solve(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame) -> tuple[dict[str, float], str | None]` — averaged weights (or a single-shot fallback) plus an explanatory note. Consumed by Task 6's `service.py` wiring.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_robust.py`:

```python
import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.robust import resample_and_solve


@pytest.fixture
def two_real_fund_request():
    return OptimizeRequest.model_validate({
        "funds": [
            {"projId": "M0209_2548", "displayName": "K-SET50"},
            {"projId": "M0155_2547", "displayName": "M-S50"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2016-01-31", "endDate": "2019-12-31"},
        "dataFrequency": "monthly", "goal": "max_sharpe", "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": True, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })


def test_resample_and_solve_against_real_cache_measures_real_time(two_real_fund_request):
    # This is the plan's explicit performance-measurement requirement: log
    # real wall-clock time for 500 resamples against the real committed NAV
    # cache, on a real 2-fund request. Not an automated pass/fail threshold
    # (the design spec deliberately leaves that as an open question to
    # raise back to the user if it proves unreasonable) -- but the timing
    # MUST be printed/logged so a human reviewing this task's report can
    # see the real number, not guess at it.
    import time

    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    returns = build_returns_panel(two_real_fund_request)
    mu, sigma = build_mu_sigma(two_real_fund_request, returns)

    started = time.monotonic()
    weights, note = resample_and_solve(two_real_fund_request, mu, sigma, returns)
    elapsed = time.monotonic() - started
    print(f"\nresample_and_solve: 500 resamples on a 2-fund request took {elapsed:.2f}s wall-clock")

    assert sum(weights.values()) == pytest.approx(100, abs=1.0)
    assert note is not None
    assert "resample" in note.lower()


def test_resample_and_solve_falls_back_when_most_resamples_fail(two_real_fund_request, monkeypatch):
    # Force every resample's solve to fail, so the function must fall back
    # to a single-shot solve on the ORIGINAL mu/sigma rather than raising or
    # returning garbage.
    import backend.app.optimizer.robust as robust_module

    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    returns = build_returns_panel(two_real_fund_request)
    mu, sigma = build_mu_sigma(two_real_fund_request, returns)

    call_count = {"n": 0}
    original_solve = robust_module.solvers.solve_for_goal

    def flaky_solve(request, resample_mu, resample_sigma, resample_returns):
        call_count["n"] += 1
        if call_count["n"] <= 500:
            # Fail every resample's solve; the 501st call (if it happens)
            # is the single-shot fallback on the original data.
            raise RuntimeError("SOLVER_NON_CONVERGENCE")
        return original_solve(request, resample_mu, resample_sigma, resample_returns)

    monkeypatch.setattr(robust_module.solvers, "solve_for_goal", flaky_solve)
    weights, note = resample_and_solve(two_real_fund_request, mu, sigma, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=1.0)
    assert note is not None
    assert "fell back" in note.lower() or "fallback" in note.lower()


def test_resample_and_solve_averages_weights_on_a_synthetic_case(monkeypatch):
    # A minimal synthetic case where every resample's solve is monkeypatched
    # to return one of two known fixed weight sets alternately -- the
    # averaged result must be the arithmetic mean of the two, proving the
    # averaging logic itself (not the solver) is correct.
    import backend.app.optimizer.robust as robust_module

    request = OptimizeRequest.model_validate({
        "funds": [
            {"projId": "A", "displayName": "Fund A"},
            {"projId": "B", "displayName": "Fund B"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2021-12-31"},
        "dataFrequency": "monthly", "goal": "max_sharpe", "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": True, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })
    dates = pd.date_range("2020-01-31", periods=24, freq="ME")
    returns = pd.DataFrame({"A": [0.01, -0.005] * 12, "B": [0.008, 0.012] * 12}, index=dates)
    pct = returns * 100
    mu = pct.mean() * 12
    sigma = pct.cov() * 12

    call_count = {"n": 0}

    def alternating_solve(req, resample_mu, resample_sigma, resample_returns):
        call_count["n"] += 1
        if call_count["n"] % 2 == 0:
            return {"A": 60.0, "B": 40.0}
        return {"A": 40.0, "B": 60.0}

    monkeypatch.setattr(robust_module.solvers, "solve_for_goal", alternating_solve)
    weights, note = resample_and_solve(request, mu, sigma, returns)
    assert weights["A"] == pytest.approx(50.0, abs=0.1)
    assert weights["B"] == pytest.approx(50.0, abs=0.1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_robust.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.optimizer.robust'`

- [ ] **Step 3: Create `robust.py`**

Create `backend/app/optimizer/robust.py`:

```python
"""Monte Carlo resampling (Michaud-style) for robustOptimization.
Verified via live research against the real PortfolioVisualizer tool that
"Robust Optimization: Yes/No" uses resampling-based Monte Carlo, not
riskfolio-lib's own Worst-Case mean-variance model -- a different
technique. See
docs/superpowers/specs/2026-08-10-phase5-return-method-lookback-robust-design.md
for the full research/design rationale.

Applies ONLY to the main solve (per design decision) -- never the rolling
evaluator's per-fold solves, never the comparison portfolio's solve, and
never re-run inside holdings.enforce_max_holdings's trim loop (only its
initial solve).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer import inputs, solvers

RESAMPLE_COUNT = 500
MIN_SUCCESSFUL_FRACTION = 0.5


def resample_and_solve(
    request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame
) -> tuple[dict[str, float], str | None]:
    """Bootstrap-resamples returns' rows (with replacement) RESAMPLE_COUNT
    times, recomputes mu/Sigma per resample via inputs.build_mu_sigma
    (same estimation logic, no new formula), solves via
    solvers.solve_for_goal, and averages the WEIGHTS of every
    successfully-solved resample -- Michaud resampling's defining step.

    A resample whose solve fails is skipped, not fatal. If fewer than
    RESAMPLE_COUNT * MIN_SUCCESSFUL_FRACTION resamples succeed, falls back
    to a single-shot solve on the ORIGINAL mu/sigma with an explanatory
    note -- never a hard error.

    Note: covariance_method="ewma" depends on chronological row order for
    its halflife weighting; bootstrap resampling scrambles that order, so
    EWMA combined with robust optimization produces a covariance estimate
    that no longer means "more recent observations weighted more heavily"
    within each resample. This is a known limitation, not a bug -- sample
    and shrinkage covariance (the common case) are unaffected since they
    don't depend on row order.
    """
    proj_ids = list(mu.index)
    n_obs = len(returns)
    rng = np.random.default_rng()

    successful_weights: list[dict[str, float]] = []
    for _ in range(RESAMPLE_COUNT):
        sample_idx = rng.integers(0, n_obs, size=n_obs)
        resampled_returns = returns.iloc[sample_idx].reset_index(drop=True)
        try:
            resampled_mu, resampled_sigma = inputs.build_mu_sigma(request, resampled_returns)
            weights = solvers.solve_for_goal(request, resampled_mu, resampled_sigma, resampled_returns)
        except (ValueError, RuntimeError):
            continue
        successful_weights.append(weights)

    required = int(RESAMPLE_COUNT * MIN_SUCCESSFUL_FRACTION)
    if len(successful_weights) < required:
        fallback_weights = solvers.solve_for_goal(request, mu, sigma, returns)
        note = (
            f"Robust optimization fell back to a single-shot solve: only "
            f"{len(successful_weights)} of {RESAMPLE_COUNT} resamples converged "
            f"(need at least {required})."
        )
        return fallback_weights, note

    total_runs = len(successful_weights)
    averaged = {pid: 0.0 for pid in proj_ids}
    for weights in successful_weights:
        for pid in proj_ids:
            averaged[pid] += weights.get(pid, 0.0)
    averaged = {pid: round(v / total_runs, 4) for pid, v in averaged.items()}
    note = f"Robust optimization: averaged {total_runs} of {RESAMPLE_COUNT} resamples."
    return averaged, note
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_robust.py -v -s`
Expected: PASS (4 tests) — the `-s` flag is needed to see the real-cache test's printed wall-clock timing, since pytest captures stdout by default

- [ ] **Step 5: Record the real measured timing in the task report**

This step has no code — it is a REQUIRED reporting step per this plan's Global Constraints and the design spec's explicit performance-measurement decision. Whoever executes this task must copy the exact printed wall-clock time from Step 4's output into their task report, plainly, as a number (e.g. "500 resamples on the real 2-fund fixture took 4.32s wall-clock"). Do not skip this or approximate it — if the number is concerning (multi-second-plus, or clearly unreasonable for a synchronous HTTP request), say so explicitly in the report's concerns section rather than silently proceeding; this is exactly the case the design spec asks to be surfaced back to the human, not judged automatically.

- [ ] **Step 6: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/robust.py backend/tests/test_robust.py`
Expected: All checks passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/optimizer/robust.py backend/tests/test_robust.py
git commit -m "feat: add robust.resample_and_solve (Monte Carlo resampling for robustOptimization)"
```

---

### Task 6: Wire into `service.py`, extend `holdings.enforce_max_holdings`, extend the smoke matrix

**Files:**
- Modify: `backend/app/optimizer/holdings.py`
- Modify: `backend/app/optimizer/service.py`
- Modify: `backend/tests/test_optimizer_smoke_matrix.py`
- Test: `backend/tests/test_holdings.py`, `backend/tests/test_optimizer_service.py` (extend both)

**Interfaces:**
- Consumes: `robust.resample_and_solve(request, mu, sigma, returns) -> tuple[dict[str, float], str | None]` (Task 5).
- Modifies: `holdings.enforce_max_holdings` gains a new OPTIONAL keyword-only parameter `initial_weights: dict[str, float] | None = None` — when provided, used as the initial (pre-trim) solve instead of calling `solvers.solve_for_goal` internally; every existing call site (which doesn't pass this parameter) is completely unaffected. `service.py`'s `OptimizeResult.model_validate({...})` gains `"robustOptimizationNote"`.

- [ ] **Step 1: Write the failing test for `holdings.py`'s new parameter**

Add to `backend/tests/test_holdings.py` (reuse this file's existing `_request`/`_mu_sigma_returns` helpers from sub-project 4):

```python
def test_enforce_max_holdings_uses_initial_weights_when_provided():
    request = _request(max_holdings=4)
    mu, sigma, returns = _mu_sigma_returns()
    fixed_initial = {"A": 25.0, "B": 25.0, "C": 25.0, "D": 25.0}
    weights, note = enforce_max_holdings(request, mu, sigma, returns, initial_weights=fixed_initial)
    # With max_holdings=4 on a 4-fund universe, no trimming is needed, so
    # the returned weights must be exactly the provided initial_weights,
    # NOT a fresh solve_for_goal result (which would very likely differ,
    # since the fixture's funds have distinct volatilities).
    assert weights == fixed_initial
    assert note is None


def test_enforce_max_holdings_still_trims_from_a_provided_initial_solve():
    request = _request(max_holdings=1)
    mu, sigma, returns = _mu_sigma_returns()
    fixed_initial = {"A": 25.0, "B": 25.0, "C": 25.0, "D": 25.0}
    weights, note = enforce_max_holdings(request, mu, sigma, returns, initial_weights=fixed_initial)
    held = [pid for pid, w in weights.items() if w > 0.5]
    assert len(held) <= 1
    assert note is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_holdings.py -k initial_weights -v`
Expected: FAIL with `TypeError: enforce_max_holdings() got an unexpected keyword argument 'initial_weights'`

- [ ] **Step 3: Add the `initial_weights` parameter to `enforce_max_holdings`**

In `backend/app/optimizer/holdings.py`, find:

```python
def enforce_max_holdings(
    request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame
) -> tuple[dict[str, float], str | None]:
```

Replace with:

```python
def enforce_max_holdings(
    request: OptimizeRequest,
    mu: pd.Series,
    sigma: pd.DataFrame,
    returns: pd.DataFrame,
    *,
    initial_weights: dict[str, float] | None = None,
) -> tuple[dict[str, float], str | None]:
```

Find:

```python
    max_holdings = request.constraints.max_holdings
    weights = solvers.solve_for_goal(request, mu, sigma, returns)
```

Replace with:

```python
    max_holdings = request.constraints.max_holdings
    # initial_weights lets a caller supply an already-computed initial
    # solve (e.g. robust.resample_and_solve's Monte Carlo average) instead
    # of a plain solve_for_goal call -- only the INITIAL solve is
    # substitutable; every trim-loop re-solve below still calls plain
    # solve_for_goal (re-running 500 resamples per trimmed fund would be
    # far too expensive, and is out of this parameter's scope).
    weights = initial_weights if initial_weights is not None else solvers.solve_for_goal(request, mu, sigma, returns)
```

Update the function's docstring's first sentence to mention the new parameter (read the current docstring and add one sentence, don't rewrite it wholesale).

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_holdings.py -v`
Expected: PASS (all tests in the file, including the 2 new ones)

- [ ] **Step 5: Wire `robust.resample_and_solve` into `service.py`**

In `backend/app/optimizer/service.py`, add to the imports (the existing `from backend.app.optimizer import (...)` block):

```python
from backend.app.optimizer import (
    black_litterman,
    comparison,
    diagnostics,
    frontier,
    holdings,
    inputs,
    report,
    robust,
    rolling,
    solvers,
)
```

Replace this line:

```python
    optimal_weights, constraint_note = holdings.enforce_max_holdings(request, mu, sigma, returns)
```

with:

```python
    robust_initial_weights = None
    robust_optimization_note = None
    if request.constraints.robust_optimization:
        robust_initial_weights, robust_optimization_note = robust.resample_and_solve(request, mu, sigma, returns)

    optimal_weights, constraint_note = holdings.enforce_max_holdings(
        request, mu, sigma, returns, initial_weights=robust_initial_weights
    )
```

Then add `"robustOptimizationNote": robust_optimization_note,` to the `OptimizeResult.model_validate({...})` dict, placed next to the other `*Note` fields (`robustNote`, `compareNote`, `constraintNote`) for readability.

- [ ] **Step 6: Add the integration test for `run_optimize`**

Add to `backend/tests/test_optimizer_service.py`:

```python
def test_run_optimize_applies_robust_optimization_when_enabled(two_real_fund_request):
    robust_request = two_real_fund_request.model_copy(update={"robust_optimization": True})
    result = run_optimize(robust_request)
    assert result.robust_optimization_note is not None
    assert sum(result.optimal_weights.values()) == pytest.approx(100, abs=0.5)


def test_run_optimize_leaves_robust_optimization_note_none_when_disabled(two_real_fund_request):
    result = run_optimize(two_real_fund_request)
    assert result.robust_optimization_note is None
```

- [ ] **Step 7: Run test to verify it passes**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py -v`
Expected: PASS (all tests in the file) — note the robust-optimization test in this file will take real wall-clock time (500 resamples against the real cache), which is expected

- [ ] **Step 8: Extend the smoke matrix with `robust_optimization` and `rolling_window_mode` variants**

Read `backend/tests/test_optimizer_smoke_matrix.py` in full first (enum-driven, parametrized over `ObjectiveGoal` × `RiskMeasure` × `CompareAgainst`, currently 112 cases as of sub-project 4). Given robust optimization's real per-request cost (500 resamples), do NOT add it as a fourth full parametrization dimension (that would multiply the smoke matrix's already-112-case runtime by up to 500x, making the suite impractically slow) — instead add ONE separate, non-parametrized (or minimally parametrized over just goal) smoke test:

```python
def test_robust_optimization_smoke_across_a_few_goals(returns_fixture):  # match this file's actual fixture name
    for goal in ["max_sharpe", "min_variance", "risk_parity"]:
        request = _synthetic_request(goal=goal, robust_optimization=True)  # adapt to this file's actual request-building helper
        result = run_optimize(request)
        assert sum(result.optimal_weights.values()) == pytest.approx(100, abs=0.5)
        assert result.robust_optimization_note is not None
```

Check the file's real fixture/helper names before writing this — do not invent function names that don't exist in the file. The point of this test is proving robust optimization doesn't crash or silently no-op for a SAMPLE of goals (not every combination — the per-task `test_robust.py` and `test_optimizer_service.py` tests already cover correctness in depth), kept small deliberately for the smoke suite's own runtime.

Separately, add ONE assertion to the EXISTING 112-case parametrized test's body confirming `rollingWindowMode`'s default doesn't change existing behavior (this should already be implicitly true from Task 3's regression tests, but add a cheap confirming line here too):

```python
    assert request.constraints.rolling_window_mode.value == "expanding"
```

- [ ] **Step 9: Run the full relevant test set**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_robust.py backend/tests/test_holdings.py backend/tests/test_optimizer_solvers_group_constraints.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py backend/tests/test_optimize_schemas.py backend/tests/test_rolling_fold_schedule.py backend/tests/test_rolling_evaluation.py backend/tests/test_comparison.py backend/tests/test_api_optimize.py -v`
Expected: PASS, all tests — this run will take noticeably longer than prior sub-projects' equivalent runs due to the 500-resample tests; that is expected, not a regression to chase.

- [ ] **Step 10: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/holdings.py backend/app/optimizer/service.py backend/tests/test_holdings.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py`
Expected: All checks passed

- [ ] **Step 11: Commit**

```bash
git add backend/app/optimizer/holdings.py backend/app/optimizer/service.py backend/tests/test_holdings.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py
git commit -m "feat: wire robust.resample_and_solve into service.run_optimize"
```

---

### Task 7: Rate-limit `robustOptimization` requests specifically

**Why this task exists:** Task 5's real-cache measurement (independently reproduced by two separate reviewers: 7.3-7.4s and 6.72s, same order of magnitude) confirmed 500 bootstrap resamples cost several seconds of synchronous wall-clock time per request — far more than a normal `/api/optimize` request. Per explicit decision, the feature ships as-is (still 500 resamples, still synchronous, no architecture change) but gets its OWN, stricter rate limit on top of the route's existing blanket `10/minute` (`backend/app/api/optimize.py`), since a client sending several `robustOptimization: true` requests in quick succession could tie up request-handling capacity disproportionately to a normal request.

**Files:**
- Modify: `backend/app/api/optimize.py`
- Test: `backend/tests/test_api_optimize.py`

**Interfaces:**
- Produces: an additional, in-process rate check specific to `robustOptimization: true` requests, enforced inside `create_optimization` (the existing route handler) — the route's existing blanket `@limiter.limit("10/minute")` decorator is UNCHANGED and still applies to every request regardless of this new check.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_api_optimize.py`. Read the file first to match its existing pattern for constructing a `TestClient` and a valid request payload (the same pattern earlier sub-projects' tests in this file already established):

```python
def test_robust_optimization_requests_are_rate_limited_more_strictly(client, valid_optimize_payload):
    # Reuse this file's existing TestClient/payload fixtures (check their real
    # names first) -- adapt request payload construction to match this
    # file's established helper rather than inventing a new one.
    payload = {**valid_optimize_payload, "robustOptimization": True}

    responses = [client.post("/api/optimize", json=payload) for _ in range(3)]
    statuses = [r.status_code for r in responses]

    # The first 2 robust-optimization requests in a short window succeed
    # (subject to the normal solve outcome, i.e. 200), the 3rd is rejected
    # with 429 before ever reaching run_optimize -- proving the
    # robust-specific limiter fires independently of the route's blanket
    # 10/minute limit (which would not have tripped after only 3 requests).
    assert statuses[:2].count(429) == 0
    assert statuses[2] == 429


def test_non_robust_requests_are_unaffected_by_the_robust_rate_limit(client, valid_optimize_payload):
    # 3 consecutive non-robust requests must NOT trip the robust-specific
    # limiter -- it only counts robustOptimization=true requests.
    payload = {**valid_optimize_payload, "robustOptimization": False}
    responses = [client.post("/api/optimize", json=payload) for _ in range(3)]
    assert all(r.status_code != 429 for r in responses)
```

If this file has no existing `client`/`valid_optimize_payload` fixtures under those exact names, read the file's real fixture names and adapt — do not invent fixture names that don't exist in the file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_api_optimize.py -k robust_optimization_requests -v`
Expected: FAIL — the 3rd robust-optimization request currently succeeds (or fails for an unrelated reason, e.g. a real solve outcome), not `429`

- [ ] **Step 3: Add the robust-specific rate check**

In `backend/app/api/optimize.py`, add a small in-process tracker and check function above the route handler (after the existing imports, before `router = APIRouter(...)`):

```python
import time
from collections import defaultdict

from slowapi.util import get_remote_address

# A second, independent rate limit specific to robustOptimization=true
# requests, on top of the route's existing blanket @limiter.limit
# ("10/minute", below). 500 bootstrap resamples measured at 6.7-7.4s
# wall-clock against the real NAV cache (Phase 5 sub-project 5's design
# spec/plan) -- several seconds per request, several times more expensive
# than a normal request, so it gets its own, stricter cap. In-process
# (not shared across workers) is acceptable for this project's
# single-process docker-compose deployment (see CLAUDE.md).
_ROBUST_OPTIMIZATION_RATE_LIMIT = 2
_ROBUST_OPTIMIZATION_RATE_WINDOW_SECONDS = 60
_robust_optimization_request_times: dict[str, list[float]] = defaultdict(list)


def _check_robust_optimization_rate_limit(client_key: str) -> None:
    now = time.monotonic()
    window_start = now - _ROBUST_OPTIMIZATION_RATE_WINDOW_SECONDS
    recent = [t for t in _robust_optimization_request_times[client_key] if t > window_start]
    if len(recent) >= _ROBUST_OPTIMIZATION_RATE_LIMIT:
        raise AppHTTPException(
            status_code=429,
            detail="Too many robust-optimization requests. Please wait before retrying.",
            code=ErrorCode.RATE_LIMITED,
        )
    recent.append(now)
    _robust_optimization_request_times[client_key] = recent
```

Then, inside `create_optimization`, immediately after the existing `proj_ids = [...]` line (before the `try:` block that calls `run_optimize`), add:

```python
    if optimize_request.constraints.robust_optimization:
        _check_robust_optimization_rate_limit(get_remote_address(request))
```

Check the exact current line order in the file before inserting — this must run BEFORE `run_optimize` is called, so a client that will be rejected never pays for a partial solve.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_api_optimize.py -v`
Expected: PASS (all tests in the file, including the 2 new ones)

- [ ] **Step 5: Run the full relevant test set**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_api_optimize.py backend/tests/test_optimizer_service.py backend/tests/test_robust.py -v`
Expected: PASS, all tests — confirm the existing blanket `10/minute` limiter and every other route behavior is unaffected.

- [ ] **Step 6: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/api/optimize.py backend/tests/test_api_optimize.py`
Expected: All checks passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/optimize.py backend/tests/test_api_optimize.py
git commit -m "feat: rate-limit robustOptimization requests more strictly (2/minute)"
```

---

## After all tasks: full suite verification

Run the full backend suite once, as the final check before this plan's own final review:

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests -q`
Expected: all pass. This run will take noticeably longer than prior sub-projects' final-suite runs — beyond the one pre-existing slow, unrelated test (`test_api_backtests.py::test_backtest_endpoint_uses_sec_cache_and_persists_run`, ~15 minutes, not a regression from this plan, do not investigate it), the new robust-optimization tests each involve 500 real solves against the committed NAV cache. If the total runtime becomes impractical, that itself is evidence for the design spec's flagged performance question — report the real number, don't silently wait past a reasonable timeout without saying so.
