import numpy as np
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
    # A deterministic alternating two-value series per fund makes both
    # funds move in lockstep, producing a rank-1 (singular) covariance
    # matrix that breaks the Sharpe-ratio SOCP transform the
    # black_litterman dispatch branch relies on (mean-variance's own QP
    # tolerates it, but Sharpe does not). Random-normal returns, matching
    # the pattern used by test_optimizer_smoke_matrix.py's synthetic panel,
    # keep the covariance full-rank for every goal including black_litterman.
    rng = np.random.default_rng(20260809)
    dates = pd.date_range("2020-01-31", periods=24, freq="ME")
    returns = pd.DataFrame(
        {
            "A": rng.normal(0.010, 0.04, size=24),
            "B": rng.normal(0.006, 0.02, size=24),
        },
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
            "tau": 0.05,
            "benchmarkExpectedReturnPct": 6.0,
            "views": [{
                "key": "v1", "assetProjId1": "A", "viewType": "absolute",
                "assetProjId2": None, "adjustedPerformancePct": 11.0, "confidence": 60,
            }],
        },
    )
    mu, sigma, returns = _mu_sigma_returns()
    weights = solvers.solve_for_goal(request, mu, sigma, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)
