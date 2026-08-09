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
