from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.domain.enums import ErrorCode
from backend.app.main import app


def _valid_optimize_payload() -> dict:
    """Minimal valid optimize request payload."""
    return {
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
            "longOnly": True,
            "minWeightPct": 0,
            "maxWeightPct": 100,
            "groupConstraintsEnabled": False,
            "maxHoldings": 20,
            "lookbackPeriodMonths": 6,
            "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5,
            "compareAgainst": "none",
            "maxTurnoverPct": None,
            "maxTrackingErrorPct": None,
        },
    }


def test_indefinite_correlation_matrix_returns_correct_error_code():
    """Verify that ValueError('INDEFINITE_CORRELATION_MATRIX') maps to
    ErrorCode.INDEFINITE_CORRELATION_MATRIX in the API response."""
    client = TestClient(app, raise_server_exceptions=False)

    # Mock run_optimize to raise the INDEFINITE_CORRELATION_MATRIX error
    with patch("backend.app.api.optimize.run_optimize", side_effect=ValueError("INDEFINITE_CORRELATION_MATRIX")):
        payload = _valid_optimize_payload()
        response = client.post("/api/optimize", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == ErrorCode.INDEFINITE_CORRELATION_MATRIX
    assert "Indefinite Correlation Matrix" in body["detail"]


def test_insufficient_nav_history_returns_correct_error_code():
    """Verify that existing ValueError('INSUFFICIENT_NAV_HISTORY') still
    maps correctly to ErrorCode.INSUFFICIENT_NAV_HISTORY."""
    client = TestClient(app, raise_server_exceptions=False)

    with patch("backend.app.api.optimize.run_optimize", side_effect=ValueError("INSUFFICIENT_NAV_HISTORY")):
        payload = _valid_optimize_payload()
        response = client.post("/api/optimize", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == ErrorCode.INSUFFICIENT_NAV_HISTORY
    assert "Insufficient Nav History" in body["detail"]


def test_missing_nav_cache_returns_nav_cache_missing():
    """Mirrors the sibling /api/backtests route: a missing parquet cache is a
    503 NAV_CACHE_MISSING, not an unhandled 500."""
    client = TestClient(app, raise_server_exceptions=False)

    with patch("backend.app.api.optimize.run_optimize", side_effect=FileNotFoundError("data/sec/normalized")):
        response = client.post("/api/optimize", json=_valid_optimize_payload())

    assert response.status_code == 503
    assert response.json()["code"] == ErrorCode.NAV_CACHE_MISSING


def test_unexpected_exception_is_translated_to_coded_server_error():
    """riskfolio-lib's internals raise bare KeyError/NameError on unsupported
    parameter combinations (the final review hit both). Those must surface as
    a coded 500, not as a raw unhandled exception."""
    client = TestClient(app, raise_server_exceptions=False)

    for error in (KeyError("black_litterman"), NameError("The limits of the frontier can't be found")):
        with patch("backend.app.api.optimize.run_optimize", side_effect=error):
            response = client.post("/api/optimize", json=_valid_optimize_payload())
        assert response.status_code == 500
        assert response.json()["code"] == ErrorCode.INTERNAL_ERROR
