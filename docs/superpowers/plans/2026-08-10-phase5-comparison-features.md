# Phase 5 sub-project 3: Comparison Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `POST /api/optimize`'s `OptimizeResult.compareWeights` and `OptimizeResult.benchmarkComparison` real — both are currently always `None` even when the request explicitly asks for a comparison.

**Architecture:** One new module, `backend/app/optimizer/comparison.py`, following the existing "orchestrator + pure functions per concern" shape: `build_comparison_weights` dispatches on `compareAgainst`'s 6 values (reusing `solvers.solve_for_goal` for `max_sharpe`/`risk_parity`, new formulas for `equal_weighted`/`inverse_volatility`, a direct pass-through for `current`), and `build_benchmark_comparison` loads an independent benchmark fund's NAV series and scores it via `backend/app/engine/metrics.py`'s real functions. `service.py` calls both once, after its existing single-shot solve.

**Tech Stack:** Python, pandas, the existing `backend/app/optimizer/*` modules (untouched except `inputs.py`'s refactor and `service.py`'s wiring), `backend/app/engine/metrics.py` (existing, untouched), pytest.

## Global Constraints

- Every comparison portfolio (`equal_weighted`/`max_sharpe`/`inverse_volatility`/`risk_parity`) respects the SAME fund bounds and long-only constraint as the main solve — never an unconstrained textbook baseline.
- `max_sharpe`/`risk_parity` comparisons reuse `solvers.solve_for_goal` exactly as-is (goal swapped via `request.model_copy(update={"goal": ...})`) — no new solving logic for those two.
- Benchmark data insufficient for the requested `time_period` → hard error, the WHOLE request fails with `ErrorCode.BENCHMARK_DATA_UNAVAILABLE`.
- A `compareAgainst` solve failure (e.g. `max_sharpe` infeasible on the comparison path) never fails the whole request — `compareWeights` becomes `None` with the reason in the new `compareNote` field, main solve result unaffected. This mirrors sub-project 2's non-blocking-secondary-feature principle for rolling-evaluation failures.
- `compareNote` is a NEW, separate field from `robustNote` — never reuse `robustNote` for comparison-specific caveats (three collided meanings in one field is the thing this decision avoids).
- Reuse `backend/app/engine/metrics.py`'s real `annualized_return`/`tracking_error` for benchmark scoring — never re-derived math.
- No new riskfolio-lib API usage, no new solver family — the only genuinely new math in this plan is the `equal_weighted`/`inverse_volatility` clamp-and-renormalize algorithm (pure numpy/dict arithmetic, no solver).
- Error responses extend the existing `AppHTTPException` + `ErrorCode` pattern — new errors raise `ValueError(<bare ErrorCode name>)`, the same convention every prior `ErrorCode` addition in this project uses, resolved by `api/optimize.py`'s existing dynamic `getattr(ErrorCode, str(exc))` lookup with no route code change.
- Use `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3` for all commands (`pytest`, `ruff`) — never a bare `python3`/`pytest`.
- Every new module/function gets tests verified against this plan's own Step commands before moving to the next task.

---

### Task 1: Add `ErrorCode.BENCHMARK_DATA_UNAVAILABLE`

**Files:**
- Modify: `backend/app/domain/enums.py`
- Test: `backend/tests/test_optimizer_errors.py`

**Interfaces:**
- Produces: `ErrorCode.BENCHMARK_DATA_UNAVAILABLE` — consumed by Task 3's `inputs.load_benchmark_returns` (raised as `ValueError("BENCHMARK_DATA_UNAVAILABLE")`) and resolved by `backend/app/api/optimize.py`'s existing dynamic lookup with no route change.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_optimizer_errors.py`:

```python
def test_benchmark_data_unavailable_error_code_exists():
    assert ErrorCode.BENCHMARK_DATA_UNAVAILABLE == "BENCHMARK_DATA_UNAVAILABLE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_errors.py -v`
Expected: FAIL with `AttributeError: BENCHMARK_DATA_UNAVAILABLE`

- [ ] **Step 3: Add the enum member**

In `backend/app/domain/enums.py`, add to `ErrorCode` (immediately after `INSUFFICIENT_ROLLING_HISTORY`):

```python
    INSUFFICIENT_ROLLING_HISTORY = "INSUFFICIENT_ROLLING_HISTORY"
    BENCHMARK_DATA_UNAVAILABLE = "BENCHMARK_DATA_UNAVAILABLE"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_errors.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/enums.py backend/tests/test_optimizer_errors.py
git commit -m "feat: add BENCHMARK_DATA_UNAVAILABLE error code"
```

