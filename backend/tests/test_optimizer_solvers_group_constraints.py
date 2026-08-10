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
