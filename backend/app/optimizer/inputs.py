from typing import cast

import numpy as np
import pandas as pd

from backend.app.data.quality import (
    align_nav_panel,
    missing_business_days,
    validate_nav_panel,
)
from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer import black_litterman
from backend.app.sec.cache import load_nav_panel

_PERIODS_PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12}


def _load_returns_for(proj_ids: list[str], request: OptimizeRequest, error_code: str) -> pd.DataFrame:
    """Load, align, and slice the NAV panel for the given proj_ids and the
    request's time period, then convert to simple period returns. Shared by
    build_returns_panel (the optimized funds) and load_benchmark_returns (an
    independent benchmark fund) so the two paths can never diverge -- only
    the raised error_code differs between callers.

    Raises ``ValueError(error_code)`` -- the bare ErrorCode name, the same
    convention every other raise site in this module uses -- when the
    aligned window is unusable. "Unusable" includes ANY missing
    observation, not just a proj_id that is entirely absent (see
    build_returns_panel's original docstring for why: a mid-window gap must
    never be forward-filled or interpolated).
    """
    # A missing parquet cache surfaces here as FileNotFoundError; it is left
    # to propagate so the API route can map it to NAV_CACHE_MISSING (503),
    # matching backend/app/api/backtests.py's handling of the same case.
    nav = align_nav_panel(load_nav_panel(proj_ids), frequency=request.data_frequency.value)
    if any(proj_id not in nav.columns for proj_id in proj_ids):
        # A proj_id entirely absent from the cache (e.g. an unrecognized
        # benchmark) has no column to slice at all -- .loc below would
        # raise a bare KeyError instead of this function's documented
        # ValueError(error_code) contract.
        raise ValueError(error_code)
    window = nav.loc[pd.Timestamp(request.time_period.start_date):pd.Timestamp(request.time_period.end_date), proj_ids]
    if window.empty or window.isna().to_numpy().any():
        raise ValueError(error_code)
    if request.data_frequency.value == "daily" and missing_business_days(pd.DatetimeIndex(window.index)):
        raise ValueError(error_code)
    issues = validate_nav_panel(window, as_of=pd.Timestamp(request.time_period.end_date))
    if any(issue["severity"] == "error" for issue in issues):
        raise ValueError(error_code)
    returns = window.pct_change().dropna(how="all")
    if returns.empty:
        raise ValueError(error_code)
    return returns


def build_returns_panel(request: OptimizeRequest) -> pd.DataFrame:
    """Load, align, and slice the NAV panel for the request's funds and
    time period, then convert to simple period returns. See
    _load_returns_for for the shared implementation and error-raising
    convention (this wrapper always raises "INSUFFICIENT_NAV_HISTORY")."""
    proj_ids = [fund.proj_id for fund in request.funds]
    return _load_returns_for(proj_ids, request, "INSUFFICIENT_NAV_HISTORY")


def load_benchmark_returns(benchmark_proj_id: str, request: OptimizeRequest) -> pd.Series:
    """The benchmark fund's own return series, aligned and validated
    identically to the optimized funds' panel via _load_returns_for, but
    raising "BENCHMARK_DATA_UNAVAILABLE" instead of
    "INSUFFICIENT_NAV_HISTORY" on failure -- per this project's decision,
    insufficient benchmark data is a hard error for the whole request, not
    a degrade-gracefully case."""
    panel = _load_returns_for([benchmark_proj_id], request, "BENCHMARK_DATA_UNAVAILABLE")
    return cast(pd.Series, panel[benchmark_proj_id])


def periods_per_year(request: OptimizeRequest) -> int:
    return _PERIODS_PER_YEAR[request.data_frequency.value]


def portfolio_return_series(
    returns: pd.DataFrame,
    weights: dict[str, float],
    columns: list[str] | None = None,
) -> pd.Series:
    """A weight set's realized periodic return series (fractions) over
    ``returns``: the weighted sum of the funds' own realized returns.

    Single implementation shared by service.py's main-solve realized
    performance and rolling.py's per-fold out-of-sample scoring. Those two
    used to carry byte-identical copies of the ``weights.get(id, 0)/100``
    -> matrix-multiply -> ``dropna()`` chain, which is exactly the drift
    risk solvers.solve_for_goal was extracted to prevent.

    ``columns`` selects and orders the columns to score (rolling passes the
    request's proj_ids); omitted, ``returns.columns`` is used as-is. A
    weight absent from ``weights`` counts as 0%.
    """
    selected = returns if columns is None else returns[columns]
    aligned = np.array([weights.get(str(column), 0.0) / 100 for column in selected.columns])
    return cast(pd.Series, (selected @ aligned).dropna())


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

    if request.return_method == "capm_implied" and request.goal != "black_litterman":
        # Reuses the exact same reverse-optimization formula
        # (Pi = risk_aversion * Sigma @ w_mkt) Black-Litterman already
        # implements -- this return method can be selected independently
        # of goal=black_litterman, so it uses standard defaults rather than
        # requiring request.black_litterman to be set. goal=black_litterman
        # is excluded here because it has its own separate equilibrium ->
        # posterior pipeline (black_litterman.blend_posterior, called from
        # service.py) that this branch would otherwise shadow.
        market_weights = pd.Series(1.0 / len(sigma.index), index=sigma.index)
        mu = black_litterman.compute_equilibrium_returns(sigma, risk_aversion=2.5, market_weights=market_weights)
    else:
        mu = pct_returns.mean() * ppy
    if not request.use_historical_returns:
        for proj_id, override in request.expected_return_overrides.items():
            if proj_id in mu.index:
                mu[proj_id] = override
    if not request.use_historical_volatility:
        vol = pd.Series(np.sqrt(sigma.to_numpy(dtype=float).diagonal()), index=sigma.index)
        for proj_id, override in request.volatility_overrides.items():
            if proj_id in vol.index:
                vol[proj_id] = override
        corr = sigma.copy()
        for i in sigma.index:
            for j in sigma.columns:
                variance_i = float(cast(float, sigma.loc[i, i]))
                variance_j = float(cast(float, sigma.loc[j, j]))
                corr.loc[i, j] = float(cast(float, sigma.loc[i, j])) / (variance_i**0.5 * variance_j**0.5) if variance_i > 0 and variance_j > 0 else 0.0
        for i in sigma.index:
            for j in sigma.columns:
                sigma.loc[i, j] = float(corr.loc[i, j]) * float(vol[i]) * float(vol[j])
    if not request.use_historical_correlations:
        for key, override in request.correlation_overrides.items():
            id_1, id_2 = key.split("|")
            if id_1 in sigma.index and id_2 in sigma.columns:
                vol_1 = float(cast(float, sigma.loc[id_1, id_1])) ** 0.5
                vol_2 = float(cast(float, sigma.loc[id_2, id_2])) ** 0.5
                sigma.loc[id_1, id_2] = override * vol_1 * vol_2
                sigma.loc[id_2, id_1] = override * vol_1 * vol_2

    if not request.use_historical_correlations and request.correlation_overrides:
        eigenvalues = np.linalg.eigvalsh(sigma.values)
        if (eigenvalues < -1e-8).any():
            raise ValueError("INDEFINITE_CORRELATION_MATRIX")

    return mu, sigma