---

### Task 2: Add `OptimizeResult.compareNote`

**Files:**
- Modify: `backend/app/domain/optimize_schemas.py`
- Test: `backend/tests/test_optimize_schemas.py`

**Interfaces:**
- Produces: `OptimizeResult.compare_note: str | None` (wire name `compareNote`) — consumed by Task 5's `service.py` wiring.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_optimize_schemas.py` (read the file first to match its existing fixture-construction style for a full valid `OptimizeResult` payload — reuse whatever helper/dict the file already has rather than rebuilding one from scratch):

```python
def test_optimize_result_accepts_compare_note():
    payload = _valid_optimize_result_payload()  # use the file's existing helper name
    payload["compareNote"] = "max_sharpe comparison could not converge"
    result = OptimizeResult.model_validate(payload)
    assert result.compare_note == "max_sharpe comparison could not converge"

    payload["compareNote"] = None
    result = OptimizeResult.model_validate(payload)
    assert result.compare_note is None
```

If the file has no existing "build a valid `OptimizeResult` payload" helper, check how its other tests construct one (likely inline dict literals) and adapt the pattern rather than inventing a new one.

- [ ] **Step 2: Run test to verify it fails**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimize_schemas.py -k compare_note -v`
Expected: FAIL — either a validation error (extra field not permitted, if the model forbids unknown fields) or an `AttributeError` on `result.compare_note`

- [ ] **Step 3: Add the field**

In `backend/app/domain/optimize_schemas.py`, add to `OptimizeResult` (immediately after `robust_note`):

```python
    robust_note: str | None
    compare_note: str | None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimize_schemas.py -v`
Expected: PASS (all tests in the file, including the new one)

- [ ] **Step 5: Run the full existing optimizer test suite to confirm no regression**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py backend/tests/test_api_optimize.py -v`
Expected: FAIL — `service.py`'s `OptimizeResult.model_validate({...})` call does not yet include a `"compareNote"` key, and `OptimizeResult` has no default for the new required field, so every existing call now errors with a missing-field validation error. This is expected and will be fixed in Task 5; do not fix it in this task.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/optimize_schemas.py backend/tests/test_optimize_schemas.py
git commit -m "feat: add OptimizeResult.compareNote field"
```

---

### Task 3: `inputs.py` — extract shared NAV-loading helper, add `load_benchmark_returns`

**Why this task exists:** `inputs.build_returns_panel` already loads-aligns-slices-validates a NAV panel for the request's optimized funds. Loading a benchmark fund's NAV needs the identical logic (same alignment, same window, same completeness validation) but for a single, possibly-different proj_id, and must raise a DIFFERENT error code (`BENCHMARK_DATA_UNAVAILABLE` instead of `INSUFFICIENT_NAV_HISTORY`) on failure. This task extracts the shared logic into one parameterized helper both call, so the two paths can never silently diverge — the same anti-drift principle that motivated `solvers.solve_for_goal`'s extraction in sub-project 2.

**Files:**
- Modify: `backend/app/optimizer/inputs.py`
- Test: `backend/tests/test_optimizer_inputs.py`

**Interfaces:**
- Produces: `inputs.load_benchmark_returns(benchmark_proj_id: str, request: OptimizeRequest) -> pd.Series` — a single-column return series (fractions, not percent) for the benchmark fund, aligned/sliced/validated identically to the main panel. Raises `ValueError("BENCHMARK_DATA_UNAVAILABLE")`. Consumed by Task 4's `comparison.build_benchmark_comparison`.
- `inputs.build_returns_panel`'s existing public signature and behavior are UNCHANGED — this task is a zero-behavior-change refactor of its internals plus one new function.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_optimizer_inputs.py`:

```python
def test_load_benchmark_returns_against_real_cache():
    from backend.app.optimizer.inputs import load_benchmark_returns

    request = OptimizeRequest.model_validate({
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
    # M0209_2548 is one of the fixture's own confirmed-present funds, used
    # here purely as a stand-in benchmark to prove the loader works against
    # the real cache -- nothing prevents a benchmark from also being one of
    # the optimized funds.
    series = load_benchmark_returns("M0209_2548", request)
    assert not series.empty
    assert series.index.is_monotonic_increasing


def test_load_benchmark_returns_raises_on_missing_fund(monkeypatch):
    import pandas as pd

    from backend.app.optimizer import inputs as inputs_module

    request = OptimizeRequest.model_validate({
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

    def fake_load_nav_panel(proj_ids):
        return pd.DataFrame()  # simulates a proj_id with zero cached NAV rows

    monkeypatch.setattr(inputs_module, "load_nav_panel", fake_load_nav_panel)
    with pytest.raises(ValueError, match="BENCHMARK_DATA_UNAVAILABLE"):
        load_benchmark_returns("NONEXISTENT_PROJ_ID", request)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_inputs.py -k benchmark -v`
