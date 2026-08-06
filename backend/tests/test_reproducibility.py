import json
from pathlib import Path

import pandas as pd
import pytest

import scripts.sec_verify_run_reproducibility as verifier
from backend.app.domain.schemas import BacktestRequest


def test_reproducibility_summary_keys_are_explicit():
    assert "ending_value" in verifier.SUMMARY_KEYS
    assert "max_drawdown" in verifier.SUMMARY_KEYS
    assert "benchmark_excess_return" in verifier.SUMMARY_KEYS


def test_verifier_uses_saved_artifacts_and_compares_recomputed_summary(tmp_path, monkeypatch):
    run_id = "saved-run"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    request = BacktestRequest(
        assets=[{"proj_id": "FUND_A", "display_name": "Fund A", "weight": 100}],
        start_date="2020-01-31",
        end_date="2020-02-29",
        initial_capital=1000,
        benchmark_proj_id="FUND_A",
        cashflow={"enabled": False, "type": "contribution", "amount": 0, "frequency": "monthly", "timing": "end"},
        rebalancing={"mode": "none"},
        costs={"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
        data={"source": "sec_open_data", "price_field": "nav_per_unit"},
    )
    stored_summary = {key: 0 for key in verifier.SUMMARY_KEYS}
    (run_dir / "request.json").write_text(json.dumps(request.model_dump(mode="json")), encoding="utf-8")
    (run_dir / "result.json").write_text(json.dumps({"summary": stored_summary}), encoding="utf-8")

    monkeypatch.setattr(verifier, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(verifier, "load_nav_panel", lambda proj_ids: pd.DataFrame({"FUND_A": [10, 10]}))
    monkeypatch.setattr(verifier, "align_nav_panel", lambda nav: nav)
    monkeypatch.setattr(verifier, "run_backtest", lambda request, nav: {"summary": stored_summary})
    monkeypatch.chdir(tmp_path)

    result = verifier.verify_run_reproducibility(run_id)

    assert result["ok"] is True
    assert set(result["diffs"]) == set(verifier.SUMMARY_KEYS)
    assert Path.cwd() == tmp_path


def test_verifier_reports_missing_saved_run(tmp_path, monkeypatch):
    monkeypatch.setattr(verifier, "RUNS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError, match="Saved run directory not found"):
        verifier.verify_run_reproducibility("missing-run")


def test_verifier_fails_when_a_saved_summary_key_is_missing(tmp_path, monkeypatch):
    run_id = "incomplete-run"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    request = BacktestRequest(
        assets=[{"proj_id": "FUND_A", "display_name": "Fund A", "weight": 100}],
        start_date="2020-01-31",
        end_date="2020-02-29",
        initial_capital=1000,
        benchmark_proj_id="FUND_A",
        cashflow={"enabled": False, "type": "contribution", "amount": 0, "frequency": "monthly", "timing": "end"},
        rebalancing={"mode": "none"},
        costs={"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
        data={"source": "sec_open_data", "price_field": "nav_per_unit"},
    )
    recomputed_summary = {key: 0 for key in verifier.SUMMARY_KEYS}
    stored_summary = recomputed_summary.copy()
    del stored_summary["sharpe"]
    (run_dir / "request.json").write_text(json.dumps(request.model_dump(mode="json")), encoding="utf-8")
    (run_dir / "result.json").write_text(json.dumps({"summary": stored_summary}), encoding="utf-8")

    monkeypatch.setattr(verifier, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(verifier, "load_nav_panel", lambda proj_ids: pd.DataFrame({"FUND_A": [10, 10]}))
    monkeypatch.setattr(verifier, "align_nav_panel", lambda nav: nav)
    monkeypatch.setattr(verifier, "run_backtest", lambda request, nav: {"summary": recomputed_summary})

    result = verifier.verify_run_reproducibility(run_id)

    assert result["ok"] is False
    assert result["diffs"]["sharpe"]["match"] is False
    assert result["diffs"]["sharpe"]["missing"] == {"stored": True, "recomputed": False}


def test_verifier_allows_an_explicitly_null_metric_on_both_sides():
    assert verifier.diff_value(None, None)["match"] is True
