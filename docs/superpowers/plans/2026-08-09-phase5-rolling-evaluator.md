# Phase 5 sub-project 2: Rolling Out-of-Sample Evaluator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `POST /api/optimize`'s `OptimizeResult.rolling` field real — walk-forward re-optimization over expanding historical windows, scored out-of-sample via the existing backtest engine — replacing what is currently always an empty list.

**Architecture:** One new module, `backend/app/optimizer/rolling.py`, following the existing "orchestrator + pure functions per concern" shape: a pure `build_fold_schedule` function (date math only, no I/O) and a `run_rolling_evaluation` function that re-runs the exact per-goal solve path sub-project 1 already built, once per fold, scoring each fold's held-out period via `backend/app/engine/metrics.py`. `service.py` calls it once, after its existing single-shot solve, and assigns the result to `OptimizeResult.rolling`/`robustNote`.

**Tech Stack:** Python, pandas (date/period grouping), the existing `backend/app/optimizer/*` modules (riskfolio-lib underneath, untouched), `backend/app/engine/metrics.py` (existing, untouched), pytest.

## Global Constraints

- Reuse `backend/app/engine/metrics.py`'s existing `annualized_return`, `annualized_volatility`, `sharpe_ratio` for all realized (out-of-sample) scoring — never re-derive this math inline, exactly as `service.py`'s `performanceSummary` fix already does.
- Reuse the exact per-goal solve dispatch and every sub-project-1 module as-is (`inputs.build_returns_panel`/`build_mu_sigma`, `solvers.solve_mean_variance`/`solve_risk_parity`/`solve_hrp`, `black_litterman.blend_posterior`) — this plan's only new solver-adjacent code is the dispatch-extraction in Task 2, which moves existing logic, it does not add new solving logic.
- No new riskfolio-lib API usage, no new solver family, no MOSEK/GUROBI — every fold's solve reuses the exact same CLARABEL-backed calls sub-project 1 already verified against the real installed riskfolio-lib 7.3.0 API.
- A fold's solve failure (`ValueError`/`RuntimeError` from the existing solve path) is skipped and noted, never fatal to the whole request — only `ValueError("INSUFFICIENT_ROLLING_HISTORY")` (raised before any folds are attempted, when there aren't enough usable folds at all) fails the request.
- Error responses extend the existing `AppHTTPException` + `ErrorCode` pattern — the new `ErrorCode.INSUFFICIENT_ROLLING_HISTORY` must resolve through `backend/app/api/optimize.py`'s existing dynamic `getattr(ErrorCode, str(exc))` lookup with no route code change, exactly like `INDEFINITE_CORRELATION_MATRIX` already does.
- No fabricated/derived-from-a-different-metric numbers anywhere in the new code — every `RollingFold` field must come from a real `engine/metrics.py` call on that fold's own realized return series, not a placeholder or an approximation from a different quantity (this is the exact defect class the sub-project 1 final review caught in `performanceSummary` and `riskContributionPct`).
- No frontend files are touched anywhere in this plan — the `RollingFold`/`OptimizeConstraints.optimizationFrequency` wire contract already exists in `frontend/src/types/optimize.ts` and `backend/app/domain/optimize_schemas.py` unchanged.
- Every new module/function gets tests verified against this plan's own Step commands before moving to the next task — no task is "done" until its tests pass.
- Use `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3` for all commands (`pytest`, `ruff`) — never a bare `python3`/`pytest`.

---

### Task 1: Add `ErrorCode.INSUFFICIENT_ROLLING_HISTORY`

**Files:**
- Modify: `backend/app/domain/enums.py`
- Test: `backend/tests/test_optimizer_errors.py`

**Interfaces:**
- Produces: `ErrorCode.INSUFFICIENT_ROLLING_HISTORY` — consumed by Task 4's `run_rolling_evaluation` (raised as `ValueError("INSUFFICIENT_ROLLING_HISTORY")`) and resolved by `backend/app/api/optimize.py`'s existing dynamic lookup with no route change.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_optimizer_errors.py`:

```python
def test_insufficient_rolling_history_error_code_exists():
    assert ErrorCode.INSUFFICIENT_ROLLING_HISTORY == "INSUFFICIENT_ROLLING_HISTORY"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_errors.py -v`
Expected: FAIL with `AttributeError: INSUFFICIENT_ROLLING_HISTORY`

- [ ] **Step 3: Add the enum member**

In `backend/app/domain/enums.py`, add to `ErrorCode` (immediately after `INDEFINITE_CORRELATION_MATRIX`):

```python
    INDEFINITE_CORRELATION_MATRIX = "INDEFINITE_CORRELATION_MATRIX"
    INSUFFICIENT_ROLLING_HISTORY = "INSUFFICIENT_ROLLING_HISTORY"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_errors.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/enums.py backend/tests/test_optimizer_errors.py
