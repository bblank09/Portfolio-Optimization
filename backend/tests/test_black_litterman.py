import pandas as pd

from backend.app.domain.optimize_schemas import BlackLittermanInputs, BlackLittermanView
from backend.app.optimizer.black_litterman import (
    blend_posterior,
    compute_equilibrium_returns,
)
from backend.tests.test_optimizer_solvers_mean_variance import (
    _fake_returns,
    _two_asset_request,
)


def test_equilibrium_returns_are_proportional_to_market_cap_weighted_risk():
    sigma = pd.DataFrame({"A": [4.0, 1.0], "B": [1.0, 1.0]}, index=["A", "B"])
    equilibrium = compute_equilibrium_returns(sigma, risk_aversion=2.5, market_weights=pd.Series({"A": 0.5, "B": 0.5}))
    # Pi = delta * Sigma @ w_mkt -- A has higher variance and covariance
    # with B, so its equilibrium return must come out higher than B's.
    assert equilibrium["A"] > equilibrium["B"]


def test_relative_view_moves_both_named_assets():
    # _two_asset_request's helper builds via OptimizeRequest.model_validate,
    # and OptimizeRequest's own model_validator rejects goal="black_litterman"
    # with blackLitterman=None at construction time -- so we can't pass
    # "black_litterman" as the initial goal here (Task 3's validator, out of
    # this task's scope, would raise before this test body ever runs).
    # Construct with a goal that passes validation, then set both fields by
    # attribute assignment afterward (OptimizeRequest has no
    # validate_assignment, so this is safe and matches what service.py does
    # once it has parsed a request that already carries black_litterman).
    request = _two_asset_request("min_variance")
    request.goal = "black_litterman"
    request.black_litterman = BlackLittermanInputs(
        riskAversion=2.5, tau=0.05, benchmarkExpectedReturnPct=7,
        views=[BlackLittermanView(
            key="v1", assetProjId1="A", viewType="relative", assetProjId2="B",
            adjustedPerformancePct=5.0, confidence=100,
        )],
    )
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    equilibrium, posterior = blend_posterior(request, mu, sigma)
    # The mock's known defect: a relative view only touched asset 1.
    # A 100%-confidence view that A beats B by 5% must move BOTH A up
    # and B down relative to their own equilibrium values.
    assert posterior["A"] > equilibrium["A"]
    assert posterior["B"] < equilibrium["B"]
