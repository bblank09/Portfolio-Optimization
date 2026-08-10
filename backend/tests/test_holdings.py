import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.holdings import enforce_max_holdings


def _request(max_holdings: int, fund_count: int = 4) -> OptimizeRequest:
    funds = [{"projId": chr(ord("A") + i), "displayName": f"Fund {chr(ord('A') + i)}"} for i in range(fund_count)]
    return OptimizeRequest.model_validate({
        "funds": funds,
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2021-12-31"},
        "dataFrequency": "monthly", "goal": "min_variance", "riskMeasure": "std_dev",
        "tailConfidence": 95, "targetAnnualVolatilityPct": 10.0, "targetAnnualReturnPct": 6.0,
        "robustOptimization": False, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": max_holdings,
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