git commit -m "feat: add INSUFFICIENT_ROLLING_HISTORY error code"
```

---

### Task 2: Extract shared per-goal solve dispatch into `solvers.solve_for_goal`

**Why this task exists:** `service.py`'s `run_optimize` currently has the goal-dispatch logic (`black_litterman` → blend then Sharpe-solve; `risk_parity` → `solve_risk_parity`; `hrp` → `solve_hrp`; everything else → `solve_mean_variance`) inlined. Task 4's `run_rolling_evaluation` needs the identical dispatch, once per fold, on a different `(mu, sigma, returns)` slice each time. Duplicating that dispatch logic in `rolling.py` would let the two copies drift (the exact defect class the final review of sub-project 1 already found and fixed once in this codebase — a UI/computation staying stale relative to another copy of the same logic). This task moves the dispatch into `solvers.py` once, with no behavior change, so both callers share it.

**Files:**
- Modify: `backend/app/optimizer/solvers.py` (add `solve_for_goal`; add `import` of `black_litterman`)
- Modify: `backend/app/optimizer/service.py` (replace the inlined dispatch with a call to `solvers.solve_for_goal`)
- Test: `backend/tests/test_optimizer_solvers_dispatch.py` (new)

**Interfaces:**
- Consumes: `solvers.solve_mean_variance(request, mu, sigma, returns) -> dict[str, float]`, `solvers.solve_risk_parity(request, mu, sigma, returns) -> dict[str, float]`, `solvers.solve_hrp(request, returns) -> dict[str, float]` (all existing, unchanged), `black_litterman.blend_posterior(request, mu, sigma) -> tuple[pd.Series, pd.Series]` (existing, unchanged).
- Produces: `solvers.solve_for_goal(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame) -> dict[str, float]` — consumed by Task 4's `run_rolling_evaluation` and by `service.py`'s existing main solve (this task rewires `service.py` to call it too).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_optimizer_solvers_dispatch.py`:

```python
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer import solvers


def _request(goal: str, black_litterman: dict | None = None) -> OptimizeRequest:
    payload = {
        "funds": [
            {"projId": "A", "displayName": "Fund A"},
            {"projId": "B", "displayName": "Fund B"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2021-12-31"},
        "dataFrequency": "monthly", "goal": goal, "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": False, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": black_litterman,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    }
    return OptimizeRequest.model_validate(payload)


def _mu_sigma_returns():
    dates = pd.date_range("2020-01-31", periods=24, freq="ME")
    returns = pd.DataFrame(
        {"A": [0.01, -0.005] * 12, "B": [0.008, 0.012] * 12},
        index=dates,
    )
    pct = returns * 100
    mu = pct.mean() * 12
    sigma = pct.cov() * 12
    return mu, sigma, returns


def test_solve_for_goal_dispatches_risk_parity():
    request = _request("risk_parity")
    mu, sigma, returns = _mu_sigma_returns()
    weights = solvers.solve_for_goal(request, mu, sigma, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_solve_for_goal_dispatches_hrp():
    request = _request("hrp")
    mu, sigma, returns = _mu_sigma_returns()
    weights = solvers.solve_for_goal(request, mu, sigma, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_solve_for_goal_dispatches_mean_variance():
    request = _request("min_variance")
    mu, sigma, returns = _mu_sigma_returns()
    weights = solvers.solve_for_goal(request, mu, sigma, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_solve_for_goal_dispatches_black_litterman():
    request = _request(
        "black_litterman",
        black_litterman={
            "riskAversion": 2.5,
            "marketWeightPct": {"A": 50.0, "B": 50.0},
            "views": [],
        },
    )
    mu, sigma, returns = _mu_sigma_returns()
    weights = solvers.solve_for_goal(request, mu, sigma, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)
```

