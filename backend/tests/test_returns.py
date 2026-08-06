import pandas as pd

from backend.app.engine.returns import (
    cumulative_returns,
    money_weighted_return,
    simple_returns,
    time_weighted_return,
)


def test_simple_returns_from_nav():
    nav = pd.DataFrame({"FUND_A": [10.0, 11.0, 9.9]})
    returns = simple_returns(nav)
    assert round(float(returns.iloc[0]["FUND_A"]), 6) == 0.10
    assert round(float(returns.iloc[1]["FUND_A"]), 6) == -0.10


def test_twrr_links_returns():
    assert round(time_weighted_return(pd.Series([0.10, -0.10])), 6) == -0.01


def test_cumulative_returns_links_returns():
    cumulative = cumulative_returns(pd.Series([0.10, -0.10]))
    assert round(float(cumulative.iloc[-1]), 6) == -0.01


def test_money_weighted_return_solves_irr():
    irr = money_weighted_return([(0.0, -1000.0), (1.0, 1100.0)])
    assert irr is not None
    assert round(irr, 6) == 0.10