Expected: FAIL with `ImportError: cannot import name 'load_benchmark_returns'`

- [ ] **Step 3: Extract the shared helper and add `load_benchmark_returns`**

In `backend/app/optimizer/inputs.py`, replace the current `build_returns_panel` function body with an extracted helper plus a thin wrapper, and add the new function. Read the current file first (it has other functions above/below this one — only this function changes):

```python
def _load_returns_for(proj_ids: list[str], request: OptimizeRequest, error_code: str) -> pd.DataFrame:
    """Load, align, and slice the NAV panel for the given proj_ids and the
    request's time period, then convert to simple period returns. Shared by
    build_returns_panel (the optimized funds) and load_benchmark_returns (an
    independent benchmark fund) so the two paths can never diverge -- only
    the raised error_code differs between callers.

    Raises ``ValueError(error_code)`` -- the bare ErrorCode name, the same
    convention every other raise site in this module uses -- when the
    aligned window is unusable. "Unusable" includes ANY missing
    observation, not just a proj_id that is entirely absent (see
    build_returns_panel's original docstring for why: a mid-window gap must
    never be forward-filled or interpolated).
    """
    # A missing parquet cache surfaces here as FileNotFoundError; it is left
    # to propagate so the API route can map it to NAV_CACHE_MISSING (503),
    # matching backend/app/api/backtests.py's handling of the same case.
    nav = align_nav_panel(load_nav_panel(proj_ids), frequency=request.data_frequency.value)
    window = nav.loc[pd.Timestamp(request.time_period.start_date):pd.Timestamp(request.time_period.end_date), proj_ids]
    if window.empty or window.isna().to_numpy().any():
        raise ValueError(error_code)
    issues = validate_nav_panel(window, as_of=pd.Timestamp(request.time_period.end_date))
    if any(issue["severity"] == "error" for issue in issues):
        raise ValueError(error_code)
    returns = window.pct_change().dropna(how="all")
    if returns.empty:
        raise ValueError(error_code)
    return returns


def build_returns_panel(request: OptimizeRequest) -> pd.DataFrame:
    """Load, align, and slice the NAV panel for the request's funds and
    time period, then convert to simple period returns. See
    _load_returns_for for the shared implementation and error-raising
    convention (this wrapper always raises "INSUFFICIENT_NAV_HISTORY")."""
    proj_ids = [fund.proj_id for fund in request.funds]
    return _load_returns_for(proj_ids, request, "INSUFFICIENT_NAV_HISTORY")


def load_benchmark_returns(benchmark_proj_id: str, request: OptimizeRequest) -> pd.Series:
    """The benchmark fund's own return series, aligned and validated
    identically to the optimized funds' panel via _load_returns_for, but
    raising "BENCHMARK_DATA_UNAVAILABLE" instead of
    "INSUFFICIENT_NAV_HISTORY" on failure -- per this project's decision,
    insufficient benchmark data is a hard error for the whole request, not
    a degrade-gracefully case."""
    panel = _load_returns_for([benchmark_proj_id], request, "BENCHMARK_DATA_UNAVAILABLE")
    return panel[benchmark_proj_id]
```

Do not change anything else in the file — `periods_per_year`, `build_mu_sigma`, `portfolio_return_series` (if already present from sub-project 2) are untouched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_inputs.py -v`
Expected: PASS (all tests in the file, including the 2 new ones)

- [ ] **Step 5: Run the full existing optimizer test suite to confirm no regression from the refactor**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py backend/tests/test_rolling_evaluation.py backend/tests/test_optimizer_smoke_matrix.py -v -k "not compare"`
Expected: same failures as Task 2 left behind (missing `compareNote` key), and otherwise no NEW failures — `build_returns_panel`'s behavior must be byte-identical to before this refactor.

- [ ] **Step 6: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/inputs.py backend/tests/test_optimizer_inputs.py`
Expected: All checks passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/optimizer/inputs.py backend/tests/test_optimizer_inputs.py
git commit -m "refactor: extract shared NAV-loading helper, add inputs.load_benchmark_returns"
```

---

### Task 4: `comparison.py` — `build_comparison_weights` (all 6 `compareAgainst` values)

**Files:**
- Create: `backend/app/optimizer/comparison.py`
- Test: `backend/tests/test_comparison.py`