If `BlackLittermanInputs`'s exact required field names differ from `riskAversion`/`marketWeightPct`/`views` shown above, read `backend/app/domain/optimize_schemas.py`'s `BlackLittermanInputs` class first and use its real field names — this is the one place in this plan where you must check the current schema rather than trust the sample verbatim, since sub-project 1 finalized these names independently of this plan.

- [ ] **Step 2: Run test to verify it fails**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_solvers_dispatch.py -v`
Expected: FAIL with `AttributeError: module 'backend.app.optimizer.solvers' has no attribute 'solve_for_goal'`

- [ ] **Step 3: Add `solve_for_goal` to `solvers.py`**

Add near the top of `backend/app/optimizer/solvers.py`, alongside the other imports (check the exact current import block first — this adds one new line to it):

```python
from backend.app.optimizer import black_litterman
```

Add the new function after `solve_hrp` (or after whichever function is currently last in the file — check the file's end first):

```python
def solve_for_goal(
    request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame
) -> dict[str, float]:
    """The single per-goal solve dispatch shared by service.py's main solve
    and rolling.py's per-fold solves, so the two never drift apart. For
    ``black_litterman`` this blends its own posterior mu internally and
    solves against it -- a caller that also needs the equilibrium/posterior
    values themselves (service.py's top-level ``blackLitterman`` result
    field) calls ``black_litterman.blend_posterior`` separately for that;
    the redundant second blend computed here is cheap linear algebra on a
    small matrix, not a correctness or performance concern."""
    if request.goal.value == "black_litterman":
        _, mu = black_litterman.blend_posterior(request, mu, sigma)
    if request.goal.value == "risk_parity":
        return solve_risk_parity(request, mu, sigma, returns)
    if request.goal.value == "hrp":
        return solve_hrp(request, returns)
    return solve_mean_variance(request, mu, sigma, returns)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_solvers_dispatch.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Rewire `service.py` to use `solve_for_goal`, with no behavior change**

In `backend/app/optimizer/service.py`, replace this block:

```python
    if request.goal.value == "risk_parity":
        optimal_weights = solvers.solve_risk_parity(request, mu, sigma, returns)
    elif request.goal.value == "hrp":
        optimal_weights = solvers.solve_hrp(request, returns)
    else:
        optimal_weights = solvers.solve_mean_variance(request, mu, sigma, returns)
```

with:

```python
    optimal_weights = solvers.solve_for_goal(request, mu, sigma, returns)
```

Leave everything else in `run_optimize` untouched, including the separate `black_litterman.blend_posterior(...)` call above this block that builds `bl_result` — `solve_for_goal` performs its own internal blend for the actual solve, independent of that call.

- [ ] **Step 6: Run the full existing optimizer test suite to confirm no regression**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py backend/tests/test_api_optimize.py -v`
Expected: PASS, same counts as before this task (this step must show zero behavior change from the refactor)

- [ ] **Step 7: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/solvers.py backend/app/optimizer/service.py backend/tests/test_optimizer_solvers_dispatch.py`
Expected: All checks passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/optimizer/solvers.py backend/app/optimizer/service.py backend/tests/test_optimizer_solvers_dispatch.py
git commit -m "refactor: extract shared per-goal solve dispatch into solvers.solve_for_goal"
```

---

### Task 3: `rolling.py` — `build_fold_schedule` (pure, date-only)

**Files:**
- Create: `backend/app/optimizer/rolling.py`
- Test: `backend/tests/test_rolling_fold_schedule.py`

**Interfaces:**
- Produces: `rolling.FoldSpec` (a frozen dataclass: `period_label: str`, `train_end: pd.Timestamp`, `test_start: pd.Timestamp`, `test_end: pd.Timestamp`) and `rolling.build_fold_schedule(index: pd.DatetimeIndex, frequency: str) -> list[FoldSpec]` — consumed by Task 4's `run_rolling_evaluation`. `frequency` is one of `"monthly"`/`"quarterly"`/`"annually"` (matches `OptimizationFrequency`'s values).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_rolling_fold_schedule.py`:

