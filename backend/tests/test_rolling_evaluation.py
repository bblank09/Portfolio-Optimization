import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.rolling import run_rolling_evaluation


@pytest.fixture
def two_real_fund_request() -> OptimizeRequest:
    # Same fixture funds/window as backend/tests/test_optimizer_service.py's
    # two_real_fund_request -- both confirmed present in the committed NAV
    # cache. Monthly data, quarterly optimization_frequency: 48 months
    # (2016-01-31..2019-12-31) is 16 quarters -> 15 folds.
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


def _load_returns(request: OptimizeRequest) -> pd.DataFrame:
    from backend.app.optimizer.inputs import build_returns_panel
    return build_returns_panel(request)


def test_rolling_evaluation_against_real_cache_produces_folds_from_real_metrics(two_real_fund_request):
    returns = _load_returns(two_real_fund_request)
    folds, _note = run_rolling_evaluation(two_real_fund_request, returns)
    assert len(folds) >= 1
    for fold in folds:
        assert set(fold) == {"periodLabel", "realizedReturnPct", "realizedVolatilityPct", "realizedSharpe"}
        assert isinstance(fold["periodLabel"], str)
        assert fold["realizedVolatilityPct"] >= 0

    # Independently recompute the FIRST fold's realized stats by hand from
    # the same training/test slices run_rolling_evaluation itself would
    # have used, via the real engine/metrics.py functions -- proving the
    # returned numbers are genuinely computed, not a placeholder, the exact
    # defect class the sub-project 1 final review caught in
    # performanceSummary/riskContributionPct.
    from backend.app.engine import metrics
    from backend.app.optimizer import inputs, solvers
    from backend.app.optimizer.rolling import (
        build_fold_schedule,
        min_train_observations,
    )

    schedule = build_fold_schedule(returns.index, "quarterly")
    # run_rolling_evaluation drops folds whose expanding training window has
    # fewer than min_train_observations(fund_count) rows before attempting
    # any solve, so the first fold it actually returns is the first *usable*
    # one, not necessarily schedule[0] -- with this fixture's real NAV cache,
    # the first return observation lands a month after startDate (pct_change
    # drops the seed row), so 2016Q2/2016Q3 are too thin and get skipped.
    floor = min_train_observations(len(two_real_fund_request.funds))
    first_fold = next(f for f in schedule if len(returns.loc[:f.train_end]) >= floor)
    train_returns = returns.loc[:first_fold.train_end]
    test_returns = returns.loc[first_fold.test_start:first_fold.test_end]
    mu, sigma = inputs.build_mu_sigma(two_real_fund_request, train_returns)
    weights = solvers.solve_for_goal(two_real_fund_request, mu, sigma, train_returns)
    proj_ids = [f.proj_id for f in two_real_fund_request.funds]
    aligned = np.array([weights.get(pid, 0.0) / 100 for pid in proj_ids])
    period_returns = (test_returns[proj_ids] @ aligned).dropna()
    expected_vol = round(metrics.annualized_volatility(period_returns, 12) * 100, 2)

    assert folds[0]["periodLabel"] == first_fold.period_label
    assert folds[0]["realizedVolatilityPct"] == pytest.approx(expected_vol, abs=0.01)

    # realizedReturnPct is the fold's OWN test-period compounded return, not
    # annualized. A quarterly fold on monthly data is a quarter long, so the
    # annualized figure is (1+r)^4-1 and must NOT be what is reported.
    expected_period_return = round((float(np.prod(1.0 + period_returns.to_numpy(dtype=float))) - 1.0) * 100, 2)
    annualized = round(metrics.annualized_return(period_returns, 12) * 100, 2)
    assert folds[0]["realizedReturnPct"] == pytest.approx(expected_period_return, abs=0.01)
    assert folds[0]["realizedReturnPct"] != pytest.approx(annualized, abs=0.01)


def test_a_single_observation_test_window_is_skipped_not_scored_with_zeros(two_real_fund_request):
    """Monthly data at a monthly cadence gives each fold a test window of
    exactly one observation, on which volatility and Sharpe are undefined.
    Those folds must be skipped, not reported as 0.0 -- the fabricated
    constant the final review caught (41/41 folds at 0.00/0.00)."""
    from backend.app.domain.optimize_schemas import OptimizationFrequency

    two_real_fund_request.constraints.optimization_frequency = OptimizationFrequency.monthly
    returns = _load_returns(two_real_fund_request)
    folds, note = run_rolling_evaluation(two_real_fund_request, returns)

    assert folds == []
    assert note is not None
    assert "skipped during scoring" in note


def test_insufficient_rolling_history_raises(two_real_fund_request):
    two_real_fund_request.time_period.start_date = "2019-10-31"
    two_real_fund_request.time_period.end_date = "2019-12-31"
    returns = _load_returns(two_real_fund_request)
    with pytest.raises(ValueError, match="INSUFFICIENT_ROLLING_HISTORY"):
        run_rolling_evaluation(two_real_fund_request, returns)


def test_a_thin_early_fold_is_skipped_not_fatal(two_real_fund_request, monkeypatch):
    returns = _load_returns(two_real_fund_request)

    from backend.app.optimizer import solvers as solvers_module

    original = solvers_module.solve_for_goal
    call_count = {"n": 0}

    def flaky_solve(request, mu, sigma, train_returns):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("SOLVER_NON_CONVERGENCE")
        return original(request, mu, sigma, train_returns)

    monkeypatch.setattr(solvers_module, "solve_for_goal", flaky_solve)
    folds, note = run_rolling_evaluation(two_real_fund_request, returns)
    assert note is not None
    assert len(folds) >= 1
    # The note must report the real per-cause counts, not one hardcoded
    # attribution: exactly one fold failed during scoring (the monkeypatched
    # solve), and this fixture's first two scheduled folds are dropped by the
    # training-window floor before any solve is attempted.
    assert "1 skipped during scoring" in note
    assert "2 folds dropped for insufficient training history" in note
    assert f"{len(folds)} of 15 scheduled folds" in note
