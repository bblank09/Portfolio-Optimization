"""Black-Litterman equilibrium returns and posterior blending.

Deviation note: the brief suggested checking whether riskfolio-lib 7.3.0
exposes a ready-made Black-Litterman helper (e.g. ``rp.Portfolio.blacklitterman_stats``).
It does (``riskfolio.src.HCPortfolio``/``Portfolio.blacklitterman_stats`` exists),
but that helper is built around riskfolio's own ``Portfolio`` object lifecycle
(it mutates ``self.mu``/``self.cov`` in place and expects the caller to have
already run ``assets_stats``), which doesn't compose cleanly with this
project's `(mu, sigma) -> (equilibrium, posterior)` pure-function interface
consumed directly by `service.py` and `solve_mean_variance`. The closed-form
Black-Litterman math (reverse optimization for equilibrium returns, the
standard posterior-blending formula) is unambiguous and short enough to
implement directly with numpy/pandas, matching the brief's sample code
exactly, so no riskfolio-lib call is used here.
"""

import numpy as np
import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest


def compute_equilibrium_returns(sigma: pd.DataFrame, risk_aversion: float, market_weights: pd.Series) -> pd.Series:
    """Pi = delta * Sigma @ w_mkt (reverse optimization), not a flat
    multiplier on each asset's own historical return -- the mock's own
    equilibriumReturnPct was `expectedReturnPct * 0.8`, which isn't
    equilibrium at all. No true market-cap weights exist for this
    shortlist, so market_weights is the equal-weighted vector by default
    (the same "unknown market portfolio" assumption riskfolio-lib's own
    docs use when one isn't supplied)."""
    w = market_weights.reindex(sigma.index).fillna(0)
    pi = risk_aversion * (sigma.values / 100 / 100) @ w.values
    return pd.Series(pi * 100, index=sigma.index)  # back to percent units


def blend_posterior(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    bl = request.black_litterman
    proj_ids = list(mu.index)
    market_weights = pd.Series(1 / len(proj_ids), index=proj_ids)
    equilibrium = compute_equilibrium_returns(sigma, bl.risk_aversion, market_weights)

    n = len(proj_ids)
    index_of = {proj_id: i for i, proj_id in enumerate(proj_ids)}
    views = [v for v in bl.views if v.asset_proj_id_1 in index_of and (v.asset_proj_id_2 is None or v.asset_proj_id_2 in index_of)]
    if not views:
        return equilibrium, equilibrium.copy()

    k = len(views)
    P = np.zeros((k, n))
    Q = np.zeros(k)
    omega_diag = np.zeros(k)
    sigma_pct = sigma.values / 100 / 100
    for row, view in enumerate(views):
        i = index_of[view.asset_proj_id_1]
        Q[row] = view.adjusted_performance_pct / 100
        if view.view_type.value == "relative" and view.asset_proj_id_2 is not None:
            j = index_of[view.asset_proj_id_2]
            P[row, i] = 1.0
            P[row, j] = -1.0
        else:
            P[row, i] = 1.0
        # Idzorek (2004)-style: lower confidence -> larger Omega (less
        # weight on the view) -- confidence is 100/75/50/25 in this
        # project's UI, so omega scales inversely with it.
        confidence = max(view.confidence, 1) / 100
        view_variance = (P[row : row + 1] @ (bl.tau * sigma_pct) @ P[row : row + 1].T).item()
        omega_diag[row] = view_variance * (1 / confidence - 1) if confidence < 1 else 1e-8

    omega = np.diag(omega_diag)
    tau_sigma = bl.tau * sigma_pct
    pi = equilibrium.values / 100

    middle = np.linalg.inv(np.linalg.inv(tau_sigma) + P.T @ np.linalg.inv(omega) @ P)
    posterior = middle @ (np.linalg.inv(tau_sigma) @ pi + P.T @ np.linalg.inv(omega) @ Q)

    return equilibrium, pd.Series(posterior * 100, index=proj_ids)
