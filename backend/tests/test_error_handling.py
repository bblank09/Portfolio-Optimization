from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app

VALID_PAYLOAD = {
    "assets": [{"proj_id": "M0209_2548", "display_name": "K-SET50", "weight": 100}],
    "start_date": "2021-06-30",
    "end_date": "2022-06-30",
    "initial_capital": 100000,
    "benchmark_proj_id": "M0209_2548",
    "risk_free_rate_pct": 0,
    "cashflow": {"enabled": False, "type": "contribution", "amount": 0, "frequency": "monthly", "timing": "end"},
    "rebalancing": {"mode": "none", "threshold_pct": 5},
    "costs": {"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
    "data": {"source": "sec_open_data", "price_field": "nav_per_unit", "frequency": "monthly"},
}


def test_unhandled_exception_returns_generic_json_not_a_stack_trace():
    # raise_server_exceptions=False: without it, TestClient re-raises the
    # exception into the test process instead of returning the HTTP response
    # a real client would see -- we need the actual response.
    client = TestClient(app, raise_server_exceptions=False)
    with patch("backend.app.api.backtests.run_backtest", side_effect=RuntimeError("boom: unexpected internal state")):
        response = client.post("/api/backtests", json=VALID_PAYLOAD)

    assert response.status_code == 500
    body = response.json()
    assert body == {"detail": "Internal server error", "code": "INTERNAL_ERROR"}
    # The real exception message/type must never reach the client.
    assert "boom" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text
