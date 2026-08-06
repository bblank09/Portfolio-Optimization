import pytest
from fastapi.testclient import TestClient

from backend.app.api.backtests import get_backtest
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


def test_get_backtest_by_id_returns_the_persisted_run_with_its_request():
    # Real backtest against real cached SEC data -- this is the exact
    # round-trip a shared URL needs: run once, then reload by run_id alone.
    client = TestClient(app)
    created = client.post("/api/backtests", json=VALID_PAYLOAD)
    assert created.status_code == 200
    run_id = created.json()["run_id"]

    response = client.get(f"/api/backtests/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["summary"]["ending_value"] == created.json()["summary"]["ending_value"]
    assert body["request"]["assets"][0]["proj_id"] == "M0209_2548"


def test_get_backtest_by_id_404s_for_an_unknown_run():
    client = TestClient(app)

    response = client.get("/api/backtests/run_does_not_exist")

    assert response.status_code == 404
    assert response.json()["code"] == "RUN_NOT_FOUND"


def test_get_backtest_by_id_rejects_path_traversal():
    # The ASGI layer normalizes ".." segments before Starlette's router ever
    # sees the path, so this request never actually reaches get_backtest()
    # -- it falls through to whatever matches the normalized path (here, the
    # SPA catch-all, since frontend/dist is built). The property that
    # actually matters is that no traversal-style URL can ever make its way
    # to a real filesystem read outside data/runs -- confirmed by the
    # response never containing real /etc/passwd content.
    client = TestClient(app)

    response = client.get("/api/backtests/..%2F..%2F..%2Fetc%2Fpasswd")

    assert "root:" not in response.text


def test_get_backtest_rejects_a_run_id_containing_a_literal_slash():
    # Belt-and-suspenders: even if a request somehow reached the handler
    # with a slash still in run_id (e.g. a future routing change), the
    # handler's own guard must still refuse it rather than trust it as a
    # filesystem path.
    with pytest.raises(Exception) as exc_info:
        get_backtest("../../etc/passwd")
    assert getattr(exc_info.value, "status_code", None) == 404