**Interfaces:**
- Consumes: `solvers.solve_for_goal(request, mu, sigma, returns) -> dict[str, float]` (existing), `solvers._asset_bounds(request, proj_ids) -> tuple[list[float], list[float]]` (existing, private but same-package import is fine — `frontier.py` already imports private helpers from `solvers.py` this way).
- Produces: `comparison.build_comparison_weights(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame) -> tuple[dict[str, float] | None, str | None]` — weights dict (or `None`) plus an optional note explaining why weights are `None`. Consumed by Task 6's `service.py` wiring.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_comparison.py`:

```python
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.comparison import _clamp_and_renormalize, build_comparison_weights


def test_clamp_and_renormalize_respects_a_tight_cap():
    # 3 equal-raw-share funds, A capped at 20% (below its 1/3 raw share) --
    # hand-computed expected result: A pins at its cap, remaining 80% of
    # the budget splits evenly across B and C (40% each).
    raw = {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}
    lower = [0.0, 0.0, 0.0]
    upper = [0.20, 1.0, 1.0]
    result = _clamp_and_renormalize(raw, lower, upper, ["A", "B", "C"])
    assert result["A"] == pytest.approx(20.0, abs=0.01)
    assert result["B"] == pytest.approx(40.0, abs=0.01)
    assert result["C"] == pytest.approx(40.0, abs=0.01)
    assert sum(result.values()) == pytest.approx(100.0, abs=0.01)


def test_clamp_and_renormalize_is_a_no_op_when_no_bound_binds():
    raw = {"A": 0.5, "B": 0.3, "C": 0.2}
    lower = [0.0, 0.0, 0.0]
    upper = [1.0, 1.0, 1.0]
    result = _clamp_and_renormalize(raw, lower, upper, ["A", "B", "C"])
    assert result["A"] == pytest.approx(50.0, abs=0.01)
    assert result["B"] == pytest.approx(30.0, abs=0.01)
    assert result["C"] == pytest.approx(20.0, abs=0.01)


@pytest.fixture
def two_real_fund_request_factory():
    def make(compare_against: str, current_weight_pct: dict | None = None):
        return OptimizeRequest.model_validate({
            "funds": [
                {"projId": "M0209_2548", "displayName": "K-SET50"},
                {"projId": "M0155_2547", "displayName": "M-S50"},
            ],
            "fundBounds": {}, "currentWeightPct": current_weight_pct or {}, "fundGroups": {},
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
                "riskFreeRatePct": 1.5, "compareAgainst": compare_against,
                "maxTurnoverPct": None, "maxTrackingErrorPct": None,
            },
        })
    return make


@pytest.mark.parametrize("compare_against", ["equal_weighted", "max_sharpe", "inverse_volatility", "risk_parity"])
def test_build_comparison_weights_against_real_cache(two_real_fund_request_factory, compare_against):
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    request = two_real_fund_request_factory(compare_against)
    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    weights, note = build_comparison_weights(request, mu, sigma, returns)
    assert weights is not None
    assert note is None
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_build_comparison_weights_none_returns_none():
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    request = OptimizeRequest.model_validate({
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
    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    weights, note = build_comparison_weights(request, mu, sigma, returns)
    assert weights is None
    assert note is None


def test_build_comparison_weights_current_with_no_holdings_returns_none(two_real_fund_request_factory):
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    request = two_real_fund_request_factory("current", current_weight_pct={})
    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    weights, note = build_comparison_weights(request, mu, sigma, returns)
    assert weights is None
    assert note is None


def test_build_comparison_weights_current_with_holdings(two_real_fund_request_factory):
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    request = two_real_fund_request_factory("current", current_weight_pct={"M0209_2548": 60.0, "M0155_2547": 40.0})
    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    weights, note = build_comparison_weights(request, mu, sigma, returns)
    assert weights == {"M0209_2548": 60.0, "M0155_2547": 40.0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_comparison.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.optimizer.comparison'`

- [ ] **Step 3: Create `comparison.py` with the clamp helper and `build_comparison_weights`**

Create `backend/app/optimizer/comparison.py`:

