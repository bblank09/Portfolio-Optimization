from fastapi.testclient import TestClient

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


def test_funds_endpoint_is_reachable_under_the_v1_prefix():
    # When frontend/dist is built (as it is after `npm run build`), main.py
    # mounts a GET catch-all that serves index.html for any unmatched path --
    # that would make a wrong route look like a 200 too. Assert the actual
    # funds payload shape, not just the status code, so this can't false-pass.
    client = TestClient(app)
    response = client.get("/api/v1/funds")
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "sec_open_data"
    assert "funds" in body


def test_backtests_endpoint_is_reachable_under_the_v1_prefix():
    client = TestClient(app)
    response = client.post("/api/v1/backtests", json=VALID_PAYLOAD)
    assert response.status_code == 200


def test_unversioned_legacy_path_still_works_as_an_alias():
    # Existing clients (including this app's own frontend, and every test
    # written before this change) hit the unversioned path -- it must keep
    # working during the migration window rather than breaking overnight.
    client = TestClient(app)
    response = client.get("/api/funds")
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "sec_open_data"
    assert "funds" in body
