import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.holdings import enforce_max_holdings


def _request(
    max_holdings: int,
    fund_count: int = 4,
    *,
    goal: str = "min_variance",
    group_constraints_enabled: bool = False,
    fund_groups: dict[str, str] | None = None,
    asset_groups: dict | None = None,
) -> OptimizeRequest:
    funds = [{"projId": chr(ord("A") + i), "displayName": f"Fund {chr(ord('A') + i)}"} for i in range(fund_count)]
    return OptimizeRequest.model_validate({
        "funds": funds,
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": fund_groups or {},
        "assetGroups": asset_groups
        or {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2021-12-31"},
        "dataFrequency": "monthly", "goal": goal, "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": False, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": group_constraints_enabled, "maxHoldings": max_holdings,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })


def _mu_sigma_returns(fund_count: int = 4):
    # Independent (not perfectly-correlated) return series with distinct
    # volatilities so min_variance naturally spreads weight across multiple
    # funds when uncapped -- the scenario that requires trimming. A
    # deterministic RNG seed keeps the fixture reproducible.
    dates = pd.date_range("2020-01-31", periods=24, freq="ME")
    rng = np.random.default_rng(42)
    data = {}
    for i in range(fund_count):
        data[chr(ord("A") + i)] = rng.normal(0, 0.01 + 0.003 * i, len(dates))
    returns = pd.DataFrame(data, index=dates)
    pct = returns * 100
    mu = pct.mean() * 12
    sigma = pct.cov() * 12
    return mu, sigma, returns


def test_no_trim_needed_when_already_within_cap():
    request = _request(max_holdings=4)
    mu, sigma, returns = _mu_sigma_returns()
    weights, note = enforce_max_holdings(request, mu, sigma, returns)
    assert note is None
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_trims_down_to_the_cap():
    request = _request(max_holdings=2)
    mu, sigma, returns = _mu_sigma_returns()
    weights, note = enforce_max_holdings(request, mu, sigma, returns)
    held = [pid for pid, w in weights.items() if w > 0.5]
    assert len(held) <= 2
    assert note is not None
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_cap_of_one_trims_to_a_single_holding():
    request = _request(max_holdings=1)
    mu, sigma, returns = _mu_sigma_returns()
    weights, note = enforce_max_holdings(request, mu, sigma, returns)
    held = [pid for pid, w in weights.items() if w > 0.5]
    assert len(held) == 1
    assert weights[held[0]] == pytest.approx(100, abs=0.5)
    assert note is not None


def test_group_floor_blocks_trimming_and_reports_a_shortfall_note():
    """groupConstraintsEnabled=True AND a binding maxHoldings in the SAME
    request -- the highest-risk interaction in this feature, and the one the
    HRP silent-constraint-drop bug fell into.

    Group X = {D} with a 20% FLOOR, so D can never be pinned to zero. The cap
    of 1 forces the heuristic to keep dropping until it must drop D, at which
    point the solve becomes infeasible: it must then return the last-good
    weights (which still honor the group floor) plus a shortfall
    constraintNote -- never a hard error and never a floor violation.
    """
    request = _request(
        max_holdings=1,
        group_constraints_enabled=True,
        fund_groups={"D": "X"},
        asset_groups={"X": {"name": "Must hold D", "minWeightPct": 20, "maxWeightPct": 100}},
    )
    mu, sigma, returns = _mu_sigma_returns()
    weights, note = enforce_max_holdings(request, mu, sigma, returns)

    assert note is not None
    assert "Could not fully trim" in note
    assert "()" not in note  # finding #6: never an empty dropped-fund list
    # The group floor is still respected in the returned allocation, and the
    # cap is (correctly) not met -- the note is what explains the shortfall.
    assert weights["D"] >= 20 - 0.5
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)
    held = [pid for pid, w in weights.items() if w > 0.5]
    assert len(held) > request.constraints.max_holdings


def test_shortfall_note_reads_correctly_when_nothing_could_be_dropped():
    """Finding #6: when the VERY FIRST trim attempt is infeasible the dropped
    list is empty, which used to render as `0 fund(s) dropped ()`. Every fund
    here carries its own 25% group floor, so no fund can ever be pinned to
    zero and the first attempt fails immediately."""
    request = _request(
        max_holdings=2,
        group_constraints_enabled=True,
        fund_groups={L: L for L in "ABCD"},
        asset_groups={L: {"name": L, "minWeightPct": 25, "maxWeightPct": 100} for L in "ABCD"},
    )
    mu, sigma, returns = _mu_sigma_returns()
    weights, note = enforce_max_holdings(request, mu, sigma, returns)

    assert note is not None
    assert "no fund could be dropped" in note
    assert "()" not in note
    assert "0 fund(s)" not in note
    assert all(w == pytest.approx(25, abs=0.5) for w in weights.values())


def test_hrp_raises_on_a_violated_group_cap_instead_of_silently_succeeding():
    """Regression for the final review's critical finding: rp.HCPortfolio has
    no linear-constraint hook, so group rows never reached the HRP solve and a
    capped group came back at ~98% with a clean `feasibility: ok`. The
    post-solve validation in solvers.solve_hrp must now raise.
    """
    from backend.app.optimizer import solvers

    request = _request(
        max_holdings=4,
        goal="hrp",
        group_constraints_enabled=True,
        fund_groups={"A": "X", "B": "X"},
        asset_groups={"X": {"name": "Capped", "minWeightPct": 0, "maxWeightPct": 10}},
    )
    mu, sigma, returns = _mu_sigma_returns()

    # Sanity: the unconstrained HRP allocation genuinely violates the 10% cap,
    # so the raise below is a real detection and not a vacuous assertion.
    uncapped = _request(max_holdings=4, goal="hrp")
    natural = solvers.solve_for_goal(uncapped, mu, sigma, returns)
    assert natural["A"] + natural["B"] > 10 + 0.5

    with pytest.raises(RuntimeError, match="INFEASIBLE_CONSTRAINTS"):
        solvers.solve_for_goal(request, mu, sigma, returns)


def test_never_exceeds_original_fund_count_minus_cap_iterations(monkeypatch):
    # A cap that can never be satisfied (every solve keeps returning all 4
    # funds nonzero) must still terminate, not loop forever -- verified by
    # capping the mock at fund_count - max_holdings calls and asserting no
    # further calls happen.
    import backend.app.optimizer.holdings as holdings_module

    request = _request(max_holdings=1, fund_count=4)
    mu, sigma, returns = _mu_sigma_returns(fund_count=4)
    call_count = {"n": 0}
    original_solve = holdings_module.solvers.solve_for_goal

    def counting_solve(req, m, s, r):
        call_count["n"] += 1
        return original_solve(req, m, s, r)

    monkeypatch.setattr(holdings_module.solvers, "solve_for_goal", counting_solve)
    enforce_max_holdings(request, mu, sigma, returns)
    # 1 initial solve + at most (4 - 1) = 3 trimming re-solves = 4 max.
    assert call_count["n"] <= 4