```python
"""Comparison-portfolio computation for compareAgainst and
benchmarkProjId. See
docs/superpowers/specs/2026-08-10-phase5-comparison-features-design.md for
the full design (why every comparison respects the same fund bounds as the
main solve, why a comparison failure never fails the whole request).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer import solvers


def _clamp_and_renormalize(
    raw: dict[str, float], lower: list[float], upper: list[float], proj_ids: list[str]
) -> dict[str, float]:
    """Water-filling clamp: distributes 1.0 of budget proportionally to
    `raw`'s relative shares, pinning any fund that would exceed its bound
    to that bound and redistributing the remainder among the still-free
    funds, one violation at a time until none remain. Returns percentages
    (0..100) summing to 100, not fractions.

    Example: 3 equal-raw-share funds, A capped at 20% (below its 1/3 raw
    share) -> A pins at 20%, remaining 80% splits evenly across B/C (40%
    each) -- see test_clamp_and_renormalize_respects_a_tight_cap.
    """
    w = {pid: max(raw.get(pid, 0.0), 0.0) for pid in proj_ids}
    lo = dict(zip(proj_ids, lower))
    hi = dict(zip(proj_ids, upper))
    fixed_total = 0.0
    free = set(proj_ids)
    for _ in range(len(proj_ids)):
        remaining_budget = 1.0 - fixed_total
        free_raw_sum = sum(w[p] for p in free)
        if free_raw_sum > 0:
            share = {p: w[p] / free_raw_sum * remaining_budget for p in free}
        else:
            share = {p: remaining_budget / len(free) for p in free} if free else {}
        violator = None
        for p in free:
            if share[p] > hi[p] + 1e-9:
                violator = (p, hi[p])
                break
            if share[p] < lo[p] - 1e-9:
                violator = (p, lo[p])
                break
        if violator is None:
            for p in free:
                w[p] = share[p]
            break
        p, bound = violator
        w[p] = bound
        fixed_total += bound
        free.discard(p)
    return {pid: round(w[pid] * 100, 4) for pid in proj_ids}


def _equal_weighted_weights(request: OptimizeRequest, proj_ids: list[str]) -> dict[str, float]:
    raw = {pid: 1.0 / len(proj_ids) for pid in proj_ids}
    lower, upper = solvers._asset_bounds(request, proj_ids)
    return _clamp_and_renormalize(raw, lower, upper, proj_ids)


def _inverse_volatility_weights(request: OptimizeRequest, sigma: pd.DataFrame, proj_ids: list[str]) -> dict[str, float]:
    vol = pd.Series(sigma.values.diagonal(), index=sigma.index) ** 0.5
    inv_vol = {pid: (1.0 / vol[pid] if vol[pid] > 0 else 0.0) for pid in proj_ids}
    total = sum(inv_vol.values())
    raw = {pid: (inv_vol[pid] / total if total > 0 else 1.0 / len(proj_ids)) for pid in proj_ids}
    lower, upper = solvers._asset_bounds(request, proj_ids)
    return _clamp_and_renormalize(raw, lower, upper, proj_ids)


def build_comparison_weights(
    request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame
) -> tuple[dict[str, float] | None, str | None]:
    """Dispatches on request.constraints.compare_against. Returns
    (weights, note) -- note is only non-None when compare_against was
    requested but weights could not be produced (a solve failure on the
    comparison path never fails the whole request, per this project's
    non-blocking-secondary-feature principle)."""
    compare_against = request.constraints.compare_against.value
    proj_ids = list(mu.index)

    if compare_against == "none":
        return None, None

    if compare_against == "current":
        if not request.current_weight_pct:
            return None, None
        return dict(request.current_weight_pct), None

    if compare_against == "equal_weighted":
        return _equal_weighted_weights(request, proj_ids), None

    if compare_against == "inverse_volatility":
        return _inverse_volatility_weights(request, sigma, proj_ids), None

    # max_sharpe / risk_parity: reuse the exact same dispatch the main
    # solve uses, with only the goal swapped -- same mu/sigma/returns/
    # constraints, so the comparison is genuinely apples-to-apples.
    alt_request = request.model_copy(update={"goal": compare_against})
    try:
        return solvers.solve_for_goal(alt_request, mu, sigma, returns), None
    except (ValueError, RuntimeError) as exc:
        return None, f"Comparison against {compare_against} could not be computed: {exc}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_comparison.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/comparison.py backend/tests/test_comparison.py`
Expected: All checks passed (if ruff flags the private `solvers._asset_bounds` import, check how `frontier.py` imports `solvers._build_portfolio` for the established pattern and match it — this is an intentional, existing same-package convention, not a new violation)

- [ ] **Step 6: Commit**

```bash
git add backend/app/optimizer/comparison.py backend/tests/test_comparison.py
git commit -m "feat: add comparison.build_comparison_weights (all 6 compareAgainst values)"
```

---

### Task 5: `comparison.py` — `build_benchmark_comparison`