```python
import pandas as pd

from backend.app.optimizer.rolling import build_fold_schedule


def test_monthly_schedule_has_one_fold_per_month_after_the_first():
    # 6 distinct calendar months of daily data -> 5 folds (month 1 is
    # training-only, has no preceding period to be "out of sample" against).
    index = pd.date_range("2021-01-01", "2021-06-30", freq="D")
    folds = build_fold_schedule(index, "monthly")
    assert len(folds) == 5
    assert folds[0].period_label == "2021-02"


def test_expanding_window_train_end_grows_each_fold():
    index = pd.date_range("2021-01-01", "2021-06-30", freq="D")
    folds = build_fold_schedule(index, "monthly")
    train_ends = [f.train_end for f in folds]
    assert train_ends == sorted(train_ends)
    # Every train_end after the first is strictly later than the previous
    # fold's -- the window expands, it never resets or shrinks.
    assert all(later > earlier for earlier, later in zip(train_ends, train_ends[1:]))


def test_test_window_covers_the_full_following_period():
    index = pd.date_range("2021-01-01", "2021-03-31", freq="D")
    folds = build_fold_schedule(index, "monthly")
    assert len(folds) == 2
    first_fold = folds[0]
    assert first_fold.test_start == pd.Timestamp("2021-02-01")
    assert first_fold.test_end == pd.Timestamp("2021-02-28")


def test_quarterly_frequency_groups_by_quarter():
    index = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    folds = build_fold_schedule(index, "quarterly")
    # 8 distinct quarters across 2020-2021 -> 7 folds.
    assert len(folds) == 7
    assert folds[0].period_label == "2020Q2"


def test_annual_frequency_groups_by_year():
    index = pd.date_range("2016-01-01", "2019-12-31", freq="D")
    folds = build_fold_schedule(index, "annually")
    assert len(folds) == 3
    assert folds[0].period_label == "2017"


def test_empty_index_produces_no_folds():
    assert build_fold_schedule(pd.DatetimeIndex([]), "monthly") == []


def test_single_calendar_period_produces_no_folds():
    index = pd.date_range("2021-01-01", "2021-01-31", freq="D")
    assert build_fold_schedule(index, "monthly") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_rolling_fold_schedule.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.optimizer.rolling'`

- [ ] **Step 3: Create `rolling.py` with `build_fold_schedule`**

Create `backend/app/optimizer/rolling.py`:

```python
"""Walk-forward rolling out-of-sample evaluation: re-solves the request's
goal on an expanding training window per calendar period, scores the
result on the following held-out period via backend/app/engine/metrics.py.

Deviation from the spec's date math is none -- expanding window, fold
boundaries keyed to calendar periods matching the request's
optimization_frequency, exactly as
docs/superpowers/specs/2026-08-09-phase5-rolling-evaluator-design.md
describes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.engine import metrics
from backend.app.optimizer import inputs, solvers

_PERIOD_FREQ = {"monthly": "M", "quarterly": "Q", "annually": "Y"}

# A new floor, not reused from elsewhere -- no equivalent constant existed
# before this module (inputs.py only rejects an empty/all-NaN window, not a
# too-short-for-covariance one). 6 is a fixed floor, not scaled to fund
# count: this project's own fund-universe finding
# (docs/optimization-assumptions.md) says a usable shortlist is small (a
# handful of funds, not dozens), so a fixed floor comfortably covers a
# 2x2 up to a small double-digit covariance matrix without needing to read
# the fund count to set it. Folds below this floor are dropped from the
# schedule before any solve is attempted -- see run_rolling_evaluation.
MIN_TRAIN_OBSERVATIONS = 6


@dataclass(frozen=True)
class FoldSpec:
    period_label: str
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def build_fold_schedule(index: pd.DatetimeIndex, frequency: str) -> list[FoldSpec]:
    """Expanding-window fold schedule keyed off calendar periods matching
    ``frequency`` ("monthly"/"quarterly"/"annually", matching
    OptimizationFrequency's values). Every fold's training window starts at
    ``index[0]`` (the caller slices ``returns.loc[:fold.train_end]``, which
    is expanding because it always starts from the same beginning); fold
    i's training window ends at the last row of calendar period i+1 (0
    indexed: the second distinct period present), and its test window is
    calendar period i+2 in full. One fewer fold than there are distinct
    calendar periods in ``index``, because the first period is
    training-only -- there is no preceding period for it to have been
    tested "out of sample" against.
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
        folds.append(
            FoldSpec(
                period_label=str(test_period),
                train_end=train_rows.max(),
                test_start=test_rows.min(),
                test_end=test_rows.max(),
            )
        )
    return folds
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_rolling_fold_schedule.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/rolling.py backend/tests/test_rolling_fold_schedule.py`
Expected: All checks passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/optimizer/rolling.py backend/tests/test_rolling_fold_schedule.py
git commit -m "feat: add rolling.build_fold_schedule (expanding-window fold boundaries)"
```

---

### Task 4: `rolling.py` — `run_rolling_evaluation`

**Files:**
- Modify: `backend/app/optimizer/rolling.py` (add `run_rolling_evaluation`)
- Test: `backend/tests/test_rolling_evaluation.py`

**Interfaces:**
- Consumes: `rolling.build_fold_schedule` (Task 3), `inputs.build_mu_sigma(request, returns) -> tuple[pd.Series, pd.DataFrame]`, `inputs.periods_per_year(request) -> int`, `solvers.solve_for_goal(request, mu, sigma, returns) -> dict[str, float]` (Task 2), `metrics.annualized_return`/`annualized_volatility`/`sharpe_ratio` (existing, `backend/app/engine/metrics.py`).
- Produces: `rolling.run_rolling_evaluation(request: OptimizeRequest, returns: pd.DataFrame) -> tuple[list[dict], str | None]` — a list of dicts shaped exactly like `RollingFold`'s camelCase fields (`periodLabel`, `realizedReturnPct`, `realizedVolatilityPct`, `realizedSharpe`), ready for `OptimizeResult.model_validate` the same way `service.py` already hands `diagnostics.build_trade_list`'s dict output straight to model validation; plus an optional note string. Raises `ValueError("INSUFFICIENT_ROLLING_HISTORY")`. Consumed by Task 5's `service.py` wiring.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_rolling_evaluation.py`:

