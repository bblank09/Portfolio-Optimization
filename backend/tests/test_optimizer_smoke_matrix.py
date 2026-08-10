"""End-to-end smoke coverage for every objective x risk-measure combination.

The final whole-branch review found two goals that raised on EVERY request --
``black_litterman`` (bare ``KeyError`` from ``solvers._OBJ_CODES``) and
``max_return_target_vol`` (``NameError: The limits of the frontier can't be
found``, because the frontier sweep inherited the goal's ``upperdev``
ceiling). Neither had any test exercising it end-to-end, so both reached the
merge checkpoint as guaranteed HTTP 500s.

This file closes that hole: 7 goals x 4 risk measures = 28 combinations, all
driven through ``service.run_optimize``. It deliberately does NOT deep-check
every response field -- its job is to prove each combination is reachable
without crashing and returns a structurally valid ``OptimizeResult``.

The returns panel is synthetic and injected via monkeypatch rather than read
from the committed NAV cache, for two reasons: the run stays offline and
deterministic, and the three assets can be given genuinely different
means/volatilities with low cross-correlation so the frontier does not
collapse to the degenerate single point that the real two-SET50-tracker
fixture in test_optimizer_service.py produces.
"""

import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import (
    ObjectiveGoal,
    OptimizeRequest,
    OptimizeResult,
    RiskMeasure,
)
from backend.app.optimizer import inputs, service

PROJ_IDS = ["A", "B", "C"]


def _synthetic_returns() -> pd.DataFrame:
    """96 months of independent monthly returns with clearly separated
    risk/return profiles, so no asset dominates another on both axes and the
    efficient frontier is a real curve rather than a single point."""
    rng = np.random.default_rng(20260808)
    dates = pd.date_range("2016-01-31", periods=96, freq="ME")
    return pd.DataFrame(
        {
            "A": rng.normal(0.010, 0.055, size=96),  # high return, high vol
            "B": rng.normal(0.006, 0.025, size=96),  # mid / mid
            "C": rng.normal(0.003, 0.010, size=96),  # low return, low vol
        },
        index=dates,
    )


def _assert_rolling_is_not_degenerate(result: OptimizeResult) -> None:
    """Rolling must either produce real folds or explain why not.

    The `>= 1 fold or a note` form this replaces was satisfied by 41 folds of
    identical fabricated `0.00 / 0.00` stats, which is how the monthly-cadence
    defect reached the merge checkpoint. Asserting the fold stats are not all
    the same tuple catches that whole "silently constant across every fold"
    class, not just the one bug.
    """
    assert len(result.rolling) >= 1 or result.robust_note is not None
    if len(result.rolling) >= 2:
        stats = {
            (f.realized_return_pct, f.realized_volatility_pct, f.realized_sharpe)
            for f in result.rolling
        }
        assert len(stats) > 1, f"every rolling fold reported the identical stats {stats}"


COMPARE_AGAINSTS = ["equal_weighted", "max_sharpe", "risk_parity", "inverse_volatility"]


def _request(
    goal: str,
    risk_measure: str,
    optimization_frequency: str = "quarterly",
    compare_against: str = "equal_weighted",
) -> OptimizeRequest:
    payload = {
        "funds": [{"projId": p, "displayName": f"Fund {p}"} for p in PROJ_IDS],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2016-01-31", "endDate": "2023-12-31"},
        "dataFrequency": "monthly",
        "goal": goal,
        "riskMeasure": risk_measure,
        "tailConfidence": 95,
        "targetAnnualVolatilityPct": 12.0,
        "targetAnnualReturnPct": 5.0,
        "robustOptimization": False,
        "useHistoricalReturns": True, "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample",
        "blackLitterman": None, "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            # 2, not the fund count -- a cap of 20 on a 3-fund universe can
            # never bind, which made the held_count assertion below a
            # universal no-op across all 112 parametrized cases (the final
            # review's finding). At 2, diversifying goals (risk_parity, hrp,
            # min_variance) genuinely have to trim from 3 down to 2, while
            # naturally-concentrated ones may already satisfy it -- both are
            # fine, the point is the assertion is now a real check.
            "groupConstraintsEnabled": False, "maxHoldings": 2,
            "lookbackPeriodMonths": 12, "optimizationFrequency": optimization_frequency,
            "riskFreeRatePct": 1.5, "compareAgainst": compare_against,
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    }
    if goal == "black_litterman":
        payload["blackLitterman"] = {
            "riskAversion": 2.5,
            "tau": 0.05,
            "benchmarkExpectedReturnPct": 7.0,
            "views": [{
                "key": "v1", "assetProjId1": "A", "viewType": "absolute",
                "assetProjId2": None, "adjustedPerformancePct": 11.0, "confidence": 60,
            }],
        }
    return OptimizeRequest.model_validate(payload)


@pytest.fixture
def synthetic_panel(monkeypatch):
    returns = _synthetic_returns()
    monkeypatch.setattr(inputs, "build_returns_panel", lambda request: returns)
    return returns


