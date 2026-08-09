import pytest

from backend.app.optimizer.solvers import solve_hrp, solve_risk_parity
from backend.tests.test_optimizer_solvers_mean_variance import (
    _fake_returns,
    _two_asset_request,
)


def test_risk_parity_weights_sum_to_100():
    request = _two_asset_request("risk_parity")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    weights = solve_risk_parity(request, mu, sigma, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_risk_parity_gives_more_weight_to_lower_risk_asset():
    request = _two_asset_request("risk_parity")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    weights = solve_risk_parity(request, mu, sigma, returns)
    assert weights["B"] > weights["A"]


def test_hrp_weights_sum_to_100():
    request = _two_asset_request("hrp")
    returns = _fake_returns()
    weights = solve_hrp(request, returns)
    assert sum(weights.values()) == pytest.approx(100, abs=0.5)


def test_risk_parity_and_hrp_differ_from_each_other():
    # The mock's most-cited defect: risk_parity/hrp/min_variance all used
    # the exact same inverse-volatility heuristic. They must be genuinely
    # different algorithms now.
    request_rp = _two_asset_request("risk_parity")
    request_hrp = _two_asset_request("hrp")
    returns = _fake_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    rp_weights = solve_risk_parity(request_rp, mu, sigma, returns)
    hrp_weights = solve_hrp(request_hrp, returns)
    assert rp_weights != pytest.approx(hrp_weights, abs=1e-9)
