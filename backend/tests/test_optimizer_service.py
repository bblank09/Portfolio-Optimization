import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.service import run_optimize


@pytest.fixture
def two_real_fund_request() -> OptimizeRequest:
    # Uses two funds already confirmed present in this project's committed
    # NAV cache (see earlier sessions' live verification against
    # K-SET50 / M-S50) -- adjust proj_ids here if the cache is refreshed
    # and these particular ids are no longer present.
    #
    # Deviation from the brief's sample fixture: the brief's window
    # (2020-01-31..2023-12-31) leaves BOTH funds with an annualized mean
    # return below the fixture's 1.5% risk-free rate over that specific
    # stretch (confirmed against the real committed cache), which makes
    # riskfolio-lib's max_sharpe (Dinkelbach-style) reformulation
    # infeasible by construction -- there is no long-only portfolio with a
    # positive risk premium to maximize, so CLARABEL correctly reports no
    # solution. That is a real property of solvers.py's Sharpe formulation
    # (out of this task's scope to change), not a bug in service.py's
    # orchestration, so the fix here is a window where both funds clear the
    # risk-free rate (2016-01-31..2019-12-31, also verified against the
    # real cache) rather than touching solver logic.
    return OptimizeRequest.model_validate({
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


def test_run_optimize_end_to_end_against_real_cache(two_real_fund_request):
    result = run_optimize(two_real_fund_request)
    assert result.feasibility == "ok"
    assert sum(result.optimal_weights.values()) == pytest.approx(100, abs=0.5)
    # This fixture's two funds are both SET50 index trackers: over this window
    # one dominates the other on BOTH return and volatility, so the efficient
    # set is genuinely a single point. riskfolio returns 24 identical columns
    # anyway; build_frontier now collapses them (see frontier._dedupe_points)
    # rather than presenting duplicates as a curve. Asserting 24 here was
    # asserting the duplicates.
    assert len(result.frontier) >= 1
    assert len({(p.volatility_pct, p.expected_return_pct) for p in result.frontier}) == len(result.frontier)
    assert result.optimal_point.label == "Your optimal portfolio"


def test_run_optimize_populates_real_rolling_folds(two_real_fund_request):
    result = run_optimize(two_real_fund_request)
    assert len(result.rolling) >= 1
    for fold in result.rolling:
        assert fold.period_label
        assert fold.realized_volatility_pct >= 0