@pytest.mark.parametrize("compare_against", COMPARE_AGAINSTS)
@pytest.mark.parametrize("goal", [g.value for g in ObjectiveGoal])
@pytest.mark.parametrize("risk_measure", [m.value for m in RiskMeasure])
def test_every_goal_and_risk_measure_combination_is_reachable(
    goal, risk_measure, compare_against, synthetic_panel
):
    request = _request(goal, risk_measure, compare_against=compare_against)
    result = service.run_optimize(request)

    assert isinstance(result, OptimizeResult)
    assert set(result.optimal_weights) == set(PROJ_IDS)
    assert sum(result.optimal_weights.values()) == pytest.approx(100, abs=0.5)
    assert all(w >= -1e-6 for w in result.optimal_weights.values())
    # The reported risk measure must be the one that was requested, and it
    # must carry a real (finite, non-negative) value -- not a placeholder.
    assert result.selected_risk_measure.measure.value == risk_measure
    assert np.isfinite(result.selected_risk_measure.optimized_value)
    assert result.selected_risk_measure.optimized_value >= 0
    # Risk contribution is a real decomposition summing to 100, not 100/n.
    assert sum(result.risk_contribution_pct.values()) == pytest.approx(100, abs=0.5)
    assert result.frontier
    # Rolling evaluation must either produce real, varying folds or explain
    # why not (INSUFFICIENT_ROLLING_HISTORY is a separate, expected error
    # path exercised by test_rolling_evaluation.py directly, not here).
    _assert_rolling_is_not_degenerate(result)
    # A non-none compareAgainst must produce real compareWeights for every
    # goal/risk-measure combination -- not left blank the way an earlier
    # sub-project's smoke matrix let a real bug hide behind a too-weak
    # assertion (see the rolling-evaluator final review's finding).
    assert result.compare_weights is not None
    assert sum(result.compare_weights.values()) == pytest.approx(100, abs=0.5)
    assert set(result.compare_weights) == set(PROJ_IDS)
    # A same-goal comparison is legitimately identical; every other pairing
    # must differ, which is what catches a comparison silently computed on
    # the main solve's own (e.g. Black-Litterman-adjusted) inputs.
    # A corner solution (everything in one asset) is a place two different
    # objectives can legitimately land independently -- semi_variance sends
    # both black_litterman and max_sharpe to 100% A on this panel -- so it
    # cannot distinguish agreement from a leaked-input bug either way.
    is_corner = max(result.optimal_weights.values()) > 99.9
    if compare_against != goal and not is_corner:
        max_delta = max(
            abs(result.compare_weights[p] - result.optimal_weights[p]) for p in PROJ_IDS
        )
        assert max_delta > 0.01, "comparison portfolio is identical to the optimized portfolio"
    # Every combination must respect optimal_weights never exceeding
    # max_holdings, whether or not trimming was actually needed for this
    # specific fixture/cap combination.
    held_count = sum(1 for w in result.optimal_weights.values() if w > 0.5)
    assert held_count <= request.constraints.max_holdings
    # rollingWindowMode's default ("expanding") must not silently change --
    # cheap confirming check alongside Task 3's dedicated regression tests.
    assert request.constraints.rolling_window_mode.value == "expanding"


@pytest.mark.parametrize("optimization_frequency", ["monthly", "quarterly", "annually"])
def test_rolling_is_never_degenerate_at_any_optimization_frequency(
    optimization_frequency, synthetic_panel
):
    """The defect this guards against was cadence-specific: monthly data at a
    monthly cadence gave every fold a one-observation test window, which
    scored as a fabricated `0.00 / 0.00` on all 41 folds while the
    quarterly-only smoke coverage stayed green. Every supported cadence is
    now exercised, and each must yield either varying fold stats or no folds
    plus an explanatory note -- never a constant column of numbers.
    """
    result = service.run_optimize(_request("min_variance", "std_dev", optimization_frequency))

    _assert_rolling_is_not_degenerate(result)
    if optimization_frequency == "monthly":
        # One monthly observation per monthly test window: unscoreable, so
        # honestly reported as no folds rather than zeros.
        assert result.rolling == []
        assert result.robust_note is not None
    else:
        assert len(result.rolling) >= 2


def test_black_litterman_comparison_is_built_on_unadjusted_mu(synthetic_panel, monkeypatch):
    """The comparison must answer "how does my BL portfolio compare to a plain
    baseline on HISTORICAL expected returns", so it gets the ORIGINAL mu --
    never the BL posterior. Passing the posterior made a ``max_sharpe``
    comparison bit-identical to the BL solve (they share an objective code),
    which the weight-delta assertion above only catches on non-corner panels.
    This checks the wiring directly.
    """
    from backend.app.optimizer import comparison

    seen: dict[str, pd.Series] = {}
    real = comparison.build_comparison_weights

    def spy(request, mu, sigma, returns):
        seen["mu"] = mu.copy()
        return real(request, mu, sigma, returns)

    monkeypatch.setattr(comparison, "build_comparison_weights", spy)
    request = _request("black_litterman", "std_dev", compare_against="max_sharpe")
    result = service.run_optimize(request)

    historical_mu = inputs.build_mu_sigma(request, synthetic_panel)[0]
    pd.testing.assert_series_equal(seen["mu"], historical_mu)
    # And the BL posterior really did differ, so the check above is not vacuous.
    assert result.black_litterman is not None
    assert result.black_litterman.adjusted_return_pct != result.black_litterman.equilibrium_return_pct


@pytest.mark.parametrize("goal", ["max_sharpe", "min_variance", "risk_parity"])
def test_robust_optimization_smoke_across_a_few_goals(goal, synthetic_panel):
    """Proves robust optimization (500-resample Michaud averaging) doesn't
    crash or silently no-op for a SAMPLE of goals -- not every goal x risk
    measure combination, which would multiply this file's already-112-case
    runtime by up to 500x given robust optimization's real per-call cost.
    Correctness in depth is covered by test_robust.py and
    test_optimizer_service.py; this is only a reachability smoke check.
    """
    request = _request(goal, "std_dev")
    request = request.model_copy(update={"robust_optimization": True})
    result = service.run_optimize(request)

    assert sum(result.optimal_weights.values()) == pytest.approx(100, abs=0.5)
    assert result.robust_optimization_note is not None
