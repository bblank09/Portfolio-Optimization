# Phase 5 sub-project 4: Portfolio Constraint Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `groupConstraintsEnabled`/`assetGroups` (group weight caps) and `maxHoldings` (a cardinality cap) real in `POST /api/optimize` — both are currently UI-selectable fields the backend never reads.

**Architecture:** Group constraints are extra rows appended to the existing per-fund `ainequality`/`binequality` linear-constraint matrix in `solvers._build_portfolio` — no new mechanism. `maxHoldings` is a greedy post-solve heuristic (a new module, `backend/app/optimizer/holdings.py`) since exact cardinality enforcement needs a Mixed-Integer solver this project doesn't have (verified: riskfolio-lib's own `card` parameter builds a boolean CVXPY variable, and of the installed free solvers only HiGHS/SCIPY are MI-capable, and HiGHS cannot solve the SOCP-based risk measures this project uses mixed with integers — confirmed via a direct test, `SolverError: The solver HIGHS cannot solve this problem`).

**Tech Stack:** Python, numpy (constraint matrix construction), the existing `backend/app/optimizer/*` modules, pytest.

## Global Constraints

- Group constraints reuse the SAME `ainequality`/`binequality` mechanism `_build_portfolio` already uses for per-fund bounds — append rows, never build a second/parallel constraint mechanism.
- `maxHoldings` is a best-effort heuristic, never an exact solver-level constraint — no MOSEK/GUROBI, no attempt to use riskfolio-lib's `card` parameter (confirmed MIP-only, incompatible with this project's free-solver-only rule).
- The heuristic's trim loop is capped at `original_fund_count - max_holdings` iterations by construction (removes exactly one fund per iteration) — it cannot loop indefinitely.
- A trim-loop solve failure is NEVER a hard error for the whole request — return the last successfully-solved weights with an explanatory `constraintNote`, same non-blocking-secondary-feature principle established in sub-projects 2 and 3.
- `constraintNote` is a NEW, separate `OptimizeResult` field — never reuse `robustNote`/`compareNote` for constraint-heuristic caveats (this project's established one-meaning-per-field rule).
- The heuristic's output weights become the FINAL `optimalWeights` used by everything downstream (frontier markers, diagnostics, performance summary, comparison) — not a side-channel.
- `Pydantic model_copy(update={...})` takes the model's actual Python field names (snake_case), NOT camelCase aliases — a known gotcha from sub-project 3 (`model_copy(update={"benchmarkProjId": ...})` silently does nothing; must be `model_copy(update={"benchmark_proj_id": ...})`). Apply this correctly for `fund_bounds`.
- Use `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3` for all commands (`pytest`, `ruff`) — never a bare `python3`/`pytest`.
- Every new module/function gets tests verified against this plan's own Step commands before moving to the next task.

---

### Task 1: Add `OptimizeResult.constraintNote`

**Files:**
- Modify: `backend/app/domain/optimize_schemas.py`
- Test: `backend/tests/test_optimize_schemas.py`

**Interfaces:**
- Produces: `OptimizeResult.constraint_note: str | None` (wire name `constraintNote`) — consumed by Task 3's `holdings.enforce_max_holdings` and Task 4's `service.py` wiring.

- [ ] **Step 1: Write the failing test**

Read `backend/tests/test_optimize_schemas.py` first to match its existing pattern for constructing a full valid `OptimizeResult` payload (the same pattern Task 2 of sub-project 3 used for `compareNote`). Add:

```python
def test_optimize_result_accepts_constraint_note():
    payload = _valid_optimize_result_payload()
    payload["constraintNote"] = "Trimmed 2 fund(s) to satisfy the 3-holding cap."
    result = OptimizeResult.model_validate(payload)
    assert result.constraint_note == "Trimmed 2 fund(s) to satisfy the 3-holding cap."

    payload["constraintNote"] = None
    result = OptimizeResult.model_validate(payload)
    assert result.constraint_note is None
```

If the file's helper for a valid payload has a different name than `_valid_optimize_result_payload`, use the file's real helper name (check Task 2 of sub-project 3's commit in this same file for the exact pattern already established).

- [ ] **Step 2: Run test to verify it fails**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimize_schemas.py -k constraint_note -v`
Expected: FAIL — extra field not permitted or `AttributeError`

- [ ] **Step 3: Add the field**

In `backend/app/domain/optimize_schemas.py`, add to `OptimizeResult` (immediately after `compare_note`):

```python
    compare_note: str | None
    constraint_note: str | None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimize_schemas.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the full existing optimizer test suite to confirm the expected, documented breakage**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py backend/tests/test_api_optimize.py -v`
Expected: FAIL — `service.py`'s `OptimizeResult.model_validate({...})` call does not yet include a `"constraintNote"` key, so every existing call now errors with a missing-field validation error. This is expected and gets fixed in Task 4, not this task — same pattern sub-project 3's Task 2 established for `compareNote`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/optimize_schemas.py backend/tests/test_optimize_schemas.py
git commit -m "feat: add OptimizeResult.constraintNote field"
```

---

### Task 2: Group constraints in `solvers._build_portfolio`

**Files:**
- Modify: `backend/app/optimizer/solvers.py`
- Test: `backend/tests/test_optimizer_solvers_group_constraints.py`

**Interfaces:**
- Modifies: `solvers._build_portfolio`'s internal `ainequality`/`binequality` construction — no signature change, same inputs/outputs, purely additive rows when `request.constraints.group_constraints_enabled` is true.
- No new public function — this task's effect is only observable through the existing `solve_for_goal`/`solve_mean_variance`/`solve_risk_parity` entry points, which already call `_build_portfolio` internally.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_optimizer_solvers_group_constraints.py`:

```python
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer import solvers


def _request(group_constraints_enabled: bool, asset_groups: dict, fund_groups: dict) -> OptimizeRequest:
    return OptimizeRequest.model_validate({
        "funds": [
            {"projId": "A", "displayName": "Fund A"},
            {"projId": "B", "displayName": "Fund B"},
            {"projId": "C", "displayName": "Fund C"},
            {"projId": "D", "displayName": "Fund D"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": fund_groups,
        "assetGroups": asset_groups,
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2021-12-31"},
        "dataFrequency": "monthly", "goal": "min_variance", "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": False, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": group_constraints_enabled, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })


def _mu_sigma_returns():
    # A and B are cheap/low-vol, C and D are the opposite -- a min_variance
    # solve with no group cap will naturally favor A/B heavily.
    dates = pd.date_range("2020-01-31", periods=24, freq="ME")
    returns = pd.DataFrame(
        {
            "A": [0.005, -0.002] * 12,
            "B": [0.004, -0.001] * 12,
            "C": [0.02, -0.018] * 12,
            "D": [0.022, -0.019] * 12,
        },
        index=dates,
    )
    pct = returns * 100
    mu = pct.mean() * 12
    sigma = pct.cov() * 12
    return mu, sigma, returns


def test_group_cap_binds_when_enabled():
    # Group "X" = {A, B} (the natural min-variance favorites), capped at 30%
    # combined -- forces the solver to hold at least 70% in C/D despite them
    # being far riskier, proving the cap actually constrains the solve.
    asset_groups = {
        "X": {"name": "Low vol", "minWeightPct": 0, "maxWeightPct": 30},
        "Y": {"name": "High vol", "minWeightPct": 0, "maxWeightPct": 100},
    }
    fund_groups = {"A": "X", "B": "X", "C": "Y", "D": "Y"}
    request = _request(True, asset_groups, fund_groups)
    mu, sigma, returns = _mu_sigma_returns()

    weights = solvers.solve_for_goal(request, mu, sigma, returns)
    group_x_total = weights["A"] + weights["B"]
    assert group_x_total <= 30 + 0.5
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_group_cap_ignored_when_disabled():
    asset_groups = {
        "X": {"name": "Low vol", "minWeightPct": 0, "maxWeightPct": 30},
        "Y": {"name": "High vol", "minWeightPct": 0, "maxWeightPct": 100},
    }
    fund_groups = {"A": "X", "B": "X", "C": "Y", "D": "Y"}
    request_capped = _request(True, asset_groups, fund_groups)
    request_uncapped = _request(False, asset_groups, fund_groups)
    mu, sigma, returns = _mu_sigma_returns()

    capped_weights = solvers.solve_for_goal(request_capped, mu, sigma, returns)
    uncapped_weights = solvers.solve_for_goal(request_uncapped, mu, sigma, returns)
    # With the cap disabled, the min-variance solve should favor A/B well
    # beyond the 30% cap that bound it in the capped case above.
    assert (uncapped_weights["A"] + uncapped_weights["B"]) > (capped_weights["A"] + capped_weights["B"])


def test_funds_not_in_any_group_are_unconstrained():
    # Only A/B are assigned to a group; C/D are absent from fund_groups
    # entirely and must remain unconstrained by the group mechanism.
    asset_groups = {"X": {"name": "Low vol", "minWeightPct": 0, "maxWeightPct": 10}}
    fund_groups = {"A": "X", "B": "X"}
    request = _request(True, asset_groups, fund_groups)
    mu, sigma, returns = _mu_sigma_returns()

    weights = solvers.solve_for_goal(request, mu, sigma, returns)
    assert (weights["A"] + weights["B"]) <= 10 + 0.5
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_group_cap_infeasible_against_real_cache_raises():
    # Same fixture funds as backend/tests/test_optimizer_service.py's
    # two_real_fund_request -- both confirmed present in the committed NAV
    # cache. Both funds placed in the SAME group, capped at 60% combined --
    # since a 2-fund, long-only, fully-invested request must sum to 100%,
    # capping the only group at 60% is infeasible BY CONSTRUCTION. This
    # proves the group-constraint rows genuinely reach the real solver
    # (against real NAV data, not just the synthetic fixture above) by
    # checking the solver correctly rejects an infeasible cap rather than
    # silently ignoring it and returning a solution that violates it.
    request = OptimizeRequest.model_validate({
        "funds": [
            {"projId": "M0209_2548", "displayName": "K-SET50"},
            {"projId": "M0155_2547", "displayName": "M-S50"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {"M0209_2548": "X", "M0155_2547": "X"},
        "assetGroups": {"X": {"name": "Both", "minWeightPct": 0, "maxWeightPct": 60}},
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
            "groupConstraintsEnabled": True, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    with pytest.raises(RuntimeError, match="SOLVER_NON_CONVERGENCE|INFEASIBLE_CONSTRAINTS"):
        solvers.solve_for_goal(request, mu, sigma, returns)


def test_group_cap_binds_against_real_cache_with_headroom():
    # Same two real funds, but the group cap (85%) leaves headroom for a
    # fully-invested 2-fund solve to satisfy it while still being tight
    # enough to bind against whichever fund max_sharpe would otherwise
    # concentrate in -- proves the cap actually constrains a SUCCESSFUL
    # real-cache solve, complementing the infeasible-cap test above.
    request = OptimizeRequest.model_validate({
        "funds": [
            {"projId": "M0209_2548", "displayName": "K-SET50"},
            {"projId": "M0155_2547", "displayName": "M-S50"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {"M0209_2548": "X"},
        "assetGroups": {"X": {"name": "K-SET50 only", "minWeightPct": 0, "maxWeightPct": 85}},
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
            "groupConstraintsEnabled": True, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    weights = solvers.solve_for_goal(request, mu, sigma, returns)
    assert weights["M0209_2548"] <= 85 + 0.5
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_solvers_group_constraints.py -v`
Expected: FAIL — `test_group_cap_binds_when_enabled` fails because the group cap is not yet enforced (group X's combined weight exceeds 30%)

- [ ] **Step 3: Add group-constraint rows to `_build_portfolio`**

In `backend/app/optimizer/solvers.py`, find the existing block:

```python
    lower, upper = _asset_bounds(request, proj_ids)
    n = len(proj_ids)
    a_upper = np.eye(n)
    a_lower = -np.eye(n)
    port.ainequality = np.vstack([a_upper, a_lower])
    port.binequality = np.array(upper + [-lo for lo in lower]).reshape(-1, 1)
```

Replace it with:

```python
    lower, upper = _asset_bounds(request, proj_ids)
    n = len(proj_ids)
    a_upper = np.eye(n)
    a_lower = -np.eye(n)
    rows_a = [a_upper, a_lower]
    rows_b = upper + [-lo for lo in lower]

    # Group weight caps: one extra row pair per group actually present in
    # asset_groups, ONLY when group_constraints_enabled -- reuses the exact
    # same A @ w <= b mechanism as the per-fund bounds above, just with a
    # row that sums the member funds instead of isolating one. Funds absent
    # from fund_groups are simply never included in any row, so they stay
    # unconstrained by this mechanism.
    if request.constraints.group_constraints_enabled:
        for group_letter, group in request.asset_groups.items():
            member_indices = [i for i, pid in enumerate(proj_ids) if request.fund_groups.get(pid) == group_letter]
            if not member_indices:
                continue
            row = np.zeros(n)
            row[member_indices] = 1.0
            rows_a.append(row.reshape(1, -1))
            rows_b.append(group.max_weight_pct / 100)
            rows_a.append((-row).reshape(1, -1))
            rows_b.append(-group.min_weight_pct / 100)

    port.ainequality = np.vstack(rows_a)
    port.binequality = np.array(rows_b).reshape(-1, 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_solvers_group_constraints.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full existing optimizer test suite to confirm no regression**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_solvers_mean_variance.py backend/tests/test_optimizer_solvers_risk_parity_hrp.py backend/tests/test_optimizer_solvers_dispatch.py backend/tests/test_optimizer_smoke_matrix.py -v -k "not compareNote and not constraintNote"`
Expected: PASS — every existing request in these files has `groupConstraintsEnabled: false` (check the fixtures to confirm), so this change must be a no-op for all of them; if any fixture has it `true` with a real `assetGroups`/`fundGroups` mapping, verify that specific test still passes with the new rows added (it should, since the new rows are additive to a matrix these tests were never checking group behavior against).

- [ ] **Step 6: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/solvers.py backend/tests/test_optimizer_solvers_group_constraints.py`
Expected: All checks passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/optimizer/solvers.py backend/tests/test_optimizer_solvers_group_constraints.py
git commit -m "feat: enforce groupConstraintsEnabled/assetGroups as solver-level linear constraints"
```

---

### Task 3: `holdings.py` — `enforce_max_holdings`

**Files:**
- Create: `backend/app/optimizer/holdings.py`
- Test: `backend/tests/test_holdings.py`

**Interfaces:**
- Consumes: `solvers.solve_for_goal(request, mu, sigma, returns) -> dict[str, float]` (existing), `FundBound` (existing Pydantic model from `backend.app.domain.optimize_schemas`).
- Produces: `holdings.enforce_max_holdings(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame) -> tuple[dict[str, float], str | None]` — the (possibly trimmed) final weights plus an optional explanatory note. Consumed by Task 4's `service.py` wiring.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_holdings.py`:

```python
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.holdings import enforce_max_holdings


def _request(max_holdings: int, fund_count: int = 4) -> OptimizeRequest:
    funds = [{"projId": chr(ord("A") + i), "displayName": f"Fund {chr(ord('A') + i)}"} for i in range(fund_count)]
    return OptimizeRequest.model_validate({
        "funds": funds,
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2021-12-31"},
        "dataFrequency": "monthly", "goal": "min_variance", "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": False, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": max_holdings,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })


def _mu_sigma_returns(fund_count: int = 4):
    dates = pd.date_range("2020-01-31", periods=24, freq="ME")
    data = {}
    for i in range(fund_count):
        # Distinct volatilities so min_variance naturally spreads weight
        # across multiple funds when uncapped -- the scenario that requires
        # trimming.
        scale = 0.003 * (i + 1)
        data[chr(ord("A") + i)] = [scale, -scale * 0.8] * 12
    returns = pd.DataFrame(data, index=dates)
    pct = returns * 100
    mu = pct.mean() * 12
    sigma = pct.cov() * 12
    return mu, sigma, returns


def test_no_trim_needed_when_already_within_cap():
    request = _request(max_holdings=4)
    mu, sigma, returns = _mu_sigma_returns()
    weights, note = enforce_max_holdings(request, mu, sigma, returns)
    assert note is None
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_trims_down_to_the_cap():
    request = _request(max_holdings=2)
    mu, sigma, returns = _mu_sigma_returns()
    weights, note = enforce_max_holdings(request, mu, sigma, returns)
    held = [pid for pid, w in weights.items() if w > 0.5]
    assert len(held) <= 2
    assert note is not None
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_cap_of_one_trims_to_a_single_holding():
    request = _request(max_holdings=1)
    mu, sigma, returns = _mu_sigma_returns()
    weights, note = enforce_max_holdings(request, mu, sigma, returns)
    held = [pid for pid, w in weights.items() if w > 0.5]
    assert len(held) == 1
    assert weights[held[0]] == pytest.approx(100, abs=0.5)
    assert note is not None


def test_never_exceeds_original_fund_count_minus_cap_iterations(monkeypatch):
    # A cap that can never be satisfied (every solve keeps returning all 4
    # funds nonzero) must still terminate, not loop forever -- verified by
    # capping the mock at fund_count - max_holdings calls and asserting no
    # further calls happen.
    import backend.app.optimizer.holdings as holdings_module

    request = _request(max_holdings=1, fund_count=4)
    mu, sigma, returns = _mu_sigma_returns(fund_count=4)
    call_count = {"n": 0}
    original_solve = holdings_module.solvers.solve_for_goal

    def counting_solve(req, m, s, r):
        call_count["n"] += 1
        return original_solve(req, m, s, r)

    monkeypatch.setattr(holdings_module.solvers, "solve_for_goal", counting_solve)
    enforce_max_holdings(request, mu, sigma, returns)
    # 1 initial solve + at most (4 - 1) = 3 trimming re-solves = 4 max.
    assert call_count["n"] <= 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_holdings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.optimizer.holdings'`

- [ ] **Step 3: Create `holdings.py`**

Create `backend/app/optimizer/holdings.py`:

```python
"""Greedy post-solve heuristic for maxHoldings (a cardinality cap). Exact
enforcement needs a Mixed-Integer solver -- confirmed via riskfolio-lib
7.3.0's own `card` parameter (constructs a boolean CVXPY variable) and a
direct test that HiGHS (the only free MI-capable solver installed) cannot
solve a mixed boolean + SOCP problem, only pure MILP. This project's risk
measures (std_dev/semi-variance/CVaR/CDaR) are all SOCP-based, so exact
cardinality is out of reach without MOSEK/GUROBI, which this project does
not use. See
docs/superpowers/specs/2026-08-10-phase5-portfolio-constraints-design.md
for the full research finding.
"""

from __future__ import annotations

import pandas as pd

from backend.app.domain.optimize_schemas import FundBound, OptimizeRequest
from backend.app.optimizer import solvers

# A weight below this is treated as "not really held" -- consistent with
# the tolerance diagnostics.py already uses for binding-constraint
# detection elsewhere in this codebase.
_MIN_HOLDING_PCT = 0.5


def enforce_max_holdings(
    request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame
) -> tuple[dict[str, float], str | None]:
    """Solves once via the normal dispatch; if more funds hold weight than
    request.constraints.max_holdings allows, iteratively pins the
    smallest-weight fund's bounds to zero (via a per-request fund_bounds
    override -- the same mechanism FundBound already provides, no new
    pinning mechanism) and re-solves, one fund at a time, until the held
    count is within the cap or a solve fails. A mid-loop failure returns
    the last successfully-solved weights (which may still exceed the cap)
    with a constraintNote explaining the shortfall -- never a hard error,
    the main solve result is always returned.
    """
    max_holdings = request.constraints.max_holdings
    weights = solvers.solve_for_goal(request, mu, sigma, returns)
    held = [pid for pid, w in weights.items() if w > _MIN_HOLDING_PCT]
    if len(held) <= max_holdings:
        return weights, None

    current_request = request
    last_good_weights = weights
    dropped: list[str] = []

    while True:
        held = [pid for pid, w in last_good_weights.items() if w > _MIN_HOLDING_PCT]
        if len(held) <= max_holdings:
            break

        smallest = min(held, key=lambda pid: last_good_weights[pid])
        candidate_bounds = dict(current_request.fund_bounds)
        candidate_bounds[smallest] = FundBound(min_weight_pct=0.0, max_weight_pct=0.0)
        candidate_request = current_request.model_copy(update={"fund_bounds": candidate_bounds})

        try:
            candidate_weights = solvers.solve_for_goal(candidate_request, mu, sigma, returns)
        except (ValueError, RuntimeError):
            note = (
                f"Could not fully trim to the {max_holdings}-holding cap: "
                f"{len(dropped)} fund(s) dropped ({', '.join(dropped)}) before the solve became "
                "infeasible; showing the last successful allocation."
            )
            return last_good_weights, note

        dropped.append(smallest)
        current_request = candidate_request
        last_good_weights = candidate_weights

    note = f"Trimmed {len(dropped)} fund(s) to satisfy the {max_holdings}-holding cap: {', '.join(dropped)}."
    return last_good_weights, note
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_holdings.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/holdings.py backend/tests/test_holdings.py`
Expected: All checks passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/optimizer/holdings.py backend/tests/test_holdings.py
git commit -m "feat: add holdings.enforce_max_holdings (greedy cardinality-cap heuristic)"
```

---

### Task 4: Wire into `service.py`, extend the smoke matrix

**Files:**
- Modify: `backend/app/optimizer/service.py`
- Modify: `backend/tests/test_optimizer_smoke_matrix.py`
- Test: `backend/tests/test_optimizer_service.py` (extend)

**Interfaces:**
- Consumes: `holdings.enforce_max_holdings(request, mu, sigma, returns) -> tuple[dict[str, float], str | None]` (Task 3).
- Produces: `OptimizeResult.optimalWeights` now reflects the max-holdings-trimmed result (when trimming was needed), and `.constraintNote` is genuinely populated. Every downstream consumer of `optimal_weights` in `run_optimize` (frontier markers, diagnostics, performance summary, comparison, risk contribution) automatically sees the trimmed weights since they all read the same local variable. No new public interface for later tasks — this is this plan's final integration point.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_optimizer_service.py`:

```python
def test_run_optimize_enforces_max_holdings(two_real_fund_request):
    # The fixture's 2-fund universe already satisfies any cap >= 2, so this
    # confirms the no-op path returns cleanly with constraint_note None.
    result = run_optimize(two_real_fund_request)
    assert result.constraint_note is None

    # A cap of 1 on a 2-fund universe MUST trigger real trimming.
    tight = two_real_fund_request.model_copy(
        update={"constraints": two_real_fund_request.constraints.model_copy(update={"max_holdings": 1})}
    )
    result = run_optimize(tight)
    held = [pid for pid, w in result.optimal_weights.items() if w > 0.5]
    assert len(held) == 1
    assert result.constraint_note is not None
```

If `OptimizeConstraints` fields aren't directly nested-copyable this way, check the real field name/type first — `two_real_fund_request.constraints` is itself a Pydantic model, so `.model_copy(update={"max_holdings": 1})` on it, then substituting the whole `constraints` object into the outer `model_copy`, is the correct two-level pattern; verify against the real schema before assuming it works as written.

- [ ] **Step 2: Run test to verify it fails**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py -v -k max_holdings`
Expected: FAIL — `OptimizeResult.model_validate` still errors on the missing `constraintNote` key (left broken since Task 1, by design), and even once that's visible, `optimal_weights` isn't yet trimmed

- [ ] **Step 3: Wire `holdings.enforce_max_holdings` into `run_optimize`**

In `backend/app/optimizer/service.py`:

Add to the imports (the existing `from backend.app.optimizer import (...)` block):

```python
from backend.app.optimizer import (
    black_litterman,
    comparison,
    diagnostics,
    frontier,
    holdings,
    inputs,
    report,
    rolling,
    solvers,
)
```

Replace this line:

```python
    optimal_weights = solvers.solve_for_goal(request, mu, sigma, returns)
```

with:

```python
    optimal_weights, constraint_note = holdings.enforce_max_holdings(request, mu, sigma, returns)
```

(`holdings.enforce_max_holdings` already calls `solvers.solve_for_goal` internally as its first step, so this is a direct one-line replacement, not an addition alongside the old call.)

Then add `"constraintNote": constraint_note,` to the `OptimizeResult.model_validate({...})` dict, placed next to the other `*Note` fields (`robustNote`, `compareNote`) for readability — check the exact current dict layout and insert it consistently with that grouping.

- [ ] **Step 4: Run test to verify it passes**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_optimizer_service.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Extend the smoke matrix with a max-holdings-constrained case**

Read `backend/tests/test_optimizer_smoke_matrix.py` in full first (enum-driven, parametrized over `ObjectiveGoal` × `RiskMeasure` × `CompareAgainst`, 112 cases as of sub-project 3). Add this assertion to the existing parametrized test function's body, after whatever it currently asserts:

```python
    # Every combination must respect optimal_weights never exceeding
    # max_holdings, whether or not trimming was actually needed for this
    # specific fixture/cap combination.
    held_count = sum(1 for w in result.optimal_weights.values() if w > 0.5)
    assert held_count <= request.constraints.max_holdings
```

Check the fixture's current `maxHoldings` value — if it's set high enough that this fixture's universe never needs trimming (e.g. `20` against a 2-3 fund panel), that's fine, the assertion still holds trivially true for every combination and remains a real regression guard for any FUTURE change that breaks the cap. Do not lower the fixture's fund count or artificially force trimming here — this task's Task 3 unit tests already prove the trimming logic itself works; this smoke-matrix assertion's job is proving the WIRING doesn't silently drop the cap check across all 7×4×4 combinations, matching the same "would this smoke test have caught the bug" bar sub-project 3's final review applied.

- [ ] **Step 6: Run the full relevant test set**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests/test_holdings.py backend/tests/test_optimizer_solvers_group_constraints.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py backend/tests/test_optimize_schemas.py backend/tests/test_comparison.py backend/tests/test_api_optimize.py -v`
Expected: PASS, all tests

- [ ] **Step 7: Run ruff**

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m ruff check backend/app/optimizer/service.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py`
Expected: All checks passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/optimizer/service.py backend/tests/test_optimizer_service.py backend/tests/test_optimizer_smoke_matrix.py
git commit -m "feat: wire holdings.enforce_max_holdings into service.run_optimize"
```

---

## After all tasks: full suite verification

Run the full backend suite once, as the final check before this plan's own final review:

Run: `/private/tmp/sec_open_data_portfolio_backtester_venv/bin/python3 -m pytest backend/tests -q`
Expected: all pass (the one pre-existing slow, unrelated test — `test_api_backtests.py::test_backtest_endpoint_uses_sec_cache_and_persists_run`, ~15 minutes — is not a regression from this plan; do not investigate it, per prior sub-projects' final review precedent).
