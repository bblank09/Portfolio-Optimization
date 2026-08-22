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
    w = market_weights.reindex(sigma.index).fillna(0).to_numpy(dtype=float)
    pi = risk_aversion * (sigma.to_numpy(dtype=float) / 100 / 100) @ w
    return pd.Series(pi * 100, index=sigma.index)  # back to percent units


def blend_posterior(request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    bl = request.black_litterman
    if bl is None:
        raise ValueError("blackLitterman inputs are required when goal is black_litterman")
    proj_ids = list(mu.index)
    market_weights = pd.Series(1 / len(proj_ids), index=proj_ids)
    equilibrium = compute_equilibrium_returns(sigma, bl.risk_aversion, market_weights)
    # The UI's benchmarkExpectedReturnPct is the expected return of the
    # market portfolio used to anchor Pi. Preserve the risk-implied relative
    # spreads while shifting the equilibrium vector so its market-weighted
    # return equals the explicit user input.
    market_expected_return = float((equilibrium * market_weights).sum())
    equilibrium = equilibrium + (bl.benchmark_expected_return_pct - market_expected_return)

    n = len(proj_ids)
    index_of = {proj_id: i for i, proj_id in enumerate(proj_ids)}
    views = [v for v in bl.views if v.asset_proj_id_1 in index_of and (v.asset_proj_id_2 is None or v.asset_proj_id_2 in index_of)]
    if not views:
        return equilibrium, equilibrium.copy()

    k = len(views)
    P = np.zeros((k, n))
    Q = np.zeros(k)
    omega_diag = np.zeros(k)
    sigma_pct = sigma.to_numpy(dtype=float) / 100 / 100
    for row, view in enumerate(views):
        i = index_of[view.asset_proj_id_1]
        if view.view_type.value == "relative" and view.asset_proj_id_2 is not None:
            j = index_of[view.asset_proj_id_2]
            P[row, i] = 1.0
            P[row, j] = -1.0
            # The UI describes a view as an adjustment relative to the
            # displayed equilibrium figures: "A will outperform B by X".
            # Encode that as the prior equilibrium spread plus X, so a
            # positive relative view moves asset 1 up and asset 2 down.
            Q[row] = (equilibrium.iloc[i] - equilibrium.iloc[j] + view.adjusted_performance_pct) / 100
        else:
            P[row, i] = 1.0
            Q[row] = view.adjusted_performance_pct / 100
        # Idzorek (2004)-style: lower confidence -> larger Omega (less
        # weight on the view) -- confidence is 100/75/50/25 in this
        # project's UI, so omega scales inversely with it.
        confidence = max(view.confidence, 1) / 100
        view_variance = (P[row : row + 1] @ (bl.tau * sigma_pct) @ P[row : row + 1].T).item()
        omega_diag[row] = view_variance * (1 / confidence - 1) if confidence < 1 else 1e-8

    omega = np.diag(omega_diag)
    tau_sigma = bl.tau * sigma_pct
    pi = equilibrium.to_numpy(dtype=float) / 100

    try:
        identity = np.eye(n)
        tau_precision = np.linalg.solve(tau_sigma, identity)
        view_precision = np.linalg.solve(omega, np.eye(k))
        posterior_precision = tau_precision + P.T @ view_precision @ P
        posterior_rhs = tau_precision @ pi + P.T @ view_precision @ Q
        posterior = np.linalg.solve(posterior_precision, posterior_rhs)
    except np.linalg.LinAlgError as exc:
        raise ValueError("INFEASIBLE_CONSTRAINTS") from exc

    if views and all(view.view_type.value == "relative" for view in views):
        # Relative views express a spread, not a change to the market
        # portfolio's expected return. Center the posterior adjustment so the
        # benchmark anchor remains unchanged while both named assets move in
        # the direction of the relative view.
        adjustment = posterior - equilibrium.to_numpy(dtype=float) / 100
        adjustment -= float(np.dot(market_weights.to_numpy(dtype=float), adjustment))
        posterior = equilibrium.to_numpy(dtype=float) / 100 + adjustment

    return equilibrium, pd.Series(posterior * 100, index=proj_ids)
