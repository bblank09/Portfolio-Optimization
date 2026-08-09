"""End-to-end smoke coverage for every objective x risk-measure combination.

The final whole-branch review found two goals that raised on EVERY request --
``black_litterman`` (bare ``KeyError`` from ``solvers._OBJ_CODES``) and
``max_return_target_vol`` (``NameError: The limits of the frontier can't be
found``, because the frontier sweep inherited the goal's ``upperdev``
ceiling). Neither had any test exercising it end-to-end, so both reached the
merge checkpoint as guaranteed HTTP 500s.

This file closes that hole: 7 goals x 4 risk measures = 28 combinations, all
driven through ``service.run_optimize``. It deliberately does NOT deep-check
every response field -- its job is to prove each combination is reachable
without crashing and returns a structurally valid ``OptimizeResult``.

The returns panel is synthetic and injected via monkeypatch rather than read
from the committed NAV cache, for two reasons: the run stays offline and
deterministic, and the three assets can be given genuinely different
means/volatilities with low cross-correlation so the frontier does not
collapse to the degenerate single point that the real two-SET50-tracker
fixture in test_optimizer_service.py produces.
"""

import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import (
    ObjectiveGoal,
    OptimizeRequest,
    OptimizeResult,
    RiskMeasure,
)
from backend.app.optimizer import inputs, service

PROJ_IDS = ["A", "B", "C"]


def _synthetic_returns() -> pd.DataFrame:
    """96 months of independent monthly returns with clearly separated
    risk/return profiles, so no asset dominates another on both axes and the
    efficient frontier is a real curve rather than a single point."""
    rng = np.random.default_rng(20260808)
    dates = pd.date_range("2016-01-31", periods=96, freq="ME")
    return pd.DataFrame(
        {
            "A": rng.normal(0.010, 0.055, size=96),  # high return, high vol
            "B": rng.normal(0.006, 0.025, size=96),  # mid / mid
            "C": rng.normal(0.003, 0.010, size=96),  # low return, low vol
        },
        index=dates,
    )


def _request(goal: str, risk_measure: str) -> OptimizeRequest:
    payload = {
        "funds": [{"projId": p, "displayName": f"Fund {p}"} for p in PROJ_IDS],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2016-01-31", "endDate": "2023-12-31"},
        "dataFrequency": "monthly",
        "goal": goal,
        "riskMeasure": risk_measure,
        "tailConfidence": 95,
        "targetAnnualVolatilityPct": 12.0,
        "targetAnnualReturnPct": 5.0,
        "robustOptimization": False,
        "useHistoricalReturns": True, "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample",
        "blackLitterman": None, "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    }
    if goal == "black_litterman":
        payload["blackLitterman"] = {
            "riskAversion": 2.5,
            "tau": 0.05,
            "benchmarkExpectedReturnPct": 7.0,
            "views": [{
                "key": "v1", "assetProjId1": "A", "viewType": "absolute",
                "assetProjId2": None, "adjustedPerformancePct": 11.0, "confidence": 60,
            }],
        }
    return OptimizeRequest.model_validate(payload)


@pytest.fixture
def synthetic_panel(monkeypatch):
    returns = _synthetic_returns()
    monkeypatch.setattr(inputs, "build_returns_panel", lambda request: returns)
    return returns


@pytest.mark.parametrize("goal", [g.value for g in ObjectiveGoal])
@pytest.mark.parametrize("risk_measure", [m.value for m in RiskMeasure])
def test_every_goal_and_risk_measure_combination_is_reachable(goal, risk_measure, synthetic_panel):
    result = service.run_optimize(_request(goal, risk_measure))

    assert isinstance(result, OptimizeResult)
    assert set(result.optimal_weights) == set(PROJ_IDS)
    assert sum(result.optimal_weights.values()) == pytest.approx(100, abs=0.5)
    assert all(w >= -1e-6 for w in result.optimal_weights.values())
    # The reported risk measure must be the one that was requested, and it
    # must carry a real (finite, non-negative) value -- not a placeholder.
    assert result.selected_risk_measure.measure.value == risk_measure
    assert np.isfinite(result.selected_risk_measure.optimized_value)
    assert result.selected_risk_measure.optimized_value >= 0
    # Risk contribution is a real decomposition summing to 100, not 100/n.
    assert sum(result.risk_contribution_pct.values()) == pytest.approx(100, abs=0.5)
    assert result.frontier
