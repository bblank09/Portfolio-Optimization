import logging

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app

LOGGER_NAME = "app.backtests"


def _sample_payload(proj_id: str, display_name: str, *, benchmark_proj_id: str | None = None) -> dict:
    return {
        "assets": [{"proj_id": proj_id, "display_name": display_name, "weight": 100}],
        "start_date": "2021-06-30",
        "end_date": "2022-06-30",
        "initial_capital": 100000,
        "benchmark_proj_id": benchmark_proj_id or proj_id,
        "cashflow": {"enabled": False, "type": "contribution", "amount": 0, "frequency": "monthly", "timing": "end"},
        "rebalancing": {"mode": "none", "threshold_pct": 5},
        "costs": {"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
        "data": {"source": "sec_open_data", "price_field": "nav_per_unit", "frequency": "monthly"},
    }


def test_successful_backtest_logs_request_details_and_duration(caplog):
    universe = pd.read_csv("data/sec/mvp_fund_universe.csv")
    first = universe.iloc[0]
    payload = _sample_payload(first["proj_id"], first["display_name"])
    client = TestClient(app)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = client.post("/api/backtests", json=payload)

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    messages = [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME]
    combined = " ".join(messages)
    # The log must actually name which funds and date range were requested
    # (that's the entire point -- being able to reconstruct what happened
    # from stdout when a deployer with no debugger reports "it broke").
    assert first["proj_id"] in combined
    assert "2021-06-30" in combined and "2022-06-30" in combined
    assert run_id in combined
    # And it must record how long the computation took, to catch slow
    # requests without needing a separate profiler.
    assert any("duration" in message.lower() or "elapsed" in message.lower() or "s\"" in message or "ms" in message for message in messages)


def test_failed_backtest_logs_the_error_before_the_generic_500(caplog):
    # A benchmark proj_id that does not exist anywhere in the NAV cache is a
    # genuine application-level failure (not a Pydantic validation rejection),
    # so it reaches our own code and is exactly the case where an operator
    # needs the log line to know *which* request failed and why.
    universe = pd.read_csv("data/sec/mvp_fund_universe.csv")
    first = universe.iloc[0]
    payload = _sample_payload(first["proj_id"], first["display_name"], benchmark_proj_id="NOT_A_REAL_FUND_ID")
    client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = client.post("/api/backtests", json=payload)

    assert response.status_code >= 400
    messages = [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME]
    combined = " ".join(messages)
    assert "NOT_A_REAL_FUND_ID" in combined
