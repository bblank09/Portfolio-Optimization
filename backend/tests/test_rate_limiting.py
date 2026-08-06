import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.core.limiter import limiter
from backend.app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # The limiter's in-memory counters are process-global, so requests other
    # tests already made against /api/backtests (same TestClient IP) would
    # otherwise count against this test's quota.
    limiter.reset()
    yield
    limiter.reset()


def _sample_payload(proj_id: str, display_name: str) -> dict:
    return {
        "assets": [{"proj_id": proj_id, "display_name": display_name, "weight": 100}],
        "start_date": "2021-06-30",
        "end_date": "2022-06-30",
        "initial_capital": 100000,
        "benchmark_proj_id": proj_id,
        "cashflow": {"enabled": False, "type": "contribution", "amount": 0, "frequency": "monthly", "timing": "end"},
        "rebalancing": {"mode": "none", "threshold_pct": 5},
        "costs": {"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
        "data": {"source": "sec_open_data", "price_field": "nav_per_unit", "frequency": "monthly"},
    }


def test_eleventh_backtest_request_within_a_minute_is_rate_limited():
    # Deployers with no infra experience have no reverse-proxy or WAF in front
    # of this API -- a single client hammering /api/backtests (accidentally,
    # via a buggy frontend retry loop, or on purpose) must not be able to peg
    # the CPU for every other visitor. 10 req/min/IP is generous for a human
    # clicking "Run backtest" but blocks a tight loop.
    universe = pd.read_csv("data/sec/mvp_fund_universe.csv")
    first = universe.iloc[0]
    payload = _sample_payload(first["proj_id"], first["display_name"])
    client = TestClient(app)

    responses = [client.post("/api/backtests", json=payload) for _ in range(11)]

    statuses = [r.status_code for r in responses]
    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429
