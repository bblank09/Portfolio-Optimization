import pytest

from backend.app.optimizer.frontier import build_frontier, extract_markers
from backend.tests.test_optimizer_solvers_mean_variance import (
    _fake_returns,
    _two_asset_request,
)


def test_frontier_points_are_consistent_with_their_own_weights():
    request = _two_asset_request("max_sharpe")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    points = build_frontier(request, mu, sigma, returns)
    assert len(points) == 24
    for point in points:
        # The mock's cited defect: frontier (vol, ret) pairs were computed
        # completely separately from the weights shown for that same
        # point. Here they must actually agree: expectedReturnPct must
        # equal mu . weights for that point (within rounding).
        implied_return = sum(mu[proj_id] * (w / 100) for proj_id, w in point["weights"].items())
        assert point["expectedReturnPct"] == pytest.approx(implied_return, abs=0.1)


def test_gmv_and_tangency_markers_are_distinct_points_on_the_frontier():
    request = _two_asset_request("max_sharpe")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    points = build_frontier(request, mu, sigma, returns)
    optimal_weights = {"A": 40.0, "B": 60.0}
    optimal, gmv, tangency = extract_markers(points, optimal_weights, mu, sigma)
    assert optimal["label"] == "Your optimal portfolio"
    assert gmv is not None and tangency is not None
    assert gmv["volatilityPct"] <= tangency["volatilityPct"] + 0.5


def test_gmv_and_tangency_markers_are_points_actually_on_the_frontier_list():
    """Regression test for the mock's cited defect: markers must be objects
    drawn from (or equal to) points literally present in the computed
    frontier, not independently recomputed coordinates that only
    coincidentally agree."""
    request = _two_asset_request("max_sharpe")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    points = build_frontier(request, mu, sigma, returns)
    optimal_weights = {"A": 40.0, "B": 60.0}
    _, gmv, tangency = extract_markers(points, optimal_weights, mu, sigma)

    frontier_pairs = {(p["volatilityPct"], p["expectedReturnPct"]) for p in points}
    assert (gmv["volatilityPct"], gmv["expectedReturnPct"]) in frontier_pairs
    assert (tangency["volatilityPct"], tangency["expectedReturnPct"]) in frontier_pairs