**Files:**
- Modify: `backend/app/optimizer/comparison.py` (add `build_benchmark_comparison`)
- Test: `backend/tests/test_comparison.py` (extend)

**Interfaces:**
- Consumes: `inputs.load_benchmark_returns(benchmark_proj_id, request) -> pd.Series` (Task 3), `inputs.portfolio_return_series(returns, weights) -> pd.Series` (existing, from sub-project 2), `metrics.annualized_return`/`metrics.tracking_error` (existing).
- Produces: `comparison.build_benchmark_comparison(request: OptimizeRequest, optimal_weights: dict[str, float], returns: pd.DataFrame) -> dict | None` — a dict shaped exactly like `BenchmarkComparison`'s camelCase fields (`projId`, `displayName`, `trackingErrorPct`, `excessReturnPct`), or `None` when `request.benchmark_proj_id` is unset. Consumed by Task 6's `service.py` wiring.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_comparison.py`:

```python
def test_build_benchmark_comparison_none_when_unset(two_real_fund_request_factory):
    from backend.app.optimizer.comparison import build_benchmark_comparison
    from backend.app.optimizer.inputs import build_returns_panel

    request = two_real_fund_request_factory("none")
    returns = build_returns_panel(request)
    result = build_benchmark_comparison(request, {"M0209_2548": 60.0, "M0155_2547": 40.0}, returns)
    assert result is None


def test_build_benchmark_comparison_against_real_cache(two_real_fund_request_factory):
    from backend.app.optimizer.comparison import build_benchmark_comparison
    from backend.app.optimizer.inputs import build_returns_panel, load_benchmark_returns, portfolio_return_series
    from backend.app.engine import metrics

    request = two_real_fund_request_factory("none")
    request = request.model_copy(update={"benchmarkProjId": "M0209_2548"})
    returns = build_returns_panel(request)
    optimal_weights = {"M0209_2548": 60.0, "M0155_2547": 40.0}

    result = build_benchmark_comparison(request, optimal_weights, returns)
    assert result is not None
    assert result["projId"] == "M0209_2548"
    assert result["displayName"] == "K-SET50"

    # Independently recompute both scored fields by hand via the same real
    # engine/metrics.py functions, proving the numbers are genuinely
    # computed -- not a placeholder, the exact defect class earlier
    # sub-projects' final reviews caught in fabricated fields.
    benchmark_returns = load_benchmark_returns("M0209_2548", request)
    portfolio_returns = portfolio_return_series(returns, optimal_weights)
    ppy = 12
    expected_excess = (
        metrics.annualized_return(portfolio_returns, ppy) - metrics.annualized_return(benchmark_returns, ppy)
    ) * 100
    expected_tracking_error = metrics.tracking_error(portfolio_returns, benchmark_returns, ppy) * 100
    assert result["excessReturnPct"] == pytest.approx(expected_excess, abs=0.01)
    assert result["trackingErrorPct"] == pytest.approx(expected_tracking_error, abs=0.01)


def test_build_benchmark_comparison_propagates_hard_error_on_missing_data(two_real_fund_request_factory, monkeypatch):
    from backend.app.optimizer import inputs as inputs_module
    from backend.app.optimizer.comparison import build_benchmark_comparison
    from backend.app.optimizer.inputs import build_returns_panel

    request = two_real_fund_request_factory("none")
    request = request.model_copy(update={"benchmarkProjId": "NONEXISTENT_PROJ_ID"})
    returns = build_returns_panel(request)

    def fake_load_nav_panel(proj_ids):
        import pandas as pd
        return pd.DataFrame()

    monkeypatch.setattr(inputs_module, "load_nav_panel", fake_load_nav_panel)
    with pytest.raises(ValueError, match="BENCHMARK_DATA_UNAVAILABLE"):
        build_benchmark_comparison(request, {"M0209_2548": 60.0, "M0155_2547": 40.0}, returns)


def test_build_benchmark_comparison_display_name_falls_back_to_universe_csv(two_real_fund_request_factory):
    from backend.app.optimizer.comparison import build_benchmark_comparison
    from backend.app.optimizer.inputs import build_returns_panel

    # M0155_2547 is NOT in this request's funds list, so its display name
    # must come from the mvp_fund_universe.csv lookup, not request.funds.
    request = two_real_fund_request_factory("none")
    request = OptimizeRequest.model_validate({
        **request.model_dump(by_alias=True),
        "funds": [{"projId": "M0209_2548", "displayName": "K-SET50"}],
        "benchmarkProjId": "M0155_2547",
    })
    returns = build_returns_panel(request.model_copy(update={"funds": request.funds}))
    result = build_benchmark_comparison(request, {"M0209_2548": 100.0}, returns)
    assert result is not None
    assert result["projId"] == "M0155_2547"
    assert result["displayName"]  # non-empty; exact text depends on the committed CSV, don't hardcode it
