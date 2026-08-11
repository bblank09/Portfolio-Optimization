import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.robust import resample_and_solve


@pytest.fixture
def two_real_fund_request():
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
        "robustOptimization": True, "useHistoricalReturns": True,
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


def test_resample_and_solve_against_real_cache_measures_real_time(two_real_fund_request):
    # This is the plan's explicit performance-measurement requirement: log
    # real wall-clock time for 500 resamples against the real committed NAV
    # cache, on a real 2-fund request. Not an automated pass/fail threshold
    # (the design spec deliberately leaves that as an open question to
    # raise back to the user if it proves unreasonable) -- but the timing
    # MUST be printed/logged so a human reviewing this task's report can
    # see the real number, not guess at it.
    import time

    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    returns = build_returns_panel(two_real_fund_request)
    mu, sigma = build_mu_sigma(two_real_fund_request, returns)

    started = time.monotonic()
    weights, note = resample_and_solve(two_real_fund_request, mu, sigma, returns)
    elapsed = time.monotonic() - started
    print(f"\nresample_and_solve: 500 resamples on a 2-fund request took {elapsed:.2f}s wall-clock")

    assert sum(weights.values()) == pytest.approx(100, abs=1.0)
    assert note is not None
    assert "resample" in note.lower()


def test_resample_and_solve_falls_back_when_most_resamples_fail(two_real_fund_request, monkeypatch):
    # Force every resample's solve to fail, so the function must fall back
    # to a single-shot solve on the ORIGINAL mu/sigma rather than raising or
    # returning garbage.
    import backend.app.optimizer.robust as robust_module
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    returns = build_returns_panel(two_real_fund_request)
    mu, sigma = build_mu_sigma(two_real_fund_request, returns)

    call_count = {"n": 0}
    original_solve = robust_module.solvers.solve_for_goal

    def flaky_solve(request, resample_mu, resample_sigma, resample_returns):
        call_count["n"] += 1
        if call_count["n"] <= 500:
            # Fail every resample's solve; the 501st call (if it happens)
            # is the single-shot fallback on the original data.
            raise RuntimeError("SOLVER_NON_CONVERGENCE")
        return original_solve(request, resample_mu, resample_sigma, resample_returns)

    monkeypatch.setattr(robust_module.solvers, "solve_for_goal", flaky_solve)
    weights, note = resample_and_solve(two_real_fund_request, mu, sigma, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=1.0)
    assert note is not None
    assert "fell back" in note.lower() or "fallback" in note.lower()


def test_resample_and_solve_averages_weights_on_a_synthetic_case(monkeypatch):
    # A minimal synthetic case where every resample's solve is monkeypatched
    # to return one of two known fixed weight sets alternately -- the
    # averaged result must be the arithmetic mean of the two, proving the
    # averaging logic itself (not the solver) is correct.
    import backend.app.optimizer.robust as robust_module

    request = OptimizeRequest.model_validate({
        "funds": [
            {"projId": "A", "displayName": "Fund A"},
            {"projId": "B", "displayName": "Fund B"},
        ],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2021-12-31"},
        "dataFrequency": "monthly", "goal": "max_sharpe", "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": True, "useHistoricalReturns": True,
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
    dates = pd.date_range("2020-01-31", periods=24, freq="ME")
    returns = pd.DataFrame({"A": [0.01, -0.005] * 12, "B": [0.008, 0.012] * 12}, index=dates)
    pct = returns * 100
    mu = pct.mean() * 12
    sigma = pct.cov() * 12

    call_count = {"n": 0}

    def alternating_solve(req, resample_mu, resample_sigma, resample_returns):
        call_count["n"] += 1
        if call_count["n"] % 2 == 0:
            return {"A": 60.0, "B": 40.0}
        return {"A": 40.0, "B": 60.0}

    monkeypatch.setattr(robust_module.solvers, "solve_for_goal", alternating_solve)
    weights, _note = resample_and_solve(request, mu, sigma, returns)
    assert weights["A"] == pytest.approx(50.0, abs=0.1)
    assert weights["B"] == pytest.approx(50.0, abs=0.1)


def test_resample_and_solve_is_deterministic_across_calls(two_real_fund_request):
    """Reproducibility invariant: the same request must produce byte-identical
    resampled weights on every call (robust.py now seeds its RNG)."""
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    returns = build_returns_panel(two_real_fund_request)
    mu, sigma = build_mu_sigma(two_real_fund_request, returns)

    first_weights, first_note = resample_and_solve(two_real_fund_request, mu, sigma, returns)
    second_weights, second_note = resample_and_solve(two_real_fund_request, mu, sigma, returns)

    assert first_weights == second_weights
    assert first_note == second_note


def test_resample_and_solve_weights_sum_to_exactly_100(two_real_fund_request):
    from backend.app.optimizer.inputs import build_mu_sigma, build_returns_panel

    returns = build_returns_panel(two_real_fund_request)
    mu, sigma = build_mu_sigma(two_real_fund_request, returns)
    weights, _note = resample_and_solve(two_real_fund_request, mu, sigma, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=1e-9)
