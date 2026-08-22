import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.core.limiter import limiter
from backend.app.domain.enums import ErrorCode
from backend.app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Both the route's blanket 10/minute limiter and the robust-optimization
    -specific limiter use module-level in-memory state that persists across
    the whole test session (same TestClient remote address every time). Reset
    both before each test so one test's request count doesn't bleed into the
    next test's rate-limit assertions."""
    from backend.app.api import optimize as optimize_module

    limiter.reset()
    optimize_module._robust_optimization_request_times.clear()
    yield
    limiter.reset()
    optimize_module._robust_optimization_request_times.clear()


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


def test_robust_optimization_requests_are_rate_limited_more_strictly():
    """A robust-optimization-specific limiter (2/minute) must fire
    independently of, and stricter than, the route's blanket 10/minute
    limiter -- proving it before only 3 requests would trip the blanket
    limit."""
    client = TestClient(app, raise_server_exceptions=False)
    payload = {**_valid_optimize_payload(), "robustOptimization": True}

    responses = [client.post("/api/optimize", json=payload) for _ in range(3)]
    statuses = [r.status_code for r in responses]

    assert statuses[:2].count(429) == 0
    assert statuses[2] == 429


def test_non_robust_requests_are_unaffected_by_the_robust_rate_limit():
    """3 consecutive non-robust requests must NOT trip the robust-specific
    limiter -- it only counts robustOptimization=true requests."""
    client = TestClient(app, raise_server_exceptions=False)
    payload = {**_valid_optimize_payload(), "robustOptimization": False}

    responses = [client.post("/api/optimize", json=payload) for _ in range(3)]
    assert all(r.status_code != 429 for r in responses)


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


def test_unknown_value_error_is_translated_to_coded_server_error():
    client = TestClient(app, raise_server_exceptions=False)

    with patch("backend.app.api.optimize.run_optimize", side_effect=ValueError("unexpected solver failure")):
        response = client.post("/api/optimize", json=_valid_optimize_payload())

    assert response.status_code == 500
    assert response.json()["code"] == ErrorCode.INTERNAL_ERROR


def test_successful_optimization_gets_a_persisted_run_url(monkeypatch, tmp_path):
    """A successful optimize response must be reloadable by its run id.

    The optimizer itself is mocked here so this test covers the API/storage
    seam without depending on a local riskfolio solver or NAV cache.
    """
    from backend.app.api import optimize as optimize_module

    monkeypatch.setattr(optimize_module, "RUNS_DIR", tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    class FakeOptimizeResult:
        def model_dump(self, **_kwargs):
            return {"feasibility": "ok", "generatedAt": "2026-08-12T00:00:00Z"}

    with patch("backend.app.api.optimize.run_optimize", return_value=FakeOptimizeResult()):
        created = client.post("/api/optimize", json=_valid_optimize_payload())

    assert created.status_code == 200
    body = created.json()
    assert body["runId"].startswith("run_")
    assert len(body["runId"].rsplit("_", 1)[-1]) == 32
    assert body["createdAt"]
    assert body["dataSource"] == "sec_open_data"
    assert (tmp_path / body["runId"] / "request.json").is_file()
    assert (tmp_path / body["runId"] / "result.json").is_file()

    loaded = client.get(f"/api/optimize/{body['runId']}")
    assert loaded.status_code == 200
    assert loaded.json()["runId"] == body["runId"]
    assert loaded.json()["request"]["funds"][0]["projId"] == "A"


def test_unknown_optimization_run_returns_run_not_found(monkeypatch, tmp_path):
    from backend.app.api import optimize as optimize_module

    monkeypatch.setattr(optimize_module, "RUNS_DIR", tmp_path)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/optimize/run_does_not_exist")

    assert response.status_code == 404
    assert response.json()["code"] == ErrorCode.RUN_NOT_FOUND


def test_corrupt_optimization_run_without_request_is_internal_error(monkeypatch, tmp_path):
    from backend.app.api import optimize as optimize_module

    monkeypatch.setattr(optimize_module, "RUNS_DIR", tmp_path)
    run_dir = tmp_path / "run_corrupt"
    run_dir.mkdir()
    (run_dir / "result.json").write_text(json.dumps({"runId": "run_corrupt"}), encoding="utf-8")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/optimize/run_corrupt")

    assert response.status_code == 500
    assert response.json()["code"] == ErrorCode.INTERNAL_ERROR
