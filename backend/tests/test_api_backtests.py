from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.data.quality import align_nav_panel
from backend.app.main import app
from backend.app.sec.cache import load_nav_panel


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data_source": "sec_open_data"}


def test_funds_endpoint_returns_cached_sec_universe():
    client = TestClient(app)
    response = client.get("/api/funds")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_source"] == "sec_open_data"
    assert len(payload["funds"]) >= 2
    assert {"proj_id", "display_name"}.issubset(payload["funds"][0].keys())


def test_testable_range_endpoint_finds_the_real_gap_free_window():
    # K-SET50 (M0209_2548) has the known real 2024-06 to 2024-11 SEC-wide
    # gap in its actual cached history -- the endpoint must route around
    # it (return a window entirely before or after it), not just report
    # the outer nav_start..nav_end bounds that still contain the gap.
    client = TestClient(app)
    response = client.get("/api/funds/testable-range", params={"proj_ids": "M0209_2548"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["start"] is not None and payload["end"] is not None
    assert not ("2024-07" <= payload["start"][:7] <= "2024-10") or not ("2024-07" <= payload["end"][:7] <= "2024-10")
    start, end = pd.Timestamp(payload["start"]), pd.Timestamp(payload["end"])
    gap_start, gap_end = pd.Timestamp("2024-07-01"), pd.Timestamp("2024-10-31")
    assert end < gap_start or start > gap_end, f"window {payload} still overlaps the known 2024 gap"


def test_testable_range_endpoint_handles_an_unknown_proj_id():
    client = TestClient(app)
    response = client.get("/api/funds/testable-range", params={"proj_ids": "NOT_A_REAL_FUND"})
    assert response.status_code == 200
    assert response.json() == {"start": None, "end": None}


def test_backtest_endpoint_uses_sec_cache_and_persists_run():
    result = create_sample_backtest()
    assert result["data_source"] == "sec_open_data"
    assert result["summary"]["ending_value"] > 0
    assert not any(issue["code"] == "stale_nav" for issue in result["quality_issues"])
    run_dir = Path("data/runs") / result["run_id"]
    assert (run_dir / "request.json").exists()
    assert (run_dir / "result.json").exists()


def test_backtest_report_endpoint_exports_research_report_markdown():
    result = create_sample_backtest()
    client = TestClient(app)
    response = client.get(f"/api/backtests/{result['run_id']}/report")
    assert response.status_code == 200
    report = response.text
    assert "SEC Open Data" in report
    assert "Formula Reference" in report
    assert "Limitations" in report
    assert "mock" not in report.lower()
    assert (Path("data/runs") / result["run_id"] / "research_report.md").exists()


@lru_cache(maxsize=1)
def sample_window() -> tuple[str, str, str, str]:
    universe = pd.read_csv("data/sec/mvp_fund_universe.csv")
    funds = universe[["proj_id", "display_name"]].drop_duplicates()
    ordered_proj_ids = funds["proj_id"].tolist()
    panel = align_nav_panel(load_nav_panel(ordered_proj_ids)).sort_index()
    # A universe entry with zero downloaded NAV rows (a fund SEC has no
    # published NAV for in the requested window at all) never gets a column
    # in the pivoted panel -- restrict to what the panel actually has so the
    # pair search below doesn't index a proj_id that isn't there.
    ordered_proj_ids = [proj_id for proj_id in ordered_proj_ids if proj_id in panel.columns]
    best: tuple[int, pd.Timestamp, str, str, pd.Timestamp, pd.Timestamp] | None = None

    for first_index, first_proj_id in enumerate(ordered_proj_ids):
        for second_proj_id in ordered_proj_ids[first_index + 1 :]:
            pair = panel[[first_proj_id, second_proj_id]].dropna(how="any")
            if len(pair) < 12:
                continue
            periods = pd.PeriodIndex(pair.index, freq="M")
            run_start = 0
            for index in range(1, len(periods) + 1):
                gap_detected = index == len(periods) or periods[index] != periods[index - 1] + 1
                if not gap_detected:
                    continue
                run = pair.iloc[run_start:index]
                if len(run) >= 12:
                    candidate = (len(run), run.index[-1], first_proj_id, second_proj_id, run.index[0], run.index[-1])
                    if best is None or candidate > best:
                        best = candidate
                run_start = index

    assert best is not None, "No SEC cache pair has a continuous 12-month overlap for the API integration test."
    _, _, first_proj_id, second_proj_id, start_date, end_date = best
    return (
        first_proj_id,
        second_proj_id,
        start_date.date().isoformat(),
        end_date.date().isoformat(),
    )


def create_sample_backtest() -> dict:
    universe = pd.read_csv("data/sec/mvp_fund_universe.csv")
    first_proj_id, second_proj_id, start_date, end_date = sample_window()
    first = universe.loc[universe["proj_id"] == first_proj_id].iloc[0]
    second = universe.loc[universe["proj_id"] == second_proj_id].iloc[0]
    payload = {
        "assets": [
            {"proj_id": first["proj_id"], "display_name": first["display_name"], "weight": 50},
            {"proj_id": second["proj_id"], "display_name": second["display_name"], "weight": 50},
        ],
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": 100000,
        "benchmark_proj_id": first["proj_id"],
        "cashflow": {"enabled": False, "type": "contribution", "amount": 0, "frequency": "monthly", "timing": "end"},
        "rebalancing": {"mode": "annual"},
        "costs": {"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
        "data": {"source": "sec_open_data", "price_field": "nav_per_unit"},
    }
    client = TestClient(app)
    response = client.post("/api/backtests", json=payload)
    assert response.status_code == 200
    return response.json()