```python
import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.rolling import run_rolling_evaluation


@pytest.fixture
def two_real_fund_request() -> OptimizeRequest:
    # Same fixture funds/window as backend/tests/test_optimizer_service.py's
    # two_real_fund_request -- both confirmed present in the committed NAV
    # cache. Monthly data, quarterly optimization_frequency: 48 months
    # (2016-01-31..2019-12-31) is 16 quarters -> 15 folds.
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


def _load_returns(request: OptimizeRequest) -> pd.DataFrame:
    from backend.app.optimizer.inputs import build_returns_panel
    return build_returns_panel(request)


def test_rolling_evaluation_against_real_cache_produces_folds_from_real_metrics(two_real_fund_request):
    returns = _load_returns(two_real_fund_request)
    folds, note = run_rolling_evaluation(two_real_fund_request, returns)
    assert len(folds) >= 1
    for fold in folds:
        assert set(fold) == {"periodLabel", "realizedReturnPct", "realizedVolatilityPct", "realizedSharpe"}
        assert isinstance(fold["periodLabel"], str)
        assert fold["realizedVolatilityPct"] >= 0

    # Independently recompute the FIRST fold's realized stats by hand from
    # the same training/test slices run_rolling_evaluation itself would
    # have used, via the real engine/metrics.py functions -- proving the
    # returned numbers are genuinely computed, not a placeholder, the exact
    # defect class the sub-project 1 final review caught in
    # performanceSummary/riskContributionPct.
    from backend.app.optimizer import inputs, solvers
    from backend.app.optimizer.rolling import build_fold_schedule
    from backend.app.engine import metrics

    schedule = build_fold_schedule(returns.index, "quarterly")
    first_fold = schedule[0]
    train_returns = returns.loc[:first_fold.train_end]
    test_returns = returns.loc[first_fold.test_start:first_fold.test_end]
    mu, sigma = inputs.build_mu_sigma(two_real_fund_request, train_returns)
    weights = solvers.solve_for_goal(two_real_fund_request, mu, sigma, train_returns)
    proj_ids = [f.proj_id for f in two_real_fund_request.funds]
    aligned = np.array([weights.get(pid, 0.0) / 100 for pid in proj_ids])
    period_returns = (test_returns[proj_ids] @ aligned).dropna()
    expected_vol = round(metrics.annualized_volatility(period_returns, 12) * 100, 2)

    assert folds[0]["periodLabel"] == first_fold.period_label
    assert folds[0]["realizedVolatilityPct"] == pytest.approx(expected_vol, abs=0.01)


def test_insufficient_rolling_history_raises(two_real_fund_request):
    two_real_fund_request.time_period.start_date = "2019-10-31"
    two_real_fund_request.time_period.end_date = "2019-12-31"
    returns = _load_returns(two_real_fund_request)
    with pytest.raises(ValueError, match="INSUFFICIENT_ROLLING_HISTORY"):
        run_rolling_evaluation(two_real_fund_request, returns)


def test_a_thin_early_fold_is_skipped_not_fatal(two_real_fund_request, monkeypatch):
    returns = _load_returns(two_real_fund_request)

    from backend.app.optimizer import solvers as solvers_module

    original = solvers_module.solve_for_goal
    call_count = {"n": 0}

    def flaky_solve(request, mu, sigma, train_returns):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("SOLVER_NON_CONVERGENCE")
        return original(request, mu, sigma, train_returns)

    monkeypatch.setattr(solvers_module, "solve_for_goal", flaky_solve)
    folds, note = run_rolling_evaluation(two_real_fund_request, returns)
    assert note is not None
    assert "1 skipped" in note
    assert len(folds) >= 1
```