```

If constructing the third test's request via `model_dump`/re-`model_validate` round-trip is awkward given `OptimizeRequest`'s real validators (e.g. the duplicate-proj_id check), simplify by building the request dict inline from scratch (copy the pattern from `two_real_fund_request_factory` and just set `funds` to a single-fund list and `benchmarkProjId` directly) rather than fighting a round-trip — the point of the test is only that a benchmark proj_id outside `request.funds` still resolves a display name.

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_comparison.py -k benchmark -v`
Expected: FAIL with `ImportError: cannot import name 'build_benchmark_comparison'`

- [ ] **Step 3: Add `build_benchmark_comparison`**

Add to `backend/app/optimizer/comparison.py` (append; add imports as needed at the top — `Path`, `pandas as pd` for the CSV read, and the two new `inputs`/`metrics` functions):

```python
from pathlib import Path

from backend.app.engine import metrics
from backend.app.optimizer import inputs

_UNIVERSE_PATH = Path("data/sec/mvp_fund_universe.csv")


def _resolve_display_name(proj_id: str, request: OptimizeRequest) -> str:
    """The benchmark fund's display name, preferring request.funds (already
    client-supplied, no I/O) and falling back to the same
    mvp_fund_universe.csv backend/app/api/funds.py reads for the fund
    picker -- a benchmark is not necessarily one of the optimized funds, so
    request.funds alone cannot always resolve it."""
    for fund in request.funds:
        if fund.proj_id == proj_id:
            return fund.display_name
    if _UNIVERSE_PATH.exists():
        universe = pd.read_csv(_UNIVERSE_PATH)
        match = universe.loc[universe["proj_id"] == proj_id, "display_name"]
        if not match.empty:
            return str(match.iloc[0])
    return proj_id


def build_benchmark_comparison(
    request: OptimizeRequest, optimal_weights: dict[str, float], returns: pd.DataFrame
) -> dict | None:
    """None when no benchmark was requested. Otherwise loads the
    benchmark's own return series (inputs.load_benchmark_returns --
    raises ValueError("BENCHMARK_DATA_UNAVAILABLE") on insufficient data,
    a hard error for the whole request per this project's decision, so
    that propagates uncaught here rather than being swallowed) and scores
    it against the optimized portfolio's realized return series via
    backend/app/engine/metrics.py's real functions."""
    benchmark_proj_id = request.benchmark_proj_id
    if not benchmark_proj_id:
        return None

    benchmark_returns = inputs.load_benchmark_returns(benchmark_proj_id, request)
    portfolio_returns = inputs.portfolio_return_series(returns, optimal_weights)
    ppy = inputs.periods_per_year(request)

    excess_return_pct = (
        metrics.annualized_return(portfolio_returns, ppy) - metrics.annualized_return(benchmark_returns, ppy)
    ) * 100
    tracking_error_pct = metrics.tracking_error(portfolio_returns, benchmark_returns, ppy) * 100

    return {
        "projId": benchmark_proj_id,
        "displayName": _resolve_display_name(benchmark_proj_id, request),
        "trackingErrorPct": round(tracking_error_pct, 2),
        "excessReturnPct": round(excess_return_pct, 2),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_comparison.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/comparison.py backend/tests/test_comparison.py`
Expected: All checks passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/optimizer/comparison.py backend/tests/test_comparison.py
git commit -m "feat: add comparison.build_benchmark_comparison"
```

---

### Task 6: Wire into `service.py`, populate `selectedRiskMeasure.comparedValue`, extend the smoke matrix

**Files:**
- Modify: `backend/app/optimizer/service.py`
- Modify: `backend/tests/test_optimizer_smoke_matrix.py`
- Test: `backend/tests/test_optimizer_service.py` (extend)

**Interfaces:**
- Consumes: `comparison.build_comparison_weights(request, mu, sigma, returns) -> tuple[dict | None, str | None]` (Task 4), `comparison.build_benchmark_comparison(request, optimal_weights, returns) -> dict | None` (Task 5), `solvers.realized_risk(request, weights, sigma, returns, periods_per_year) -> tuple[float, bool]` (existing).
- Produces: `OptimizeResult.compareWeights`, `.compareNote`, `.benchmarkComparison`, and `.selectedRiskMeasure.comparedValue` now genuinely populated. No new public interface for later tasks — this is this plan's final integration point.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_optimizer_service.py`:

