import pytest

from backend.app.optimizer.diagnostics import binding_constraints, build_trade_list
from backend.tests.test_optimizer_solvers_mean_variance import _two_asset_request


def test_max_weight_flagged_only_when_actually_hit():
    request = _two_asset_request("min_variance")
    request.constraints.max_weight_pct = 60
    weights_at_cap = {"A": 60.0, "B": 40.0}
    findings = binding_constraints(request, weights_at_cap)
    assert any("max weight" in f["label"] for f in findings)

    weights_under_cap = {"A": 55.0, "B": 45.0}
    findings_slack = binding_constraints(request, weights_under_cap)
    assert not any("max weight" in f["label"] for f in findings_slack)


def test_turnover_cap_flagged_only_when_actually_exceeded():
    request = _two_asset_request("min_variance")
    request.current_weight_pct = {"A": 70.0, "B": 30.0}
    request.constraints.max_turnover_pct = 5.0
    weights = {"A": 40.0, "B": 60.0}  # 30-point move, well over a 5% cap
    findings = binding_constraints(request, weights)
    assert any("turnover" in f["label"].lower() for f in findings)

    request.constraints.max_turnover_pct = 50.0  # cap well above what's needed
    findings_slack = binding_constraints(request, weights)
    assert not any("turnover" in f["label"].lower() for f in findings_slack)


def test_trade_list_computes_one_way_turnover():
    request = _two_asset_request("min_variance")
    request.current_weight_pct = {"A": 70.0, "B": 30.0}
    weights = {"A": 60.0, "B": 40.0}
    trades, turnover = build_trade_list(request, weights)
    assert turnover == pytest.approx(10.0, abs=0.01)
    sell_row = next(row for row in trades if row["projId"] == "A")
    assert sell_row["action"] == "sell"
