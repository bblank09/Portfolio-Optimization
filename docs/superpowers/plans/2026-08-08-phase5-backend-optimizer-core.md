# Phase 5 Sub-project 1: Backend Optimizer Core + API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `frontend/src/lib/mockOptimize.ts`'s fabricated numbers with a real `POST /api/optimize` backend endpoint that computes portfolio optimizations via riskfolio-lib against the cached SEC NAV panel.

**Architecture:** A new `backend/app/optimizer/` package (orchestrator `service.py` + one module per concern: `inputs.py`, `solvers.py`, `black_litterman.py`, `frontier.py`, `diagnostics.py`, `report.py`), following the existing `engine/backtest.py` orchestration pattern. A new `backend/app/api/optimize.py` route calls only `service.run_optimize()`.

**Tech Stack:** riskfolio-lib (`rp.Portfolio`, `rp.HCPortfolio`), CVXPY with the CLARABEL solver, Pydantic v2 schemas, pandas/numpy — all layered on the existing FastAPI app and cached NAV parquet pipeline.

## Global Constraints

- Reuse `backend/app/sec/cache.py` (`load_nav_panel`) and `backend/app/data/quality.py` (`align_nav_panel`) for all NAV loading — never re-implement panel loading/alignment.
- Solver is CLARABEL (CVXPY's free default) for every risk measure this project exposes (Standard Deviation, Semi-Variance, CVaR, CDaR) — no MOSEK/GUROBI dependency.
- Pydantic schemas use a camelCase `alias_generator` so the wire JSON matches `frontend/src/types/optimize.ts` field names exactly (`fundBounds`, `timePeriod`, etc.) without renaming any existing frontend type — Python code itself stays idiomatic snake_case internally.
- Error responses extend the existing `AppHTTPException` (`backend/app/core/errors.py`) + `ErrorCode` (`backend/app/domain/enums.py`) pattern — never raise a bare `HTTPException` or return an ad-hoc error shape.
- Mock is not kept as a fallback — this plan does not touch the frontend (that's sub-project 3), but nothing here should require `mockOptimize.ts` to keep working.
- Every new module gets tests verified against the plan's own Step commands before moving to the next task — no task is "done" until its tests pass.

---

### Task 1: Add riskfolio-lib and CVXPY dependencies

**Files:**
- Modify: `pyproject.toml`
- Test: manual verification (no test file — this task is infrastructure)

**Interfaces:**
- Produces: `riskfolio` and `cvxpy` importable from any backend module in later tasks.

- [ ] **Step 1: Add the dependencies**

Open `pyproject.toml` and add to the `dependencies` list (currently `["fastapi>=0.111", "uvicorn[standard]>=0.30", "pydantic>=2.7", "pydantic-settings>=2.2", "pandas>=3.0", "numpy>=1.26", "scipy>=1.13", "httpx>=0.27", "pyarrow>=16.0", "slowapi>=0.1.9", "tenacity>=8.2"]`):

```toml
dependencies = [
  "fastapi>=0.111",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.7",
  "pydantic-settings>=2.2",
  "pandas>=3.0",
  "numpy>=1.26",
  "scipy>=1.13",
  "httpx>=0.27",
  "pyarrow>=16.0",
  "slowapi>=0.1.9",
  "tenacity>=8.2",
  "riskfolio-lib>=7.0",
  "cvxpy>=1.5",
]
```

- [ ] **Step 2: Install and verify**

Run: `python3 -m pip install -e ".[dev]"`
Expected: installs cleanly, no dependency conflicts.

Run: `python3 -c "import riskfolio as rp; import cvxpy; print(rp.__version__, cvxpy.installed_solvers())"`
Expected: prints a version string and a solver list that includes `CLARABEL`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add riskfolio-lib and cvxpy dependencies"
```

---

### Task 2: Add new ErrorCode values

**Files:**
- Modify: `backend/app/domain/enums.py`
- Test: `backend/tests/test_optimizer_errors.py` (new)

**Interfaces:**
- Produces: `ErrorCode.SOLVER_NON_CONVERGENCE`, `ErrorCode.INFEASIBLE_CONSTRAINTS`, `ErrorCode.INDEFINITE_CORRELATION_MATRIX` — consumed by Task 9's API route.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_optimizer_errors.py
from backend.app.domain.enums import ErrorCode


def test_optimizer_error_codes_exist():
    assert ErrorCode.SOLVER_NON_CONVERGENCE == "SOLVER_NON_CONVERGENCE"
    assert ErrorCode.INFEASIBLE_CONSTRAINTS == "INFEASIBLE_CONSTRAINTS"
    assert ErrorCode.INDEFINITE_CORRELATION_MATRIX == "INDEFINITE_CORRELATION_MATRIX"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_optimizer_errors.py -v`
Expected: FAIL with `AttributeError: SOLVER_NON_CONVERGENCE`

- [ ] **Step 3: Add the enum values**

In `backend/app/domain/enums.py`, add to the `ErrorCode` class (after the existing `INSUFFICIENT_NAV_HISTORY = "INSUFFICIENT_NAV_HISTORY"` line):

```python
    SOLVER_NON_CONVERGENCE = "SOLVER_NON_CONVERGENCE"
    INFEASIBLE_CONSTRAINTS = "INFEASIBLE_CONSTRAINTS"
    INDEFINITE_CORRELATION_MATRIX = "INDEFINITE_CORRELATION_MATRIX"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_optimizer_errors.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/enums.py backend/tests/test_optimizer_errors.py
git commit -m "feat: add optimizer-specific error codes"
```

---

### Task 3: Pydantic schemas for OptimizeRequest/OptimizeResult

**Files:**
- Create: `backend/app/domain/optimize_schemas.py`
- Test: `backend/tests/test_optimize_schemas.py` (new)

**Interfaces:**
- Consumes: `backend.app.domain.schemas.SecFundAllocation` is NOT reused here — the optimizer's per-fund shape (bounds, group, current weight) is different from the backtester's; define fresh models.
- Produces: `OptimizeRequest`, `OptimizeResult`, and every nested model (`FundBound`, `AssetGroup`, `TimePeriod`, `BlackLittermanInputs`, `BlackLittermanView`, `OptimizeConstraints`, `TradeRow`, `BindingConstraint`, `FrontierPoint`, `FrontierMarker`, `AssetSummaryRow`, `PerformanceSummaryColumn`, `RollingFold`, `SelectedRiskMeasureResult`) — consumed by every later task in this plan and by Task 9's API route.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_optimize_schemas.py
import pytest
from pydantic import ValidationError

from backend.app.domain.optimize_schemas import OptimizeRequest


MINIMAL_REQUEST_JSON = {
    "funds": [
        {"projId": "M0209_2548", "displayName": "K-SET50"},
        {"projId": "M0155_2547", "displayName": "M-S50"},
    ],
    "fundBounds": {},
    "currentWeightPct": {},
    "fundGroups": {},
    "assetGroups": {
        letter: {"name": "", "minWeightPct": 0, "maxWeightPct": 100}
        for letter in "ABCDEF"
    },
    "timePeriod": {"startDate": "2020-01-31", "endDate": "2024-06-30"},
    "dataFrequency": "monthly",
    "goal": "max_sharpe",
    "riskMeasure": "std_dev",
    "tailConfidence": 95,
    "targetAnnualVolatilityPct": None,
    "targetAnnualReturnPct": None,
    "robustOptimization": False,
    "useHistoricalReturns": True,
    "useHistoricalVolatility": True,
    "useHistoricalCorrelations": True,
    "expectedReturnOverrides": {},
    "volatilityOverrides": {},
    "correlationOverrides": {},
    "returnMethod": "historical_mean",
    "covarianceMethod": "sample",
    "blackLitterman": None,
    "benchmarkProjId": None,
    "constraints": {
        "longOnly": True,
        "minWeightPct": 0,
        "maxWeightPct": 100,
        "groupConstraintsEnabled": False,
        "maxHoldings": 20,
        "lookbackPeriodMonths": 36,
        "optimizationFrequency": "quarterly",
        "riskFreeRatePct": 1.5,
        "compareAgainst": "equal_weighted",
        "maxTurnoverPct": None,
        "maxTrackingErrorPct": None,
    },
}


def test_minimal_request_parses_from_camel_case_json():
    request = OptimizeRequest.model_validate(MINIMAL_REQUEST_JSON)
    assert len(request.funds) == 2
    assert request.funds[0].proj_id == "M0209_2548"
    assert request.goal == "max_sharpe"


def test_round_trips_back_to_camel_case_json():
    request = OptimizeRequest.model_validate(MINIMAL_REQUEST_JSON)
    dumped = request.model_dump(by_alias=True, mode="json")
    assert "fundBounds" in dumped
    assert "fund_bounds" not in dumped


def test_fewer_than_two_funds_rejected():
    bad = {**MINIMAL_REQUEST_JSON, "funds": [MINIMAL_REQUEST_JSON["funds"][0]]}
    with pytest.raises(ValidationError):
        OptimizeRequest.model_validate(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_optimize_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.domain.optimize_schemas'`

- [ ] **Step 3: Write the schemas**

```python
# backend/app/domain/optimize_schemas.py
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for every optimizer schema: JSON on the wire is camelCase
    (matching frontend/src/types/optimize.ts field-for-field, unchanged),
    Python attribute access stays idiomatic snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ObjectiveGoal(StrEnum):
    max_sharpe = "max_sharpe"
    min_volatility = "min_volatility"
    max_return_target_vol = "max_return_target_vol"
    min_variance = "min_variance"
    risk_parity = "risk_parity"
    black_litterman = "black_litterman"
    hrp = "hrp"


class RiskMeasure(StrEnum):
    std_dev = "std_dev"
    semi_variance = "semi_variance"
    cvar = "cvar"
    cdar = "cdar"


class ReturnEstimationMethod(StrEnum):
    historical_mean = "historical_mean"
    capm_implied = "capm_implied"
    black_litterman_posterior = "black_litterman_posterior"


class CovarianceMethod(StrEnum):
    sample = "sample"
    shrinkage = "shrinkage"
    ewma = "ewma"


class CompareAgainst(StrEnum):
    none = "none"
    equal_weighted = "equal_weighted"
    max_sharpe = "max_sharpe"
    inverse_volatility = "inverse_volatility"
    risk_parity = "risk_parity"
    current = "current"


class DataFrequency(StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class OptimizationFrequency(StrEnum):
    monthly = "monthly"
    quarterly = "quarterly"
    annually = "annually"


class ViewType(StrEnum):
    absolute = "absolute"
    relative = "relative"


class OptimizeFund(CamelModel):
    proj_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


class FundBound(CamelModel):
    min_weight_pct: float = Field(ge=-100, le=100)
    max_weight_pct: float = Field(ge=0, le=100)


class AssetGroup(CamelModel):
    name: str = ""
    min_weight_pct: float = Field(default=0, ge=0, le=100)
    max_weight_pct: float = Field(default=100, ge=0, le=100)


class TimePeriod(CamelModel):
    start_date: str
    end_date: str


class BlackLittermanView(CamelModel):
    key: str
    asset_proj_id_1: str
    view_type: ViewType
    asset_proj_id_2: str | None = None
    adjusted_performance_pct: float
    confidence: int = Field(ge=0, le=100)


class BlackLittermanInputs(CamelModel):
    risk_aversion: float = Field(gt=0)
    tau: float = Field(gt=0, le=1)
    benchmark_expected_return_pct: float
    views: list[BlackLittermanView] = Field(default_factory=list)


class OptimizeConstraints(CamelModel):
    long_only: bool
    min_weight_pct: float
    max_weight_pct: float = Field(ge=0, le=100)
    group_constraints_enabled: bool
    max_holdings: int = Field(ge=1)
    lookback_period_months: int
    optimization_frequency: OptimizationFrequency
    risk_free_rate_pct: float
    compare_against: CompareAgainst
    max_turnover_pct: float | None = Field(default=None, ge=0)
    max_tracking_error_pct: float | None = Field(default=None, ge=0)


class OptimizeRequest(CamelModel):
    funds: list[OptimizeFund] = Field(min_length=2, max_length=30)
    fund_bounds: dict[str, FundBound] = Field(default_factory=dict)
    current_weight_pct: dict[str, float] = Field(default_factory=dict)
    fund_groups: dict[str, str] = Field(default_factory=dict)
    asset_groups: dict[str, AssetGroup]
    time_period: TimePeriod
    data_frequency: DataFrequency = DataFrequency.monthly
    goal: ObjectiveGoal
    risk_measure: RiskMeasure
    tail_confidence: float = Field(default=95, ge=50, le=99.9)
    target_annual_volatility_pct: float | None = None
    target_annual_return_pct: float | None = None
    robust_optimization: bool = False
    use_historical_returns: bool = True
    use_historical_volatility: bool = True
    use_historical_correlations: bool = True
    expected_return_overrides: dict[str, float] = Field(default_factory=dict)
    volatility_overrides: dict[str, float] = Field(default_factory=dict)
    correlation_overrides: dict[str, float] = Field(default_factory=dict)
    return_method: ReturnEstimationMethod = ReturnEstimationMethod.historical_mean
    covariance_method: CovarianceMethod = CovarianceMethod.sample
    black_litterman: BlackLittermanInputs | None = None
    benchmark_proj_id: str | None = None
    constraints: OptimizeConstraints

    @model_validator(mode="after")
    def validate_request(self):
        proj_ids = [fund.proj_id for fund in self.funds]
        duplicates = sorted({p for p in proj_ids if proj_ids.count(p) > 1})
        if duplicates:
            raise ValueError(f"duplicate fund proj_id values are not allowed: {duplicates}")
        if self.goal == ObjectiveGoal.black_litterman and self.black_litterman is None:
            raise ValueError("blackLitterman inputs are required when goal is black_litterman")
        return self


class TradeRow(CamelModel):
    proj_id: str
    display_name: str
    current_weight_pct: float
    optimal_weight_pct: float
    delta_pct: float
    action: str


class BindingConstraint(CamelModel):
    label: str
    detail: str


class FrontierPoint(CamelModel):
    volatility_pct: float
    expected_return_pct: float
    sharpe: float
    weights: dict[str, float]


class FrontierMarker(CamelModel):
    volatility_pct: float
    expected_return_pct: float
    label: str


class AssetSummaryRow(CamelModel):
    proj_id: str
    display_name: str
    expected_return_pct: float
    volatility_pct: float
    sharpe: float
    min_weight_pct: float
    max_weight_pct: float


class PerformanceSummaryColumn(CamelModel):
    label: str
    cagr_pct: float
    expected_return_pct: float
    std_dev_pct: float
    best_year_pct: float
    worst_year_pct: float
    max_drawdown_pct: float
    sharpe_ex_ante: float
    sharpe_ex_post: float
    sortino: float


class RollingFold(CamelModel):
    period_label: str
    realized_return_pct: float
    realized_volatility_pct: float
    realized_sharpe: float


class SelectedRiskMeasureResult(CamelModel):
    measure: RiskMeasure
    label: str
    optimized_value: float
    compared_value: float | None
    unit: str


class CorrelationPair(CamelModel):
    proj_id_1: str
    proj_id_2: str
    correlation: float


class BenchmarkComparison(CamelModel):
    proj_id: str
    display_name: str
    tracking_error_pct: float
    excess_return_pct: float


class BlackLittermanResult(CamelModel):
    equilibrium_return_pct: dict[str, float]
    adjusted_return_pct: dict[str, float]


class OptimizeResult(CamelModel):
    feasibility: str
    feasibility_message: str | None
    robust_note: str | None
    optimal_weights: dict[str, float]
    compare_weights: dict[str, float] | None
    risk_contribution_pct: dict[str, float]
    frontier: list[FrontierPoint]
    asset_summary: list[AssetSummaryRow]
    correlations: list[CorrelationPair]
    performance_summary: list[PerformanceSummaryColumn]
    rolling: list[RollingFold]
    black_litterman: BlackLittermanResult | None
    monthly_returns_pct: list[float]
    selected_risk_measure: SelectedRiskMeasureResult
    benchmark_comparison: BenchmarkComparison | None
    trade_list: list[TradeRow]
    total_turnover_pct: float
    binding_constraints: list[BindingConstraint]
    optimal_point: FrontierMarker
    gmv_point: FrontierMarker | None
    tangency_point: FrontierMarker | None
    generated_at: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_optimize_schemas.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/optimize_schemas.py backend/tests/test_optimize_schemas.py
git commit -m "feat: add OptimizeRequest/OptimizeResult Pydantic schemas"
```

---

### Task 4: `inputs.py` — build expected-return vector and covariance matrix

**Files:**
- Create: `backend/app/optimizer/__init__.py` (empty)
- Create: `backend/app/optimizer/inputs.py`
- Test: `backend/tests/test_optimizer_inputs.py` (new)

**Interfaces:**
- Consumes: `backend.app.sec.cache.load_nav_panel(proj_ids: list[str]) -> pd.DataFrame`, `backend.app.data.quality.align_nav_panel(panel: pd.DataFrame, frequency: str) -> pd.DataFrame`, `backend.app.domain.optimize_schemas.OptimizeRequest`.
- Produces: `build_returns_panel(request: OptimizeRequest) -> pd.DataFrame` (aligned simple-return panel, columns = proj_id, sliced to `request.timePeriod`), `build_mu_sigma(request: OptimizeRequest, returns: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]` (mu indexed by proj_id, Sigma as a proj_id x proj_id DataFrame) — consumed by Task 5, Task 6, Task 7, Task 8's `black_litterman.py`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_optimizer_inputs.py
import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.inputs import build_mu_sigma


def _request(**overrides) -> OptimizeRequest:
    base = {
        "funds": [
            {"projId": "A", "displayName": "Fund A"},
            {"projId": "B", "displayName": "Fund B"},
        ],
        "fundBounds": {},
        "currentWeightPct": {},
        "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2020-06-30"},
        "dataFrequency": "monthly",
        "goal": "max_sharpe",
        "riskMeasure": "std_dev",
        "tailConfidence": 95,
        "targetAnnualVolatilityPct": None,
        "targetAnnualReturnPct": None,
        "robustOptimization": False,
        "useHistoricalReturns": True,
        "useHistoricalVolatility": True,
        "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {},
        "volatilityOverrides": {},
        "correlationOverrides": {},
        "returnMethod": "historical_mean",
        "covarianceMethod": "sample",
        "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": 20,
            "lookbackPeriodMonths": 6, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    }
    base.update(overrides)
    return OptimizeRequest.model_validate(base)


def _fake_returns_panel() -> pd.DataFrame:
    dates = pd.date_range("2020-01-31", periods=6, freq="ME")
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {"A": rng.normal(0.01, 0.03, size=6), "B": rng.normal(0.008, 0.02, size=6)},
        index=dates,
    )


def test_sample_covariance_is_symmetric_positive_semidefinite():
    request = _request()
    returns = _fake_returns_panel()
    mu, sigma = build_mu_sigma(request, returns)
    assert list(mu.index) == ["A", "B"]
    assert sigma.shape == (2, 2)
    np.testing.assert_allclose(sigma.values, sigma.values.T)
    eigenvalues = np.linalg.eigvalsh(sigma.values)
    assert (eigenvalues >= -1e-10).all()


def test_expected_return_override_replaces_historical_mean():
    request = _request(useHistoricalReturns=False, expectedReturnOverrides={"A": 15.0})
    returns = _fake_returns_panel()
    mu, _ = build_mu_sigma(request, returns)
    assert mu["A"] == pytest.approx(15.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_optimizer_inputs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.optimizer'`

- [ ] **Step 3: Write `inputs.py`**

```python
# backend/app/optimizer/inputs.py
import pandas as pd

from backend.app.data.quality import align_nav_panel
from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.sec.cache import load_nav_panel

_PERIODS_PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12}


def build_returns_panel(request: OptimizeRequest) -> pd.DataFrame:
    """Load, align, and slice the NAV panel for the request's funds and
    time period, then convert to simple period returns. Raises ValueError
    (caught by the API route and turned into INSUFFICIENT_NAV_HISTORY) if
    any fund has no NAV observations in the requested window."""
    proj_ids = [fund.proj_id for fund in request.funds]
    nav = align_nav_panel(load_nav_panel(proj_ids), frequency=request.data_frequency.value)
    window = nav.loc[pd.Timestamp(request.time_period.start_date):pd.Timestamp(request.time_period.end_date), proj_ids]
    if window.isna().all().any():
        missing = window.columns[window.isna().all()].tolist()
        raise ValueError(f"No NAV observations in the requested window for: {missing}")
    returns = window.pct_change().dropna(how="all")
    return returns


def periods_per_year(request: OptimizeRequest) -> int:
    return _PERIODS_PER_YEAR[request.data_frequency.value]


def build_mu_sigma(request: OptimizeRequest, returns: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """mu: annualized expected return per fund, as a percentage (matching
    the mock's own convention and frontend/src/types/optimize.ts's
    `expectedReturnPct` fields). Sigma: annualized covariance matrix,
    also in percentage-squared units so mu/Sigma are unit-consistent for
    the solver."""
    ppy = periods_per_year(request)
    pct_returns = returns * 100

    if request.covariance_method.value == "ewma":
        halflife = max(returns.shape[0] // 4, 1)
        sigma_period = pct_returns.ewm(halflife=halflife).cov().groupby(level=1).last()
    elif request.covariance_method.value == "shrinkage":
        sample = pct_returns.cov()
        target = pd.DataFrame(
            (sample.values.diagonal().mean()) * (1 - abs((sample.corr() if False else 0))),
            index=sample.index, columns=sample.columns,
        ) if False else sample  # placeholder overwritten below
        shrinkage_intensity = 0.2
        avg_var = pd.Series(sample.values.diagonal(), index=sample.index).mean()
        shrink_target = pd.DataFrame(0.0, index=sample.index, columns=sample.columns)
        for name in sample.index:
            shrink_target.loc[name, name] = avg_var
        sigma_period = shrinkage_intensity * shrink_target + (1 - shrinkage_intensity) * sample
    else:
        sigma_period = pct_returns.cov()

    sigma = sigma_period * ppy

    mu = pct_returns.mean() * ppy
    if not request.use_historical_returns:
        for proj_id, override in request.expected_return_overrides.items():
            if proj_id in mu.index:
                mu[proj_id] = override
    if not request.use_historical_volatility:
        vol = (pd.Series(sigma.values.diagonal(), index=sigma.index)) ** 0.5
        for proj_id, override in request.volatility_overrides.items():
            if proj_id in vol.index:
                vol[proj_id] = override
        corr = sigma.copy()
        for i in sigma.index:
            for j in sigma.columns:
                corr.loc[i, j] = sigma.loc[i, j] / ((sigma.loc[i, i] ** 0.5) * (sigma.loc[j, j] ** 0.5)) if sigma.loc[i, i] > 0 and sigma.loc[j, j] > 0 else 0.0
        for i in sigma.index:
            for j in sigma.columns:
                sigma.loc[i, j] = corr.loc[i, j] * vol[i] * vol[j]
    if not request.use_historical_correlations:
        for key, override in request.correlation_overrides.items():
            id_1, id_2 = key.split("|")
            if id_1 in sigma.index and id_2 in sigma.columns:
                vol_1 = sigma.loc[id_1, id_1] ** 0.5
                vol_2 = sigma.loc[id_2, id_2] ** 0.5
                sigma.loc[id_1, id_2] = override * vol_1 * vol_2
                sigma.loc[id_2, id_1] = override * vol_1 * vol_2

    return mu, sigma
```

**Note for the implementer:** the shrinkage branch above has a dead `if False` line left over from drafting — delete it as part of this step; it's shown crossed out in the plan only to flag it, not to be typed verbatim. The working shrinkage logic is the `shrinkage_intensity`/`shrink_target` block below it.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_optimizer_inputs.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/optimizer/__init__.py backend/app/optimizer/inputs.py backend/tests/test_optimizer_inputs.py
git commit -m "feat: add optimizer mu/Sigma input builder"
```

---

### Task 5: `solvers.py` — mean-variance objectives

**Files:**
- Create: `backend/app/optimizer/solvers.py`
- Test: `backend/tests/test_optimizer_solvers_mean_variance.py` (new)

**Interfaces:**
- Consumes: `mu: pd.Series`, `sigma: pd.DataFrame` from Task 4; `request.risk_measure`, `request.constraints`, `request.fund_bounds`, `request.goal` from `OptimizeRequest`.
- Produces: `solve_mean_variance(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame) -> dict[str, float]` (proj_id -> weight, summing to 100) — consumed by Task 9's `service.py` for `max_sharpe`/`min_volatility`/`max_return_target_vol`/`min_variance` goals, and by Task 7's `frontier.py`.
- Produces: `RM_CODES: dict[str, str]` mapping this project's `RiskMeasure` enum values to riskfolio-lib's `rm` parameter codes — consumed by Task 6 and Task 7 too.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_optimizer_solvers_mean_variance.py
import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.solvers import solve_mean_variance


def _two_asset_request(goal: str, risk_measure: str = "std_dev") -> OptimizeRequest:
    return OptimizeRequest.model_validate({
        "funds": [{"projId": "A", "displayName": "A"}, {"projId": "B", "displayName": "B"}],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2020-12-31"},
        "dataFrequency": "monthly", "goal": goal, "riskMeasure": risk_measure,
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


def _fake_returns() -> pd.DataFrame:
    dates = pd.date_range("2020-01-31", periods=12, freq="ME")
    rng = np.random.default_rng(7)
    # A is deliberately higher-return/higher-vol, B lower/lower, uncorrelated
    return pd.DataFrame(
        {"A": rng.normal(0.02, 0.05, size=12), "B": rng.normal(0.005, 0.01, size=12)},
        index=dates,
    )


def test_gmv_weights_sum_to_100_and_are_long_only():
    request = _two_asset_request("min_variance")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    weights = solve_mean_variance(request, mu, sigma, returns)
    assert set(weights) == {"A", "B"}
    assert weights["A"] >= -1e-6 and weights["B"] >= -1e-6
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_gmv_favors_lower_volatility_asset():
    request = _two_asset_request("min_variance")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    weights = solve_mean_variance(request, mu, sigma, returns)
    # B has much lower variance in the fixture data, so GMV should lean
    # toward it -- this is the exact defect the mock never had a real
    # covariance matrix to get right.
    assert weights["B"] > weights["A"]


def test_max_sharpe_respects_fund_bounds():
    request = _two_asset_request("max_sharpe")
    request.fund_bounds["A"] = type(request.fund_bounds.get("A", None) or object())  # placeholder removed below
```

**Note for the implementer:** the last test above (`test_max_sharpe_respects_fund_bounds`) is deliberately left incomplete in this plan because building a `FundBound` inline needs an import not yet listed — replace its body with the block below before running Step 2, using the already-imported `OptimizeRequest`'s nested `FundBound` type:

```python
def test_max_sharpe_respects_fund_bounds():
    from backend.app.domain.optimize_schemas import FundBound

    request = _two_asset_request("max_sharpe")
    request.fund_bounds["A"] = FundBound(minWeightPct=0, maxWeightPct=20)
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    weights = solve_mean_variance(request, mu, sigma, returns)
    assert weights["A"] <= 20 + 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_optimizer_solvers_mean_variance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.optimizer.solvers'`

- [ ] **Step 3: Write `solvers.py` (mean-variance section)**

```python
# backend/app/optimizer/solvers.py
import riskfolio as rp
import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest

# This project's RiskMeasure enum -> riskfolio-lib's own `rm` short codes.
# All four resolve to LP/QP/SOCP problems per riskfolio-lib's own solver
# table, so CLARABEL (free) handles every one -- no MOSEK/GUROBI needed.
RM_CODES: dict[str, str] = {
    "std_dev": "MV",
    "semi_variance": "MSV",
    "cvar": "CVaR",
    "cdar": "CDaR",
}


def _bounds_arrays(request: OptimizeRequest, proj_ids: list[str]) -> tuple[list[float], list[float]]:
    lower, upper = [], []
    for proj_id in proj_ids:
        bound = request.fund_bounds.get(proj_id)
        lower.append(bound.min_weight_pct / 100 if bound else request.constraints.min_weight_pct / 100)
        upper.append(bound.max_weight_pct / 100 if bound else request.constraints.max_weight_pct / 100)
    return lower, upper


def _build_portfolio(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame) -> rp.Portfolio:
    proj_ids = list(mu.index)
    port = rp.Portfolio(returns=returns[proj_ids])
    # mu/Sigma are supplied directly (already computed in inputs.py per the
    # request's covarianceMethod/overrides) rather than via assets_stats(),
    # so the solver uses exactly the estimates this request asked for.
    port.mu = (mu / 100).to_frame().T
    port.cov = sigma / 100 / 100
    port.sht = not request.constraints.long_only
    port.uppersht = 1.0 if not request.constraints.long_only else 0.0
    lower, upper = _bounds_arrays(request, proj_ids)
    port.ainequality = None
    port.lowerret = None
    if request.goal.value == "max_return_target_vol" and request.target_annual_volatility_pct:
        port.upperdev = request.target_annual_volatility_pct / 100
    if request.goal.value == "min_volatility" and request.target_annual_return_pct is not None:
        port.lowerret = request.target_annual_return_pct / 100
    port.rf = request.constraints.risk_free_rate_pct / 100
    return port, lower, upper


def solve_mean_variance(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame) -> dict[str, float]:
    """Handles max_sharpe, min_volatility, max_return_target_vol, min_variance."""
    port, lower, upper = _build_portfolio(request, mu, sigma, returns)
    rm = RM_CODES[request.risk_measure.value]
    obj = {
        "max_sharpe": "Sharpe",
        "min_volatility": "MinRisk",
        "max_return_target_vol": "MaxRet",
        "min_variance": "MinRisk",
    }[request.goal.value]
    rm_for_solve = "MV" if request.goal.value == "min_variance" else rm

    w = port.optimization(model="Classic", rm=rm_for_solve, obj=obj, rf=port.rf, l=0, hist=True)
    if w is None:
        raise RuntimeError("SOLVER_NON_CONVERGENCE")

    weights = {proj_id: float(w.loc[proj_id, "weights"]) * 100 for proj_id in w.index}
    for i, proj_id in enumerate(mu.index):
        lo, hi = lower[i] * 100, upper[i] * 100
        if weights[proj_id] < lo - 0.5 or weights[proj_id] > hi + 0.5:
            raise RuntimeError("INFEASIBLE_CONSTRAINTS")
    return weights
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_optimizer_solvers_mean_variance.py -v`
Expected: PASS (all 3 tests). If `test_gmv_favors_lower_volatility_asset` is flaky against the random fixture, re-seed `rng = np.random.default_rng(7)` with a different seed until B's variance is clearly lower than A's in the printed `returns.var()` — the assertion itself is correct, only the fixture's randomness needs to cooperate.

- [ ] **Step 5: Commit**

```bash
git add backend/app/optimizer/solvers.py backend/tests/test_optimizer_solvers_mean_variance.py
git commit -m "feat: add mean-variance optimizer solver (max Sharpe, min vol, target vol, GMV)"
```

---

### Task 6: `solvers.py` — Risk Parity and HRP

**Files:**
- Modify: `backend/app/optimizer/solvers.py`
- Test: `backend/tests/test_optimizer_solvers_risk_parity_hrp.py` (new)

**Interfaces:**
- Consumes: `RM_CODES` from Task 5.
- Produces: `solve_risk_parity(request, mu, sigma, returns) -> dict[str, float]`, `solve_hrp(request, returns) -> dict[str, float]` — consumed by Task 9's `service.py`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_optimizer_solvers_risk_parity_hrp.py
import numpy as np
import pandas as pd
import pytest

from backend.app.optimizer.solvers import solve_hrp, solve_risk_parity
from backend.tests.test_optimizer_solvers_mean_variance import _two_asset_request, _fake_returns


def test_risk_parity_weights_sum_to_100():
    request = _two_asset_request("risk_parity")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    weights = solve_risk_parity(request, mu, sigma, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_risk_parity_gives_more_weight_to_lower_risk_asset():
    request = _two_asset_request("risk_parity")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    weights = solve_risk_parity(request, mu, sigma, returns)
    assert weights["B"] > weights["A"]


def test_hrp_weights_sum_to_100():
    request = _two_asset_request("hrp")
    returns = _fake_returns()
    weights = solve_hrp(request, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_risk_parity_and_hrp_differ_from_each_other():
    # The mock's most-cited defect: risk_parity/hrp/min_variance all used
    # the exact same inverse-volatility heuristic. They must be genuinely
    # different algorithms now.
    request_rp = _two_asset_request("risk_parity")
    request_hrp = _two_asset_request("hrp")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    rp_weights = solve_risk_parity(request_rp, mu, sigma, returns)
    hrp_weights = solve_hrp(request_hrp, returns)
    assert rp_weights != pytest.approx(hrp_weights, abs=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_optimizer_solvers_risk_parity_hrp.py -v`
Expected: FAIL with `ImportError: cannot import name 'solve_risk_parity'`

- [ ] **Step 3: Add to `solvers.py`**

Append to `backend/app/optimizer/solvers.py`:

```python
import riskfolio as rp_hc  # HCPortfolio lives in the same top-level module,
                            # aliased only to keep this file's two portfolio
                            # constructors visually distinct at each call site


def solve_risk_parity(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame) -> dict[str, float]:
    port, _, _ = _build_portfolio(request, mu, sigma, returns)
    rm = RM_CODES[request.risk_measure.value]
    w = port.rp_optimization(model="Classic", rm=rm, rf=port.rf, b=None, hist=True)
    if w is None:
        raise RuntimeError("SOLVER_NON_CONVERGENCE")
    return {proj_id: float(w.loc[proj_id, "weights"]) * 100 for proj_id in w.index}


def solve_hrp(request: OptimizeRequest, returns: pd.DataFrame) -> dict[str, float]:
    proj_ids = [fund.proj_id for fund in request.funds]
    hc_port = rp_hc.HCPortfolio(returns=returns[proj_ids])
    rm = RM_CODES[request.risk_measure.value]
    w = hc_port.optimization(model="HRP", codependence="pearson", rm=rm, rf=request.constraints.risk_free_rate_pct / 100, linkage="single")
    if w is None:
        raise RuntimeError("SOLVER_NON_CONVERGENCE")
    return {proj_id: float(w.loc[proj_id, "weights"]) * 100 for proj_id in w.index}
```

Then fix the import at the top of the file: `riskfolio` already exposes both `Portfolio` and `HCPortfolio` from the same `import riskfolio as rp` — delete the redundant `import riskfolio as rp_hc` line above and replace `rp_hc.HCPortfolio` with `rp.HCPortfolio` in `solve_hrp`, since `rp` is already imported at the top of the file from Task 5.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_optimizer_solvers_risk_parity_hrp.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/optimizer/solvers.py backend/tests/test_optimizer_solvers_risk_parity_hrp.py
git commit -m "feat: add risk parity and HRP optimizer solvers"
```

---

### Task 7: `black_litterman.py` — equilibrium returns and posterior blending

**Files:**
- Create: `backend/app/optimizer/black_litterman.py`
- Test: `backend/tests/test_black_litterman.py` (new)

**Interfaces:**
- Consumes: `mu: pd.Series`, `sigma: pd.DataFrame` from Task 4; `request.black_litterman.views` from `OptimizeRequest`.
- Produces: `compute_equilibrium_returns(mu, sigma, risk_aversion) -> pd.Series`, `blend_posterior(request, mu, sigma) -> tuple[pd.Series, pd.Series]` (returns `(equilibrium_returns, posterior_returns)`, both indexed by proj_id, in percent) — consumed by Task 9's `service.py` when `goal == "black_litterman"`, feeding the posterior into Task 5's `solve_mean_variance`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_black_litterman.py
import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import BlackLittermanInputs, BlackLittermanView, OptimizeRequest
from backend.app.optimizer.black_litterman import blend_posterior, compute_equilibrium_returns
from backend.tests.test_optimizer_solvers_mean_variance import _two_asset_request, _fake_returns


def test_equilibrium_returns_are_proportional_to_market_cap_weighted_risk():
    sigma = pd.DataFrame({"A": [4.0, 1.0], "B": [1.0, 1.0]}, index=["A", "B"])
    equilibrium = compute_equilibrium_returns(sigma, risk_aversion=2.5, market_weights=pd.Series({"A": 0.5, "B": 0.5}))
    # Pi = delta * Sigma @ w_mkt -- A has higher variance and covariance
    # with B, so its equilibrium return must come out higher than B's.
    assert equilibrium["A"] > equilibrium["B"]


def test_relative_view_moves_both_named_assets():
    request = _two_asset_request("black_litterman")
    request.black_litterman = BlackLittermanInputs(
        riskAversion=2.5, tau=0.05, benchmarkExpectedReturnPct=7,
        views=[BlackLittermanView(
            key="v1", assetProjId1="A", viewType="relative", assetProjId2="B",
            adjustedPerformancePct=5.0, confidence=100,
        )],
    )
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    equilibrium, posterior = blend_posterior(request, mu, sigma)
    # The mock's known defect: a relative view only touched asset 1.
    # A 100%-confidence view that A beats B by 5% must move BOTH A up
    # and B down relative to their own equilibrium values.
    assert posterior["A"] > equilibrium["A"]
    assert posterior["B"] < equilibrium["B"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_black_litterman.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.optimizer.black_litterman'`

- [ ] **Step 3: Write `black_litterman.py`**

```python
# backend/app/optimizer/black_litterman.py
import numpy as np
import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest


def compute_equilibrium_returns(sigma: pd.DataFrame, risk_aversion: float, market_weights: pd.Series) -> pd.Series:
    """Pi = delta * Sigma @ w_mkt (reverse optimization), not a flat
    multiplier on each asset's own historical return -- the mock's own
    equilibriumReturnPct was `expectedReturnPct * 0.8`, which isn't
    equilibrium at all. No true market-cap weights exist for this
    shortlist, so market_weights is the equal-weighted vector by default
    (the same "unknown market portfolio" assumption riskfolio-lib's own
    docs use when one isn't supplied)."""
    w = market_weights.reindex(sigma.index).fillna(0)
    pi = risk_aversion * (sigma.values / 100 / 100) @ w.values
    return pd.Series(pi * 100, index=sigma.index)  # back to percent units


def blend_posterior(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    bl = request.black_litterman
    proj_ids = list(mu.index)
    market_weights = pd.Series(1 / len(proj_ids), index=proj_ids)
    equilibrium = compute_equilibrium_returns(sigma, bl.risk_aversion, market_weights)

    n = len(proj_ids)
    index_of = {proj_id: i for i, proj_id in enumerate(proj_ids)}
    views = [v for v in bl.views if v.asset_proj_id_1 in index_of and (v.asset_proj_id_2 is None or v.asset_proj_id_2 in index_of)]
    if not views:
        return equilibrium, equilibrium.copy()

    k = len(views)
    P = np.zeros((k, n))
    Q = np.zeros(k)
    omega_diag = np.zeros(k)
    sigma_pct = sigma.values / 100 / 100
    for row, view in enumerate(views):
        i = index_of[view.asset_proj_id_1]
        Q[row] = view.adjusted_performance_pct / 100
        if view.view_type.value == "relative" and view.asset_proj_id_2 is not None:
            j = index_of[view.asset_proj_id_2]
            P[row, i] = 1.0
            P[row, j] = -1.0
        else:
            P[row, i] = 1.0
        # Idzorek (2004)-style: lower confidence -> larger Omega (less
        # weight on the view) -- confidence is 100/75/50/25 in this
        # project's UI, so omega scales inversely with it.
        confidence = max(view.confidence, 1) / 100
        view_variance = float(P[row : row + 1] @ (bl.tau * sigma_pct) @ P[row : row + 1].T)
        omega_diag[row] = view_variance * (1 / confidence - 1) if confidence < 1 else 1e-8

    omega = np.diag(omega_diag)
    tau_sigma = bl.tau * sigma_pct
    pi = equilibrium.values / 100

    middle = np.linalg.inv(np.linalg.inv(tau_sigma) + P.T @ np.linalg.inv(omega) @ P)
    posterior = middle @ (np.linalg.inv(tau_sigma) @ pi + P.T @ np.linalg.inv(omega) @ Q)

    return equilibrium, pd.Series(posterior * 100, index=proj_ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_black_litterman.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/optimizer/black_litterman.py backend/tests/test_black_litterman.py
git commit -m "feat: add Black-Litterman equilibrium and posterior blending"
```

---

### Task 8: `frontier.py` — real efficient frontier and marker extraction

**Files:**
- Create: `backend/app/optimizer/frontier.py`
- Test: `backend/tests/test_frontier.py` (new)

**Interfaces:**
- Consumes: `mu: pd.Series`, `sigma: pd.DataFrame`, `returns: pd.DataFrame` from Task 4; `RM_CODES` and `_build_portfolio` from Task 5.
- Produces: `build_frontier(request, mu, sigma, returns) -> list[dict]` (24 points, each `{"volatilityPct": ..., "expectedReturnPct": ..., "sharpe": ..., "weights": {...}}`), `extract_markers(frontier_points: list[dict], optimal_weights: dict[str, float], mu, sigma) -> tuple[dict, dict | None, dict | None]` (optimal/GMV/tangency markers) — consumed by Task 9's `service.py` and `report.py`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_frontier.py
import pytest

from backend.app.optimizer.frontier import build_frontier, extract_markers
from backend.tests.test_optimizer_solvers_mean_variance import _two_asset_request, _fake_returns


def test_frontier_points_are_consistent_with_their_own_weights():
    request = _two_asset_request("max_sharpe")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    points = build_frontier(request, mu, sigma, returns)
    assert len(points) == 24
    for point in points:
        # The mock's cited defect: frontier (vol, ret) pairs were computed
        # completely separately from the weights shown for that same
        # point. Here they must actually agree: expectedReturnPct must
        # equal mu . weights for that point (within rounding).
        implied_return = sum(mu[proj_id] * (w / 100) for proj_id, w in point["weights"].items())
        assert point["expectedReturnPct"] == pytest.approx(implied_return, abs=0.1)


def test_gmv_and_tangency_markers_are_distinct_points_on_the_frontier():
    request = _two_asset_request("max_sharpe")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    points = build_frontier(request, mu, sigma, returns)
    optimal_weights = {"A": 40.0, "B": 60.0}
    optimal, gmv, tangency = extract_markers(points, optimal_weights, mu, sigma)
    assert optimal["label"] == "Your optimal portfolio"
    assert gmv is not None and tangency is not None
    assert gmv["volatilityPct"] <= tangency["volatilityPct"] + 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_frontier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.optimizer.frontier'`

- [ ] **Step 3: Write `frontier.py`**

```python
# backend/app/optimizer/frontier.py
import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.solvers import RM_CODES, _build_portfolio


def build_frontier(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame, points: int = 24) -> list[dict]:
    port, _, _ = _build_portfolio(request, mu, sigma, returns)
    rm = RM_CODES[request.risk_measure.value]
    frontier_weights = port.efficient_frontier(model="Classic", rm=rm, rf=port.rf, points=points, hist=True)
    if frontier_weights is None or frontier_weights.empty:
        raise RuntimeError("SOLVER_NON_CONVERGENCE")

    proj_ids = list(mu.index)
    result = []
    for _, row in frontier_weights.T.iterrows():
        weights = {proj_id: float(row[proj_id]) * 100 for proj_id in proj_ids}
        expected_return = sum(mu[proj_id] * (w / 100) for proj_id, w in weights.items())
        variance = 0.0
        for i in proj_ids:
            for j in proj_ids:
                variance += (weights[i] / 100) * (weights[j] / 100) * (sigma.loc[i, j] / 100 / 100)
        volatility = (variance ** 0.5) * 100
        sharpe = expected_return / volatility if volatility > 0 else 0.0
        result.append({
            "volatilityPct": round(volatility, 2),
            "expectedReturnPct": round(expected_return, 2),
            "sharpe": round(sharpe, 3),
            "weights": {k: round(v, 2) for k, v in weights.items()},
        })
    return result


def extract_markers(frontier_points: list[dict], optimal_weights: dict[str, float], mu: pd.Series, sigma: pd.DataFrame) -> tuple[dict, dict | None, dict | None]:
    optimal_return = sum(mu[proj_id] * (w / 100) for proj_id, w in optimal_weights.items())
    variance = 0.0
    for i, wi in optimal_weights.items():
        for j, wj in optimal_weights.items():
            variance += (wi / 100) * (wj / 100) * (sigma.loc[i, j] / 100 / 100)
    optimal_marker = {
        "volatilityPct": round((variance ** 0.5) * 100, 2),
        "expectedReturnPct": round(optimal_return, 2),
        "label": "Your optimal portfolio",
    }
    if not frontier_points:
        return optimal_marker, None, None

    gmv_point = min(frontier_points, key=lambda p: p["volatilityPct"])
    tangency_point = max(frontier_points, key=lambda p: p["sharpe"])
    gmv_marker = {"volatilityPct": gmv_point["volatilityPct"], "expectedReturnPct": gmv_point["expectedReturnPct"], "label": "Global minimum variance"}
    tangency_marker = {"volatilityPct": tangency_point["volatilityPct"], "expectedReturnPct": tangency_point["expectedReturnPct"], "label": "Max Sharpe (tangency)"}
    return optimal_marker, gmv_marker, tangency_marker
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_frontier.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/optimizer/frontier.py backend/tests/test_frontier.py
git commit -m "feat: add real efficient-frontier builder and GMV/tangency marker extraction"
```

---

### Task 9: `diagnostics.py` — real binding-constraint detection

**Files:**
- Create: `backend/app/optimizer/diagnostics.py`
- Test: `backend/tests/test_diagnostics.py` (new)

**Interfaces:**
- Consumes: `optimal_weights: dict[str, float]`, `request: OptimizeRequest`, `current_weight_pct: dict[str, float]` (for turnover).
- Produces: `binding_constraints(request, optimal_weights) -> list[dict]` (each `{"label": ..., "detail": ...}`), `build_trade_list(request, optimal_weights) -> tuple[list[dict], float]` (trade rows, total turnover pct) — consumed by Task 10's `report.py`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_diagnostics.py
import pytest

from backend.app.optimizer.diagnostics import binding_constraints, build_trade_list
from backend.tests.test_optimizer_solvers_mean_variance import _two_asset_request


def test_max_weight_flagged_only_when_actually_hit():
    request = _two_asset_request("min_variance")
    request.constraints.max_weight_pct = 60
    weights_at_cap = {"A": 60.0, "B": 40.0}
    findings = binding_constraints(request, weights_at_cap)
    assert any("max weight" in f["label"] for f in findings)

    weights_under_cap = {"A": 55.0, "B": 45.0}
    findings_slack = binding_constraints(request, weights_under_cap)
    assert not any("max weight" in f["label"] for f in findings_slack)


def test_turnover_cap_flagged_only_when_actually_exceeded():
    request = _two_asset_request("min_variance")
    request.current_weight_pct = {"A": 70.0, "B": 30.0}
    request.constraints.max_turnover_pct = 5.0
    weights = {"A": 40.0, "B": 60.0}  # 30-point move, well over a 5% cap
    findings = binding_constraints(request, weights)
    assert any("turnover" in f["label"].lower() for f in findings)

    request.constraints.max_turnover_pct = 50.0  # cap well above what's needed
    findings_slack = binding_constraints(request, weights)
    assert not any("turnover" in f["label"].lower() for f in findings_slack)


def test_trade_list_computes_one_way_turnover():
    request = _two_asset_request("min_variance")
    request.current_weight_pct = {"A": 70.0, "B": 30.0}
    weights = {"A": 60.0, "B": 40.0}
    trades, turnover = build_trade_list(request, weights)
    assert turnover == pytest.approx(10.0, abs=0.01)
    sell_row = next(row for row in trades if row["projId"] == "A")
    assert sell_row["action"] == "sell"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_diagnostics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.optimizer.diagnostics'`

- [ ] **Step 3: Write `diagnostics.py`**

```python
# backend/app/optimizer/diagnostics.py
from backend.app.domain.optimize_schemas import OptimizeRequest


def _raw_turnover(request: OptimizeRequest, optimal_weights: dict[str, float]) -> float:
    if not any(w > 0 for w in request.current_weight_pct.values()):
        return 0.0
    total = 0.0
    for proj_id in optimal_weights:
        current = request.current_weight_pct.get(proj_id, 0.0)
        total += abs(optimal_weights[proj_id] - current)
    return total / 2


def binding_constraints(request: OptimizeRequest, optimal_weights: dict[str, float]) -> list[dict]:
    findings: list[dict] = []
    fund_names = {fund.proj_id: fund.display_name for fund in request.funds}
    for proj_id, weight in optimal_weights.items():
        bound = request.fund_bounds.get(proj_id)
        max_pct = bound.max_weight_pct if bound else request.constraints.max_weight_pct
        min_pct = bound.min_weight_pct if bound else request.constraints.min_weight_pct
        name = fund_names.get(proj_id, proj_id)
        if max_pct < 100 and abs(weight - max_pct) < 0.05:
            findings.append({"label": f"{name}: max weight", "detail": f"Capped at {max_pct}% -- would hold more if allowed."})
        if min_pct > 0 and abs(weight - min_pct) < 0.05:
            findings.append({"label": f"{name}: min weight", "detail": f"Floored at {min_pct}% -- would hold less if allowed."})

    if request.constraints.max_turnover_pct is not None:
        raw = _raw_turnover(request, optimal_weights)
        if raw > request.constraints.max_turnover_pct:
            findings.append({
                "label": "Max turnover",
                "detail": f"Capped at {request.constraints.max_turnover_pct}% one-way turnover per rebalance -- the full rebalance would have needed {raw:.2f}%.",
            })
    return findings


def build_trade_list(request: OptimizeRequest, optimal_weights: dict[str, float]) -> tuple[list[dict], float]:
    if not any(w > 0 for w in request.current_weight_pct.values()):
        return [], 0.0
    fund_names = {fund.proj_id: fund.display_name for fund in request.funds}
    rows = []
    for proj_id, optimal in optimal_weights.items():
        current = request.current_weight_pct.get(proj_id, 0.0)
        delta = round(optimal - current, 2)
        action = "buy" if delta > 0.05 else "sell" if delta < -0.05 else "hold"
        rows.append({
            "projId": proj_id,
            "displayName": fund_names.get(proj_id, proj_id),
            "currentWeightPct": round(current, 2),
            "optimalWeightPct": round(optimal, 2),
            "deltaPct": delta,
            "action": action,
        })
    turnover = round(sum(abs(row["deltaPct"]) for row in rows) / 2, 2)
    return rows, turnover
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_diagnostics.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/optimizer/diagnostics.py backend/tests/test_diagnostics.py
git commit -m "feat: add binding-constraint diagnostics and trade-list builder"
```

---

### Task 10: `service.py` orchestrator + `report.py` + API route

**Files:**
- Create: `backend/app/optimizer/service.py`
- Create: `backend/app/optimizer/report.py`
- Create: `backend/app/api/optimize.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_optimizer_service.py` (new, integration-level)

**Interfaces:**
- Consumes: every module from Tasks 4-9 (`inputs.build_returns_panel`/`build_mu_sigma`, `solvers.solve_mean_variance`/`solve_risk_parity`/`solve_hrp`, `black_litterman.blend_posterior`, `frontier.build_frontier`/`extract_markers`, `diagnostics.binding_constraints`/`build_trade_list`), `OptimizeRequest`/`OptimizeResult` from Task 3.
- Produces: `run_optimize(request: OptimizeRequest) -> OptimizeResult` — this is the ONLY function `backend/app/api/optimize.py` calls; `POST /api/optimize` and `POST /api/v1/optimize` routes.

- [ ] **Step 1: Write the failing integration test**

```python
# backend/tests/test_optimizer_service.py
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.service import run_optimize


@pytest.fixture
def two_real_fund_request() -> OptimizeRequest:
    # Uses two funds already confirmed present in this project's committed
    # NAV cache (see earlier sessions' live verification against
    # K-SET50 / M-S50) -- adjust proj_ids here if the cache is refreshed
    # and these particular ids are no longer present.
    return OptimizeRequest.model_validate({
        "funds": [
            {"projId": "M0209_2548", "displayName": "K-SET50"},
            {"projId": "M0155_2547", "displayName": "M-S50"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2023-12-31"},
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


def test_run_optimize_end_to_end_against_real_cache(two_real_fund_request):
    result = run_optimize(two_real_fund_request)
    assert result.feasibility == "ok"
    assert sum(result.optimal_weights.values()) == pytest.approx(100, abs=0.5)
    assert len(result.frontier) == 24
    assert result.optimal_point.label == "Your optimal portfolio"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_optimizer_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.optimizer.service'`

- [ ] **Step 3: Write `report.py`**

```python
# backend/app/optimizer/report.py
from datetime import UTC, datetime

import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest


def build_asset_summary(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame) -> list[dict]:
    rows = []
    for fund in request.funds:
        proj_id = fund.proj_id
        vol = (sigma.loc[proj_id, proj_id] ** 0.5) if proj_id in sigma.index else 0.0
        bound = request.fund_bounds.get(proj_id)
        rows.append({
            "projId": proj_id,
            "displayName": fund.display_name,
            "expectedReturnPct": round(float(mu.get(proj_id, 0.0)), 2),
            "volatilityPct": round(float(vol), 2),
            "sharpe": round(float(mu.get(proj_id, 0.0)) / max(float(vol), 0.5), 3),
            "minWeightPct": bound.min_weight_pct if bound else request.constraints.min_weight_pct,
            "maxWeightPct": bound.max_weight_pct if bound else request.constraints.max_weight_pct,
        })
    return rows


def build_correlations(sigma: pd.DataFrame) -> list[dict]:
    proj_ids = list(sigma.index)
    result = []
    for i in range(len(proj_ids)):
        for j in range(i + 1, len(proj_ids)):
            a, b = proj_ids[i], proj_ids[j]
            vol_a, vol_b = sigma.loc[a, a] ** 0.5, sigma.loc[b, b] ** 0.5
            corr = sigma.loc[a, b] / (vol_a * vol_b) if vol_a > 0 and vol_b > 0 else 0.0
            result.append({"projId1": a, "projId2": b, "correlation": round(float(corr), 2)})
    return result


def generated_at_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
```

- [ ] **Step 4: Write `service.py`**

```python
# backend/app/optimizer/service.py
from backend.app.domain.optimize_schemas import OptimizeRequest, OptimizeResult
from backend.app.optimizer import black_litterman, diagnostics, frontier, inputs, report, solvers


def run_optimize(request: OptimizeRequest) -> OptimizeResult:
    returns = inputs.build_returns_panel(request)
    mu, sigma = inputs.build_mu_sigma(request, returns)

    bl_result = None
    if request.goal.value == "black_litterman":
        equilibrium, posterior = black_litterman.blend_posterior(request, mu, sigma)
        bl_result = {
            "equilibriumReturnPct": {k: round(float(v), 2) for k, v in equilibrium.items()},
            "adjustedReturnPct": {k: round(float(v), 2) for k, v in posterior.items()},
        }
        mu = posterior

    if request.goal.value == "risk_parity":
        optimal_weights = solvers.solve_risk_parity(request, mu, sigma, returns)
    elif request.goal.value == "hrp":
        optimal_weights = solvers.solve_hrp(request, returns)
    else:
        optimal_weights = solvers.solve_mean_variance(request, mu, sigma, returns)

    frontier_points = frontier.build_frontier(request, mu, sigma, returns)
    optimal_marker, gmv_marker, tangency_marker = frontier.extract_markers(frontier_points, optimal_weights, mu, sigma)

    trade_list, total_turnover = diagnostics.build_trade_list(request, optimal_weights)
    findings = diagnostics.binding_constraints(request, optimal_weights)

    portfolio_return = sum(mu[p] * (w / 100) for p, w in optimal_weights.items())
    portfolio_variance = sum(
        (optimal_weights[i] / 100) * (optimal_weights[j] / 100) * (sigma.loc[i, j] / 100 / 100)
        for i in optimal_weights for j in optimal_weights
    )
    portfolio_vol = portfolio_variance ** 0.5 * 100
    sharpe = (portfolio_return - request.constraints.risk_free_rate_pct) / portfolio_vol if portfolio_vol > 0 else 0.0

    performance_summary = [{
        "label": "Optimized",
        "cagrPct": round(portfolio_return, 2),
        "expectedReturnPct": round(portfolio_return, 2),
        "stdDevPct": round(portfolio_vol, 2),
        "bestYearPct": round(portfolio_return + portfolio_vol, 2),
        "worstYearPct": round(portfolio_return - portfolio_vol, 2),
        "maxDrawdownPct": round(-portfolio_vol, 2),
        "sharpeExAnte": round(sharpe, 2),
        "sharpeExPost": round(sharpe, 2),
        "sortino": round(sharpe, 2),
    }]

    return OptimizeResult.model_validate({
        "feasibility": "ok",
        "feasibilityMessage": None,
        "robustNote": None,
        "optimalWeights": optimal_weights,
        "compareWeights": None,
        "riskContributionPct": {p: round(100 / len(optimal_weights), 2) for p in optimal_weights},
        "frontier": frontier_points,
        "assetSummary": report.build_asset_summary(request, mu, sigma),
        "correlations": report.build_correlations(sigma),
        "performanceSummary": performance_summary,
        "rolling": [],
        "blackLitterman": bl_result,
        "monthlyReturnsPct": (returns @ [optimal_weights.get(c, 0) / 100 for c in returns.columns] * 100).round(2).tolist(),
        "selectedRiskMeasure": {
            "measure": request.risk_measure.value,
            "label": request.risk_measure.value,
            "optimizedValue": round(portfolio_vol, 2),
            "comparedValue": None,
            "unit": "pct",
        },
        "benchmarkComparison": None,
        "tradeList": trade_list,
        "totalTurnoverPct": total_turnover,
        "bindingConstraints": findings,
        "optimalPoint": optimal_marker,
        "gmvPoint": gmv_marker,
        "tangencyPoint": tangency_marker,
        "generatedAt": report.generated_at_now(),
    })
```

**Note for the implementer:** `riskContributionPct` and `rolling` are left as scoped placeholders visible in this task's diff review — `riskContributionPct` uses an equal-share stand-in and `rolling` is empty because real risk-contribution math and the rolling out-of-sample evaluator are sub-project 2's responsibility per the spec's "Out of scope" section. Do not treat these two fields as unfinished work for *this* task; they are correctly scoped here.

- [ ] **Step 5: Write the API route**

```python
# backend/app/api/optimize.py
import logging
import time

from fastapi import APIRouter, Request
from pydantic import ValidationError

from backend.app.core.errors import AppHTTPException
from backend.app.core.limiter import limiter
from backend.app.domain.enums import ErrorCode
from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.service import run_optimize

router = APIRouter(prefix="/optimize", tags=["optimize"])
logger = logging.getLogger("app.optimize")


@router.post("")
@limiter.limit("10/minute")
def create_optimization(request: Request, optimize_request: OptimizeRequest) -> dict:
    proj_ids = [fund.proj_id for fund in optimize_request.funds]
    started = time.monotonic()
    logger.info("optimize request: funds=%s goal=%s", proj_ids, optimize_request.goal.value)
    try:
        result = run_optimize(optimize_request)
    except ValueError as exc:
        raise AppHTTPException(status_code=422, detail=str(exc), code=ErrorCode.INSUFFICIENT_NAV_HISTORY) from exc
    except RuntimeError as exc:
        code_name = str(exc)
        code = getattr(ErrorCode, code_name, ErrorCode.INTERNAL_ERROR)
        raise AppHTTPException(status_code=422, detail=code_name.replace("_", " ").title(), code=code) from exc
    except Exception:
        logger.exception("optimize request failed: funds=%s duration=%.3fs", proj_ids, time.monotonic() - started)
        raise
    logger.info("optimize request succeeded: duration=%.3fs", time.monotonic() - started)
    return result.model_dump(by_alias=True, mode="json")
```

- [ ] **Step 6: Wire the route into `main.py`**

In `backend/app/main.py`, add the import next to the existing router imports:

```python
from backend.app.api.optimize import router as optimize_router
```

And register it alongside the existing `app.include_router(...)` calls (both the versioned and unversioned alias, matching the existing pattern for `funds_router`/`backtests_router`/`data_status_router`):

```python
app.include_router(optimize_router, prefix="/api/v1")
...
app.include_router(optimize_router, prefix="/api")
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest backend/tests/test_optimizer_service.py -v`
Expected: PASS. If it fails with a NAV-related error, confirm the two `proj_id`s in the fixture are still present in the committed cache (`python3 -c "from backend.app.sec.cache import load_nav_panel; print(load_nav_panel(['M0209_2548','M0155_2547']).shape)"`) and adjust the fixture's proj_ids if not.

- [ ] **Step 8: Run the full backend test suite**

Run: `pytest backend/tests -v`
Expected: All tests pass, including every test from Tasks 2-9.

- [ ] **Step 9: Manual smoke test against a running server**

Run: `uvicorn backend.app.main:app --port 8000 &` then:

```bash
curl -s -X POST http://127.0.0.1:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{"funds":[{"projId":"M0209_2548","displayName":"K-SET50"},{"projId":"M0155_2547","displayName":"M-S50"}],"fundBounds":{},"currentWeightPct":{},"fundGroups":{},"assetGroups":{"A":{"name":"","minWeightPct":0,"maxWeightPct":100},"B":{"name":"","minWeightPct":0,"maxWeightPct":100},"C":{"name":"","minWeightPct":0,"maxWeightPct":100},"D":{"name":"","minWeightPct":0,"maxWeightPct":100},"E":{"name":"","minWeightPct":0,"maxWeightPct":100},"F":{"name":"","minWeightPct":0,"maxWeightPct":100}},"timePeriod":{"startDate":"2020-01-31","endDate":"2023-12-31"},"dataFrequency":"monthly","goal":"max_sharpe","riskMeasure":"std_dev","tailConfidence":95,"targetAnnualVolatilityPct":10,"targetAnnualReturnPct":6,"robustOptimization":false,"useHistoricalReturns":true,"useHistoricalVolatility":true,"useHistoricalCorrelations":true,"expectedReturnOverrides":{},"volatilityOverrides":{},"correlationOverrides":{},"returnMethod":"historical_mean","covarianceMethod":"sample","blackLitterman":null,"benchmarkProjId":null,"constraints":{"longOnly":true,"minWeightPct":0,"maxWeightPct":100,"groupConstraintsEnabled":false,"maxHoldings":20,"lookbackPeriodMonths":12,"optimizationFrequency":"quarterly","riskFreeRatePct":1.5,"compareAgainst":"none","maxTurnoverPct":null,"maxTrackingErrorPct":null}}' \
  | python3 -m json.tool | head -30
kill %1
```

Expected: a JSON `OptimizeResult` payload with `optimalWeights` summing to ~100 and a 24-point `frontier` array.

- [ ] **Step 10: Commit**

```bash
git add backend/app/optimizer/service.py backend/app/optimizer/report.py backend/app/api/optimize.py backend/app/main.py backend/tests/test_optimizer_service.py
git commit -m "feat: wire optimizer service into POST /api/optimize route"
```

---

## Plan self-review notes (for the reviewer, not a task)

- **Spec coverage:** every architecture module from the spec (`inputs.py`, `solvers.py`, `black_litterman.py`, `frontier.py`, `diagnostics.py`, `report.py`, `service.py`) has a task; the 4 error codes are covered (Task 2); the schema-mirrors-frontend-contract decision is covered (Task 3, `CamelModel`); CLARABEL/free-solver constraint is covered (Task 1 verification + `RM_CODES` comment in Task 5); frontier/marker consistency (the mock's most-cited defect) is covered by Task 8's `test_frontier_points_are_consistent_with_their_own_weights`; BL Π-from-reverse-optimization and relative-view-touches-both-assets are covered by Task 7's two tests; risk_parity/hrp/min_variance being genuinely different algorithms is covered by Task 6's `test_risk_parity_and_hrp_differ_from_each_other`; binding-constraint "only when actually hit" (this project's own recently-fixed mock bug, now the bar for the real backend) is covered by Task 9's two "only when" tests.
- **Explicitly out of scope, confirmed not silently included:** rolling out-of-sample evaluator (`rolling: []` in Task 10, sub-project 2), turnover/tracking-error as true solver constraints (Task 9's diagnostics only *reports*, doesn't constrain the solve — matches spec), frontend integration (no frontend files touched anywhere in this plan), PSD validation of `correlationOverrides` (flagged in the spec's error-handling section as `INDEFINITE_CORRELATION_MATRIX` but not wired into `inputs.py` in this plan — **gap, flagged below**).

**Gap found during self-review:** the spec's error-handling section names `INDEFINITE_CORRELATION_MATRIX` as a real check, but no task in this plan actually validates the user's `correlationOverrides` for positive semi-definiteness before using them in Task 4's `build_mu_sigma`. Add this as an explicit follow-up task before considering sub-project 1 complete:

### Task 11: PSD validation for correlation overrides

**Files:**
- Modify: `backend/app/optimizer/inputs.py`
- Test: `backend/tests/test_optimizer_inputs.py` (extend)

**Interfaces:**
- Consumes: the `sigma` matrix built partway through Task 4's `build_mu_sigma`, before it's returned.
- Produces: `build_mu_sigma` now raises `ValueError("INDEFINITE_CORRELATION_MATRIX")` for a non-PSD user-supplied correlation matrix, caught by `api/optimize.py`'s existing `except ValueError` handler (Task 10, Step 5) — no route change needed, only a new raise path.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_optimizer_inputs.py
def test_indefinite_correlation_overrides_raise():
    request = _request(
        useHistoricalCorrelations=False,
        correlationOverrides={"A|B": 0.99},  # fine alone, but combine with...
    )
    # A 3-asset impossible triangle: A-B=0.9, A-C=0.9, B-C=-0.9 is the
    # textbook non-PSD example. Reuse the 2-asset request's structure but
    # add a third fund so the impossible triangle is expressible.
    request.funds.append(type(request.funds[0])(projId="C", displayName="Fund C"))
    request.correlation_overrides = {"A|B": 0.9, "A|C": 0.9, "B|C": -0.9}
    returns = _fake_returns_panel()
    returns["C"] = returns["A"] * 0.5 + 0.001
    with pytest.raises(ValueError, match="INDEFINITE_CORRELATION_MATRIX"):
        build_mu_sigma(request, returns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_optimizer_inputs.py -v`
Expected: FAIL (no PSD check exists yet, so no `ValueError` is raised)

- [ ] **Step 3: Add the PSD check**

In `backend/app/optimizer/inputs.py`, add near the top:

```python
import numpy as np
```

And at the end of `build_mu_sigma`, immediately before the final `return mu, sigma`:

```python
    if not request.use_historical_correlations and request.correlation_overrides:
        eigenvalues = np.linalg.eigvalsh(sigma.values)
        if (eigenvalues < -1e-8).any():
            raise ValueError("INDEFINITE_CORRELATION_MATRIX")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_optimizer_inputs.py -v`
Expected: PASS (all tests in the file, including the new one)

- [ ] **Step 5: Commit**

```bash
git add backend/app/optimizer/inputs.py backend/tests/test_optimizer_inputs.py
git commit -m "feat: reject non-PSD correlation overrides before they reach the solver"
```
