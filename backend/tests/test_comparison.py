import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.comparison import (
    _clamp_and_renormalize,
    build_comparison_weights,
)


def test_clamp_and_renormalize_respects_a_tight_cap():
    # 3 equal-raw-share funds, A capped at 20% (below its 1/3 raw share) --
    # hand-computed expected result: A pins at its cap, remaining 80% of
    # the budget splits evenly across B and C (40% each).
    raw = {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}
    lower = [0.0, 0.0, 0.0]
    upper = [0.20, 1.0, 1.0]
    result = _clamp_and_renormalize(raw, lower, upper, ["A", "B", "C"])
    assert result["A"] == pytest.approx(20.0, abs=0.01)
    assert result["B"] == pytest.approx(40.0, abs=0.01)
    assert result["C"] == pytest.approx(40.0, abs=0.01)
    assert sum(result.values()) == pytest.approx(100.0, abs=0.01)


def test_clamp_and_renormalize_is_a_no_op_when_no_bound_binds():
    raw = {"A": 0.5, "B": 0.3, "C": 0.2}
    lower = [0.0, 0.0, 0.0]
    upper = [1.0, 1.0, 1.0]
    result = _clamp_and_renormalize(raw, lower, upper, ["A", "B", "C"])
    assert result["A"] == pytest.approx(50.0, abs=0.01)
    assert result["B"] == pytest.approx(30.0, abs=0.01)
    assert result["C"] == pytest.approx(20.0, abs=0.01)


@pytest.fixture
def two_real_fund_request_factory():
    def make(compare_against: str, current_weight_pct: dict | None = None):
        return OptimizeRequest.model_validate({
            "funds": [
                {"projId": "M0209_2548", "displayName": "K-SET50"},
                {"projId": "M0155_2547", "displayName": "M-S50"},
            ],
            "fundBounds": {}, "currentWeightPct": current_weight_pct or {}, "fundGroups": {},
            "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
            "timePeriod": {"startDate": "2016-01-31", "endDate": "2019-12-31"},
            "dataFrequency": "monthly", "goal": "max_sharpe", "riskMeasure": "std_dev",
            "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
            "robustOptimization": False, "useHistoricalReturns": True,
            "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
            "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
            "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": None,
            "benchmarkProjId": None,
            "constraints": {
                "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
                "groupConstraintsEnabled": False, "maxHoldings": 20,
                "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
                "riskFreeRatePct": 1.5, "compareAgainst": compare_against,
                "maxTurnoverPct": None, "maxTrackingErrorPct": None,
            },
        })
    return make


@pytest.mark.parametrize("compare_against", ["equal_weighted", "max_sharpe", "inverse_volatility", "risk_parity"])
def test_build_comparison_weights_against_real_cache(two_real_fund_request_factory, compare_against):
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    request = two_real_fund_request_factory(compare_against)
    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    weights, note = build_comparison_weights(request, mu, sigma, returns)
    assert weights is not None
    assert note is None
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_build_comparison_weights_none_returns_none():
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    request = OptimizeRequest.model_validate({
        "funds": [
            {"projId": "M0209_2548", "displayName": "K-SET50"},
            {"projId": "M0155_2547", "displayName": "M-S50"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2016-01-31", "endDate": "2019-12-31"},
        "dataFrequency": "monthly", "goal": "max_sharpe", "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": False, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })
    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    weights, note = build_comparison_weights(request, mu, sigma, returns)
    assert weights is None
    assert note is None


def test_build_comparison_weights_current_with_no_holdings_returns_none(two_real_fund_request_factory):
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    request = two_real_fund_request_factory("current", current_weight_pct={})
    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    weights, note = build_comparison_weights(request, mu, sigma, returns)
    assert weights is None
    assert note is None


def test_build_comparison_weights_current_with_holdings(two_real_fund_request_factory):
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    request = two_real_fund_request_factory("current", current_weight_pct={"M0209_2548": 60.0, "M0155_2547": 40.0})
    returns = build_returns_panel(request)
    mu, sigma = build_mu_sigma(request, returns)
    weights, _note = build_comparison_weights(request, mu, sigma, returns)
    assert weights == {"M0209_2548": 60.0, "M0155_2547": 40.0}