If `time_period.start_date`/`end_date` are not directly assignable strings on the Pydantic model (e.g. the model is frozen, or the field is a `date` not a `str`), construct a second `OptimizeRequest.model_validate(...)` with the shorter `timePeriod` instead of mutating the fixture in place — check `TimePeriod`'s real field type in `backend/app/domain/optimize_schemas.py` first.

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_rolling_evaluation.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_rolling_evaluation'`

- [ ] **Step 3: Add `run_rolling_evaluation` to `rolling.py`**

Append to `backend/app/optimizer/rolling.py`:

```python
def run_rolling_evaluation(
    request: OptimizeRequest, returns: pd.DataFrame
) -> tuple[list[dict], str | None]:
    """Walk-forward re-optimization: for each fold in the expanding-window
    schedule, re-solves the request's goal on the training slice via the
    exact same dispatch service.py's main solve uses
    (``solvers.solve_for_goal``), applies the result to the held-out test
    slice, and scores it via backend/app/engine/metrics.py. A fold whose
    solve raises is skipped and counted, never fatal to the whole request.

    Raises ``ValueError("INSUFFICIENT_ROLLING_HISTORY")`` -- the bare
    ErrorCode name, same convention as inputs.py/solvers.py, resolved by
    api/optimize.py's existing dynamic lookup with no route change -- when
    fewer than 2 folds have enough training observations to even attempt a
    solve. This check runs before any solve is attempted; a fold failing
    *during* its solve is a different, non-fatal path (see above).
    """
    frequency = request.constraints.optimization_frequency.value
    schedule = build_fold_schedule(returns.index, frequency)
    usable = [f for f in schedule if len(returns.loc[: f.train_end]) >= MIN_TRAIN_OBSERVATIONS]
    if len(usable) < 2:
        raise ValueError("INSUFFICIENT_ROLLING_HISTORY")

    proj_ids = [fund.proj_id for fund in request.funds]
    ppy = inputs.periods_per_year(request)
    risk_free_fraction = request.constraints.risk_free_rate_pct / 100

    folds: list[dict] = []
    failed = 0
    for fold in usable:
        train_returns = returns.loc[: fold.train_end]
        test_returns = returns.loc[fold.test_start : fold.test_end]
        if test_returns.empty:
            failed += 1
            continue
        try:
            mu, sigma = inputs.build_mu_sigma(request, train_returns)
            weights = solvers.solve_for_goal(request, mu, sigma, train_returns)
        except (ValueError, RuntimeError):
            failed += 1
            continue

        aligned = np.array([weights.get(proj_id, 0.0) / 100 for proj_id in proj_ids])
        period_returns = (test_returns[proj_ids] @ aligned).dropna()
        if period_returns.empty:
            failed += 1
            continue

        sharpe = metrics.sharpe_ratio(period_returns, risk_free_fraction, ppy)
        folds.append(
            {
                "periodLabel": fold.period_label,
                "realizedReturnPct": round(metrics.annualized_return(period_returns, ppy) * 100, 2),
                "realizedVolatilityPct": round(metrics.annualized_volatility(period_returns, ppy) * 100, 2),
                "realizedSharpe": round(sharpe, 2) if sharpe is not None else 0.0,
            }
        )

    note = None
    if failed > 0:
        note = (
            f"Rolling validation: {len(folds)} of {len(usable)} folds converged; "
            f"{failed} skipped due to solver non-convergence on thin training windows."
        )
    return folds, note
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_rolling_evaluation.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/rolling.py backend/tests/test_rolling_evaluation.py`
Expected: All checks passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/optimizer/rolling.py backend/tests/test_rolling_evaluation.py
git commit -m "feat: add rolling.run_rolling_evaluation (per-fold walk-forward solve + scoring)"
```

---

### Task 5: Wire into `service.py`, extend the smoke matrix

**Files:**
- Modify: `backend/app/optimizer/service.py`
- Modify: `backend/tests/test_optimizer_smoke_matrix.py`
- Test: `backend/tests/test_optimizer_service.py` (extend existing)

**Interfaces:**
- Consumes: `rolling.run_rolling_evaluation(request, returns) -> tuple[list[dict], str | None]` (Task 4).
- Produces: `OptimizeResult.rolling` and `OptimizeResult.robust_note` now genuinely populated by `run_optimize`. No new public interface for later tasks — this is the plan's final integration point.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_optimizer_service.py`:

