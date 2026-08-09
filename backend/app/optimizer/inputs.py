import pandas as pd

from backend.app.data.quality import align_nav_panel
from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.sec.cache import load_nav_panel

_PERIODS_PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12}


def build_returns_panel(request: OptimizeRequest) -> pd.DataFrame:
    """Load, align, and slice the NAV panel for the request's funds and
    time period, then convert to simple period returns. Raises ValueError
    (caught by the API route and turned into INSUFFICIENT_NAV_HISTORY) if
    any fund has no NAV observations in the requested window."""
    proj_ids = [fund.proj_id for fund in request.funds]
    nav = align_nav_panel(load_nav_panel(proj_ids), frequency=request.data_frequency.value)
    window = nav.loc[pd.Timestamp(request.time_period.start_date):pd.Timestamp(request.time_period.end_date), proj_ids]
    if window.isna().all().any():
        missing = window.columns[window.isna().all()].tolist()
        raise ValueError(f"No NAV observations in the requested window for: {missing}")
    returns = window.pct_change().dropna(how="all")
    return returns


def periods_per_year(request: OptimizeRequest) -> int:
    return _PERIODS_PER_YEAR[request.data_frequency.value]


def build_mu_sigma(request: OptimizeRequest, returns: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """mu: annualized expected return per fund, as a percentage (matching
    the mock's own convention and frontend/src/types/optimize.ts's
    `expectedReturnPct` fields). Sigma: annualized covariance matrix,
    also in percentage-squared units so mu/Sigma are unit-consistent for
    the solver."""
    ppy = periods_per_year(request)
    pct_returns = returns * 100

    if request.covariance_method.value == "ewma":
        halflife = max(returns.shape[0] // 4, 1)
        sigma_period = pct_returns.ewm(halflife=halflife).cov().groupby(level=1).last()
    elif request.covariance_method.value == "shrinkage":
        sample = pct_returns.cov()
        shrinkage_intensity = 0.2
        avg_var = pd.Series(sample.values.diagonal(), index=sample.index).mean()
        shrink_target = pd.DataFrame(0.0, index=sample.index, columns=sample.columns)
        for name in sample.index:
            shrink_target.loc[name, name] = avg_var
        sigma_period = shrinkage_intensity * shrink_target + (1 - shrinkage_intensity) * sample
    else:
        sigma_period = pct_returns.cov()

    sigma = sigma_period * ppy

    mu = pct_returns.mean() * ppy
    if not request.use_historical_returns:
        for proj_id, override in request.expected_return_overrides.items():
            if proj_id in mu.index:
                mu[proj_id] = override
    if not request.use_historical_volatility:
        vol = (pd.Series(sigma.values.diagonal(), index=sigma.index)) ** 0.5
        for proj_id, override in request.volatility_overrides.items():
            if proj_id in vol.index:
                vol[proj_id] = override
        corr = sigma.copy()
        for i in sigma.index:
            for j in sigma.columns:
                corr.loc[i, j] = sigma.loc[i, j] / ((sigma.loc[i, i] ** 0.5) * (sigma.loc[j, j] ** 0.5)) if sigma.loc[i, i] > 0 and sigma.loc[j, j] > 0 else 0.0
        for i in sigma.index:
            for j in sigma.columns:
                sigma.loc[i, j] = corr.loc[i, j] * vol[i] * vol[j]
    if not request.use_historical_correlations:
        for key, override in request.correlation_overrides.items():
            id_1, id_2 = key.split("|")
            if id_1 in sigma.index and id_2 in sigma.columns:
                vol_1 = sigma.loc[id_1, id_1] ** 0.5
                vol_2 = sigma.loc[id_2, id_2] ** 0.5
                sigma.loc[id_1, id_2] = override * vol_1 * vol_2
                sigma.loc[id_2, id_1] = override * vol_1 * vol_2

    return mu, sigma
