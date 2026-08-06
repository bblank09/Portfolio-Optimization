import numpy as np
import pandas as pd
from scipy.optimize import brentq


def simple_returns(nav: pd.DataFrame | pd.Series, drop: str = "any") -> pd.DataFrame | pd.Series:
    returns = nav.pct_change(fill_method=None)
    if drop == "any":
        return returns.dropna(how="any") if isinstance(returns, pd.DataFrame) else returns.dropna()
    if drop == "all":
        return returns.dropna(how="all") if isinstance(returns, pd.DataFrame) else returns.dropna()
    return returns


def cumulative_returns(period_returns: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    return (1 + period_returns).cumprod() - 1


def wealth_index(period_returns: pd.Series, initial_value: float = 1.0) -> pd.Series:
    return initial_value * (1 + period_returns).cumprod()


def time_weighted_return(period_returns: pd.Series) -> float:
    clean = period_returns.dropna()
    if clean.empty:
        return 0.0
    clean_values = clean.to_numpy(dtype=float)
    return float(np.prod(1.0 + clean_values) - 1.0)


def money_weighted_return(cashflows: list[tuple[float, float]]) -> float | None:
    def npv(rate: float) -> float:
        return sum(amount / ((1 + rate) ** period) for period, amount in cashflows)

    try:
        return float(brentq(npv, -0.999999, 10.0))
    except ValueError:
        return None
