import pandas as pd

from backend.app.engine.metrics import (
    annualized_return,
    annualized_volatility,
    beta_alpha,
    correlation,
    information_ratio,
    max_drawdown,
    sharpe_ratio,
    tracking_error,
)


def test_max_drawdown():
    assert round(max_drawdown(pd.Series([100, 120, 90, 150])), 6) == -0.25


def test_annualized_return_from_monthly_returns():
    returns = pd.Series([0.01] * 12)
    assert round(annualized_return(returns, 12), 6) == round((1.01**12) - 1, 6)


def test_annualized_volatility_scales_by_periods():
    returns = pd.Series([0.01, -0.01, 0.02, -0.02])
    assert annualized_volatility(returns, 12) > 0


def test_sharpe_ratio_returns_none_for_zero_volatility():
    assert sharpe_ratio(pd.Series([0.01, 0.01, 0.01]), 0.0, 12) is None


def test_beta_alpha_returns_floats():
    beta, alpha = beta_alpha(pd.Series([0.02, 0.01, -0.01]), pd.Series([0.01, 0.02, -0.02]), 0.0, 12)
    assert isinstance(beta, float)
    assert isinstance(alpha, float)


def test_tracking_error_and_information_ratio():
    portfolio = pd.Series([0.02, 0.01, -0.01])
    benchmark = pd.Series([0.01, 0.02, -0.02])
    assert tracking_error(portfolio, benchmark, 12) > 0
    assert information_ratio(portfolio, benchmark, 12) is not None


def test_correlation():
    assert round(correlation(pd.Series([1, 2, 3]), pd.Series([1, 2, 3])), 6) == 1.0
