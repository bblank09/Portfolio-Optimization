import pytest

from backend.app.domain.optimize_schemas import (
    CompareAgainst,
    ObjectiveGoal,
    OptimizeRequest,
)
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


def test_too_short_a_window_still_returns_the_main_solve_without_rolling(two_real_fund_request):
    """A rolling-evaluation failure must never block the primary result.

    This window is too short for two folds, so run_rolling_evaluation raises
    INSUFFICIENT_ROLLING_HISTORY. Before the fix that propagated out of
    service.run_optimize and turned the whole /api/optimize request into a
    422 -- losing weights the main solve had already produced fine.
    """
    two_real_fund_request.time_period.start_date = "2019-10-31"
    two_real_fund_request.time_period.end_date = "2019-12-31"

    result = run_optimize(two_real_fund_request)

    assert result.feasibility == "ok"
    assert set(result.optimal_weights) == {"M0209_2548", "M0155_2547"}
    assert sum(result.optimal_weights.values()) == pytest.approx(100, abs=0.5)
    assert result.rolling == []
    assert result.robust_note is not None
    assert "Rolling validation unavailable" in result.robust_note


def test_run_optimize_populates_real_compare_weights(two_real_fund_request):
    two_real_fund_request.constraints = two_real_fund_request.constraints.model_copy(
        update={"compare_against": CompareAgainst.equal_weighted}
    )
    result = run_optimize(two_real_fund_request)
    assert result.compare_weights is not None
    assert sum(result.compare_weights.values()) == pytest.approx(100, abs=0.5)
    assert result.compare_note is None
    assert result.selected_risk_measure.compared_value is not None
    assert {column.label for column in result.performance_summary} == {"Optimized", "Equal weighted"}


def test_run_optimize_populates_real_benchmark_comparison(two_real_fund_request):
    two_real_fund_request.benchmark_proj_id = "M0209_2548"
    result = run_optimize(two_real_fund_request)
    assert result.benchmark_comparison is not None
    assert result.benchmark_comparison.proj_id == "M0209_2548"


def test_run_optimize_propagates_benchmark_data_unavailable(two_real_fund_request):
    two_real_fund_request.benchmark_proj_id = "NONEXISTENT_PROJ_ID"
    with pytest.raises(ValueError, match="BENCHMARK_DATA_UNAVAILABLE"):
        run_optimize(two_real_fund_request)


def test_run_optimize_enforces_max_holdings(two_real_fund_request):
    # The fixture's 2-fund universe already satisfies any cap >= 2, so this
    # confirms the no-op path returns cleanly with constraint_note None.
    result = run_optimize(two_real_fund_request)
    assert result.constraint_note is None

    # A cap of 1 on a 2-fund universe MUST trigger real trimming.
    #
    # Deviation from the brief's sample test: the brief's version only
    # overrode `max_holdings` and kept the fixture's default goal
    # (max_sharpe). Verified against the real committed NAV cache for this
    # exact fund pair/window, max_sharpe on 2 highly-correlated funds
    # (corr ~0.94) already concentrates ~100% into the higher-Sharpe fund on
    # its own, before any cap is applied -- so a max_holdings=1 cap would be
    # a no-op there and never exercise the trimming path at all. Switching
    # the goal to risk_parity (also verified against the real cache) yields
    # an unconstrained solve that holds both funds meaningfully, so the
    # max_holdings=1 cap genuinely forces holdings.enforce_max_holdings to
    # trim -- this is the scenario the brief's assertions describe.
    tight = two_real_fund_request.model_copy(
        update={
            "goal": ObjectiveGoal.risk_parity,
            "constraints": two_real_fund_request.constraints.model_copy(update={"max_holdings": 1}),
        }
    )
    result = run_optimize(tight)
    held = [pid for pid, w in result.optimal_weights.items() if w > 0.5]
    assert len(held) == 1
    assert result.constraint_note is not None


def test_run_optimize_applies_robust_optimization_when_enabled(two_real_fund_request):
    robust_request = two_real_fund_request.model_copy(update={"robust_optimization": True})
    result = run_optimize(robust_request)
    assert result.robust_optimization_note is not None
    assert sum(result.optimal_weights.values()) == pytest.approx(100, abs=0.5)


def test_run_optimize_leaves_robust_optimization_note_none_when_disabled(two_real_fund_request):
    result = run_optimize(two_real_fund_request)
    assert result.robust_optimization_note is None


def test_robust_note_discloses_post_trim_resolve_when_max_holdings_binds(two_real_fund_request):
    """Regression guard for the final-review finding: when maxHoldings binds,
    holdings.enforce_max_holdings discards the resampled average and returns a
    plain single-shot solve, so the robust note must not keep claiming the
    allocation is the resampled average. Asserting on the note's TEXT, not
    merely `is not None` -- the weak assertion is why this slipped through.
    """
    tight = two_real_fund_request.model_copy(
        update={
            "robust_optimization": True,
            "goal": ObjectiveGoal.risk_parity,
            "constraints": two_real_fund_request.constraints.model_copy(update={"max_holdings": 1}),
        }
    )
    result = run_optimize(tight)

    held = [pid for pid, w in result.optimal_weights.items() if w > 0.5]
    assert len(held) == 1
    assert result.constraint_note is not None
    assert result.robust_optimization_note is not None
    # The original resampling statement is preserved...
    assert "resample" in result.robust_optimization_note.lower()
    # ...and the disclosure that the shown allocation is NOT that average.
    assert "single-shot solve, not the resampled average" in result.robust_optimization_note
    assert "max-holdings cap" in result.robust_optimization_note


def test_robust_note_unchanged_when_max_holdings_does_not_bind(two_real_fund_request):
    result = run_optimize(two_real_fund_request.model_copy(update={"robust_optimization": True}))
    assert result.constraint_note is None
    assert result.robust_optimization_note is not None
    assert "single-shot solve, not the resampled average" not in result.robust_optimization_note


def test_trailing_rolling_window_with_robust_optimization_against_real_cache(two_real_fund_request):
    """The design spec's smoke-matrix extension named BOTH robust_optimization
    and rolling_window_mode="trailing"; only the robust variant existed. One
    bounded cross-feature case (not a new parametrization dimension, matching
    how the robust smoke test is already scoped)."""
    request = two_real_fund_request.model_copy(
        update={
            "robust_optimization": True,
            "constraints": two_real_fund_request.constraints.model_copy(
                update={"rolling_window_mode": "trailing", "lookback_period_months": 12}
            ),
        }
    )
    result = run_optimize(request)

    assert sum(result.optimal_weights.values()) == pytest.approx(100, abs=0.5)
    assert result.robust_optimization_note is not None
    assert len(result.rolling) >= 1
    # Cheap non-degenerate check: the trailing folds are not all the same fold.
    if len(result.rolling) > 1:
        assert len({f.realized_return_pct for f in result.rolling}) > 1