```python
def test_run_optimize_populates_real_compare_weights(two_real_fund_request):
    two_real_fund_request.constraints.compare_against = "equal_weighted"
    result = run_optimize(two_real_fund_request)
    assert result.compare_weights is not None
    assert sum(result.compare_weights.values()) == pytest.approx(100, abs=0.5)
    assert result.compare_note is None
    assert result.selected_risk_measure.compared_value is not None


def test_run_optimize_populates_real_benchmark_comparison(two_real_fund_request):
    two_real_fund_request.benchmark_proj_id = "M0209_2548"
    result = run_optimize(two_real_fund_request)
    assert result.benchmark_comparison is not None
    assert result.benchmark_comparison.proj_id == "M0209_2548"
```

If `two_real_fund_request`'s fields are not directly assignable (check whether `OptimizeRequest`/`OptimizeConstraints` are frozen Pydantic models by trying it — the fixture already exists in this file from sub-project 2), construct a second request via `two_real_fund_request.model_copy(update={...})` (top-level fields) or rebuild the nested `constraints` object with `model_copy` for `compare_against` instead of direct attribute assignment.

- [ ] **Step 2: Run test to verify it fails**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py -v -k compare`
Expected: FAIL — `result.compare_weights` is `None` and `OptimizeResult.model_validate` in `service.py` still errors on the missing `compareNote` key (left broken since Task 2, by design)

- [ ] **Step 3: Wire both `comparison.py` functions into `run_optimize`**

In `backend/app/optimizer/service.py`:

Add to the imports (the existing `from backend.app.optimizer import (...)` block):

```python
from backend.app.optimizer import (
    black_litterman,
    comparison,
    diagnostics,
    frontier,
    inputs,
    report,
    rolling,
    solvers,
)
```

Add these lines right after the existing `rolling_folds, rolling_note = ...` try/except block (before `frontier_points = frontier.build_frontier(...)`):

```python
    compare_weights, compare_note = comparison.build_comparison_weights(request, mu, sigma, returns)
    benchmark_comparison = comparison.build_benchmark_comparison(request, optimal_weights, returns)

    compared_risk_value = None
    if compare_weights is not None:
        compared_risk_value, _ = solvers.realized_risk(request, compare_weights, sigma, returns, inputs.periods_per_year(request))
```

Then update the `OptimizeResult.model_validate({...})` call:

Replace:
```python
        "compareWeights": None,
```
with:
```python
        "compareWeights": compare_weights,
        "compareNote": compare_note,
```

Replace:
```python
        "benchmarkComparison": None,
```
with:
```python
        "benchmarkComparison": benchmark_comparison,
```

Replace:
```python
            "comparedValue": None,
```
with:
```python
            "comparedValue": round(compared_risk_value, 2) if compared_risk_value is not None else None,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Extend the enum-driven smoke matrix to cover comparison**

Read `backend/tests/test_optimizer_smoke_matrix.py` in full first (it is enum-driven, parametrized over `ObjectiveGoal` × `RiskMeasure`, 28 cases). Add this assertion to the existing test function's body, after whatever it currently asserts:

```python
    # A non-none compareAgainst must produce real compareWeights for every
    # goal/risk-measure combination -- not left blank the way an earlier
    # sub-project's smoke matrix let a real bug hide behind a too-weak
    # assertion (see the rolling-evaluator final review's finding).
    if request.constraints.compare_against.value != "none":
        assert result.compare_weights is not None
```

If the existing fixture request in this test file has `compareAgainst` set to `"none"` (check its construction), change it to `"equal_weighted"` so the new assertion actually exercises the real path across all 28 parametrized cases rather than trivially passing because the condition never triggers.

- [ ] **Step 6: Run the full comparison-relevant test set**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_comparison.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py backend/tests/test_optimizer_inputs.py backend/tests/test_optimize_schemas.py backend/tests/test_optimizer_errors.py backend/tests/test_api_optimize.py -v`
Expected: PASS, all tests

- [ ] **Step 7: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/service.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py`
Expected: All checks passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/optimizer/service.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py
git commit -m "feat: wire comparison.py into service.run_optimize"
```

---

## After all tasks: full suite verification

Run the full backend suite once, as the final check before this plan's own final review:

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests -q`
Expected: all pass (the one pre-existing slow, unrelated test — `test_api_backtests.py::test_backtest_endpoint_uses_sec_cache_and_persists_run`, ~15 minutes — is not a regression from this plan; do not investigate it, per sub-project 1/2's final review precedent).
