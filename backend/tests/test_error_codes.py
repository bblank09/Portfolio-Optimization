from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app.api import funds as funds_module
from backend.app.api.backtests import create_backtest
from backend.app.core.errors import AppHTTPException
from backend.app.domain.enums import ErrorCode
from backend.app.domain.schemas import BacktestRequest
from backend.app.main import app

VALID_PAYLOAD = {
    "assets": [{"proj_id": "M0209_2548", "display_name": "K-SET50", "weight": 100}],
    "start_date": "2021-06-30",
    "end_date": "2022-06-30",
    "initial_capital": 100000,
    "benchmark_proj_id": "M0209_2548",
    "cashflow": {"enabled": False, "type": "contribution", "amount": 0, "frequency": "monthly", "timing": "end"},
    "rebalancing": {"mode": "none", "threshold_pct": 5},
    "costs": {"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
    "data": {"source": "sec_open_data", "price_field": "nav_per_unit", "frequency": "monthly"},
}


def test_unsupported_data_source_returns_a_stable_code():
    # `data.source` is a single-member pydantic enum today, so no payload can
    # reach this branch over HTTP -- it is defense-in-depth for a future
    # second data source. Exercised by calling the handler directly with a
    # request built via model_construct(), which bypasses that validation.
    backtest_request = BacktestRequest.model_validate(VALID_PAYLOAD)
    backtest_request.data = backtest_request.data.model_copy(update={"source": "not_sec_open_data"})
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/backtests",
        "headers": [],
        "client": ("testclient", 12345),
        "app": app,
    }
    fake_request = Request(scope)

    try:
        create_backtest(fake_request, backtest_request)
        raise AssertionError("expected AppHTTPException")
    except AppHTTPException as exc:
        assert exc.status_code == 400
        assert exc.code == ErrorCode.UNSUPPORTED_DATA_SOURCE
        assert exc.detail  # human message is preserved for existing clients


def test_missing_nav_cache_returns_a_stable_code():
    client = TestClient(app)
    with patch("backend.app.api.backtests.load_nav_panel", side_effect=FileNotFoundError("no cache")):
        response = client.post("/api/backtests", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert response.json()["code"] == "NAV_CACHE_MISSING"


def test_insufficient_nav_history_returns_a_stable_code():
    client = TestClient(app)
    with patch("backend.app.api.backtests.run_backtest", side_effect=ValueError("not enough NAV observations")):
        response = client.post("/api/backtests", json=VALID_PAYLOAD)

    assert response.status_code == 422
    assert response.json()["code"] == "INSUFFICIENT_NAV_HISTORY"


def test_missing_run_id_returns_a_stable_code():
    client = TestClient(app)

    response = client.get("/api/backtests/run_does_not_exist/report")

    assert response.status_code == 404
    assert response.json()["code"] == "RUN_NOT_FOUND"


def test_missing_fund_universe_cache_returns_a_stable_code():
    client = TestClient(app)
    with patch.object(funds_module, "UNIVERSE_PATH", Path("data/sec/does_not_exist.csv")):
        response = client.get("/api/funds")

    assert response.status_code == 503
    assert response.json()["code"] == "FUND_UNIVERSE_CACHE_MISSING"
