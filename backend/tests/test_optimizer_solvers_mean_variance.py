import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.solvers import solve_mean_variance


def _two_asset_request(goal: str, risk_measure: str = "std_dev") -> OptimizeRequest:
    return OptimizeRequest.model_validate({
        "funds": [{"projId": "A", "displayName": "A"}, {"projId": "B", "displayName": "B"}],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2020-12-31"},
        "dataFrequency": "monthly", "goal": goal, "riskMeasure": risk_measure,
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


def _fake_returns() -> pd.DataFrame:
    dates = pd.date_range("2020-01-31", periods=12, freq="ME")
    rng = np.random.default_rng(7)
    # A is deliberately higher-return/higher-vol, B lower/lower, uncorrelated
    return pd.DataFrame(
        {"A": rng.normal(0.02, 0.05, size=12), "B": rng.normal(0.005, 0.01, size=12)},
        index=dates,
    )


def test_gmv_weights_sum_to_100_and_are_long_only():
    request = _two_asset_request("min_variance")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    weights = solve_mean_variance(request, mu, sigma, returns)
    assert set(weights) == {"A", "B"}
    assert weights["A"] >= -1e-6 and weights["B"] >= -1e-6
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_gmv_favors_lower_volatility_asset():
    request = _two_asset_request("min_variance")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    weights = solve_mean_variance(request, mu, sigma, returns)
    # B has much lower variance in the fixture data, so GMV should lean
    # toward it -- this is the exact defect the mock never had a real
    # covariance matrix to get right.
    assert weights["B"] > weights["A"]


def test_max_sharpe_respects_fund_bounds():
    from backend.app.domain.optimize_schemas import FundBound

    request = _two_asset_request("max_sharpe")
    request.fund_bounds["A"] = FundBound(minWeightPct=0, maxWeightPct=20)
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    weights = solve_mean_variance(request, mu, sigma, returns)
    assert weights["A"] <= 20 + 0.5


def test_max_sharpe_all_negative_excess_returns_uses_frontier_tangency(monkeypatch):
    """Riskfolio's Sharpe fallback can return an interior point when every
    asset has a negative excess return. The optimizer must select the best
    feasible point from its own frontier instead of returning that fallback.
    """
    from backend.app.optimizer import solvers

    request = _two_asset_request("max_sharpe")
    mu = pd.Series({"A": -4.0, "B": -2.0})
    sigma = pd.DataFrame([[4.0, 0.0], [0.0, 25.0]], index=["A", "B"], columns=["A", "B"])
    returns = pd.DataFrame({"A": [-0.01, -0.02], "B": [-0.01, -0.02]})

    class FakePortfolio:
        rf = request.constraints.risk_free_rate_pct / 100

        def optimization(self, **_kwargs):
            return pd.DataFrame({"weights": [0.4, 0.6]}, index=["A", "B"])

        def efficient_frontier(self, **_kwargs):
            return pd.DataFrame(
                [[1.0, 0.5, 0.0], [0.0, 0.5, 1.0]],
                index=["A", "B"],
            )

    monkeypatch.setattr(solvers, "_build_portfolio", lambda *_args, **_kwargs: FakePortfolio())

    weights = solvers.solve_mean_variance(request, mu, sigma, returns)

    assert weights["A"] == pytest.approx(0.0)
    assert weights["B"] == pytest.approx(100.0)


def test_max_sharpe_all_negative_excess_returns_real_frontier_prefers_best_corner():
    """The real riskfolio frontier must make the same honest choice as the
    isolated fallback test above, not merely pass through the selection logic.
    """
    request = _two_asset_request("max_sharpe")
    mu = pd.Series({"A": -4.0, "B": -2.0})
    sigma = pd.DataFrame([[4.0, 0.0], [0.0, 25.0]], index=["A", "B"], columns=["A", "B"])
    returns = pd.DataFrame({"A": [-0.01, -0.02], "B": [-0.01, -0.02]})

    weights = solve_mean_variance(request, mu, sigma, returns)

    assert weights["A"] == pytest.approx(0.0, abs=0.1)
    assert weights["B"] == pytest.approx(100.0, abs=0.1)