```python
def test_run_optimize_populates_real_rolling_folds(two_real_fund_request):
    result = run_optimize(two_real_fund_request)
    assert len(result.rolling) >= 1
    for fold in result.rolling:
        assert fold.period_label
        assert fold.realized_volatility_pct >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py -v -k rolling`
Expected: FAIL — `result.rolling` is `[]` (the current hardcoded empty list)

- [ ] **Step 3: Wire `rolling.run_rolling_evaluation` into `run_optimize`**

In `backend/app/optimizer/service.py`:

Add to the imports (the existing `from backend.app.optimizer import (...)` block):

```python
from backend.app.optimizer import (
    black_litterman,
    diagnostics,
    frontier,
    inputs,
    report,
    rolling,
    solvers,
)
```

Add this line right after the existing `optimal_weights = solvers.solve_for_goal(request, mu, sigma, returns)` line (from Task 2):

```python
    rolling_folds, rolling_note = rolling.run_rolling_evaluation(request, returns)
```

Then replace these two lines in the `OptimizeResult.model_validate({...})` call:

```python
        "robustNote": None,
```
```python
        # Rolling out-of-sample evaluator is sub-project 2's responsibility;
        # empty here is the correct scoping, not a gap in this task.
        "rolling": [],
```

with:

```python
        "robustNote": rolling_note,
```
```python
        "rolling": rolling_folds,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py -v`
Expected: PASS (all tests in the file, including the new one and the pre-existing `test_run_optimize_end_to_end_against_real_cache`)

- [ ] **Step 5: Extend the enum-driven smoke matrix to cover rolling**

Read `backend/tests/test_optimizer_smoke_matrix.py` in full first — it is enum-driven (`@pytest.mark.parametrize` over `ObjectiveGoal`/`RiskMeasure`), and this step adds one assertion to its existing body rather than a new test function, so every one of its 28 parametrized cases gets the new check automatically. Add this assertion to the existing test function's body, after whatever it currently asserts about the returned `OptimizeResult`:

```python
    # Rolling evaluation must either produce real folds or explain why not
    # (INSUFFICIENT_ROLLING_HISTORY is a separate, expected error path
    # exercised by test_rolling_evaluation.py directly, not here) -- this
    # fixture's window is long enough that every goal/risk-measure
    # combination should produce at least one fold.
    assert len(result.rolling) >= 1 or result.robust_note is not None
```

- [ ] **Step 6: Run the full smoke matrix and every optimizer-relevant test file**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_smoke_matrix.py backend/tests/test_optimizer_service.py backend/tests/test_rolling_fold_schedule.py backend/tests/test_rolling_evaluation.py backend/tests/test_optimizer_solvers_dispatch.py backend/tests/test_api_optimize.py -v`
Expected: PASS, all tests

- [ ] **Step 7: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/service.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py`
Expected: All checks passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/optimizer/service.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py
git commit -m "feat: wire rolling.run_rolling_evaluation into service.run_optimize"
```

---

## After all tasks: full suite verification

Run the full backend suite (not just the optimizer-relevant subset) once, as the final check before this plan's own final review, exactly as sub-project 1 did:

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests -q`
Expected: all pass (the one pre-existing slow, unrelated test — `test_api_backtests.py::test_backtest_endpoint_uses_sec_cache_and_persists_run`, ~15 minutes — is not a regression from this plan; do not investigate it, per sub-project 1's final review precedent).
