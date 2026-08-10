import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.comparison import (
    _clamp_and_renormalize,
    build_comparison_weights,
)


def test_build_benchmark_comparison_none_when_unset(two_real_fund_request_factory):
    from backend.app.optimizer.comparison import build_benchmark_comparison
    from backend.app.optimizer.inputs import build_returns_panel

    request = two_real_fund_request_factory("none")
    returns = build_returns_panel(request)
    result = build_benchmark_comparison(request, {"M0209_2548": 60.0, "M0155_2547": 40.0}, returns)
    assert result is None


def test_build_benchmark_comparison_against_real_cache(two_real_fund_request_factory):
    from backend.app.engine import metrics
    from backend.app.optimizer.comparison import build_benchmark_comparison
    from backend.app.optimizer.inputs import (
        build_returns_panel,
        load_benchmark_returns,
        portfolio_return_series,
    )

    request = two_real_fund_request_factory("none")
    request = request.model_copy(update={"benchmark_proj_id": "M0209_2548"})
    returns = build_returns_panel(request)
    optimal_weights = {"M0209_2548": 60.0, "M0155_2547": 40.0}

    result = build_benchmark_comparison(request, optimal_weights, returns)
    assert result is not None
    assert result["projId"] == "M0209_2548"
    assert result["displayName"] == "K-SET50"

    # Independently recompute both scored fields by hand via the same real
    # engine/metrics.py functions, proving the numbers are genuinely
    # computed -- not a placeholder, the exact defect class earlier
    # sub-projects' final reviews caught in fabricated fields.
    benchmark_returns = load_benchmark_returns("M0209_2548", request)
    portfolio_returns = portfolio_return_series(returns, optimal_weights)
    ppy = 12
    expected_excess = (
        metrics.annualized_return(portfolio_returns, ppy) - metrics.annualized_return(benchmark_returns, ppy)
    ) * 100
    expected_tracking_error = metrics.tracking_error(portfolio_returns, benchmark_returns, ppy) * 100
    assert result["excessReturnPct"] == pytest.approx(expected_excess, abs=0.01)
    assert result["trackingErrorPct"] == pytest.approx(expected_tracking_error, abs=0.01)


def test_build_benchmark_comparison_propagates_hard_error_on_missing_data(two_real_fund_request_factory, monkeypatch):
    from backend.app.optimizer import inputs as inputs_module
    from backend.app.optimizer.comparison import build_benchmark_comparison
    from backend.app.optimizer.inputs import build_returns_panel

    request = two_real_fund_request_factory("none")
    request = request.model_copy(update={"benchmark_proj_id": "NONEXISTENT_PROJ_ID"})
    returns = build_returns_panel(request)

    def fake_load_nav_panel(proj_ids):
        import pandas as pd
        # Match load_nav_panel's real empty-result shape (a DatetimeIndex,
        # not the RangeIndex a bare pd.DataFrame() carries) so this reaches
        # the same align_nav_panel code path a genuinely-missing proj_id
        # hits in production, rather than a resample() TypeError.
        return pd.DataFrame(index=pd.DatetimeIndex([], name="nav_date"))

    monkeypatch.setattr(inputs_module, "load_nav_panel", fake_load_nav_panel)
    with pytest.raises(ValueError, match="BENCHMARK_DATA_UNAVAILABLE"):
        build_benchmark_comparison(request, {"M0209_2548": 60.0, "M0155_2547": 40.0}, returns)


def test_build_benchmark_comparison_display_name_falls_back_to_universe_csv(two_real_fund_request_factory):
    from backend.app.optimizer.comparison import build_benchmark_comparison
    from backend.app.optimizer.inputs import build_returns_panel

    # M0155_2547 is NOT in this request's funds list, so its display name
    # must come from the mvp_fund_universe.csv lookup, not request.funds.
    # Built inline from scratch (mirroring two_real_fund_request_factory)
    # rather than a model_dump/model_validate round-trip, since funds
    # requires >= 2 items and this request needs exactly one.
    request = two_real_fund_request_factory("none")
    request = OptimizeRequest.model_validate({
        **request.model_dump(by_alias=True),
        "funds": [
            {"projId": "M0209_2548", "displayName": "K-SET50"},
            {"projId": "M0155_2547", "displayName": "M-S50"},
        ],
        "benchmarkProjId": "M0155_2547",
    })
    request = request.model_copy(update={"benchmark_proj_id": "M0155_2547"})
    returns = build_returns_panel(request)
    # Drop M0155_2547 from the *funds* list only (keep it in the returns
    # panel so load_benchmark_returns still has data), simulating a
    # benchmark that isn't one of the optimized funds.
    request = request.model_copy(update={"funds": [f for f in request.funds if f.proj_id != "M0155_2547"]})
    result = build_benchmark_comparison(request, {"M0209_2548": 100.0}, returns)
    assert result is not None
    assert result["projId"] == "M0155_2547"
    assert result["displayName"]  # non-empty; exact text depends on the committed CSV, don't hardcode it


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
