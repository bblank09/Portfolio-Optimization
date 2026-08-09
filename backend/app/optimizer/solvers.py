"""Mean-variance family solvers: max_sharpe, min_volatility,
max_return_target_vol, min_variance -- all built on riskfolio-lib's
``rp.Portfolio`` "Classic" model.

Deviations from the task brief's sample code (verified against the actually
installed riskfolio-lib 7.3.0 in
/private/tmp/sec_open_data_portfolio_backtester_venv):

1. ``rp.Portfolio`` has no ``sht``/``uppersht`` setters that take booleans
   the way the brief's draft implies -- ``sht`` is a plain bool ("allow
   shorting") and ``uppersht`` is the shorting budget (float), which is what
   the constructor already defaults sensibly. We instead pass these at
   construction time via ``rp.Portfolio(returns=..., sht=..., uppersht=...)``
   and leave ``upperlng``/``lowerlng`` at their long-only defaults (1/0),
   matching how the constructor's own docstring describes them.
2. ``rp.Portfolio.lowerlng``/``upperlng`` are *scalar* (portfolio-wide)
   bounds -- there is no per-asset bound parameter on the constructor. The
   brief's draft computed per-asset lower/upper arrays but never actually
   fed them into the optimization; it only checked them *after* solving and
   raised ``INFEASIBLE_CONSTRAINTS`` on violation. That does not satisfy
   `test_max_sharpe_respects_fund_bounds` (which expects the bound to be
   *respected*, not detected-and-rejected) whenever the unconstrained
   optimum would violate a per-fund bound. Real per-asset bounds require the
   general linear-constraint mechanism ``ainequality``/``binequality``
   (``A @ w <= b``, verified via ``rp.Portfolio.ainequality`` /
   ``binequality`` property setters in riskfolio's source), so we build that
   matrix explicitly from ``request.fund_bounds`` (falling back to
   ``request.constraints.min_weight_pct``/``max_weight_pct`` per asset).
3. ``port.mu``/``port.cov`` are plain attributes (no custom property
   setters in riskfolio-lib's source), so direct assignment of a 1-row
   DataFrame / a DataFrame is exactly the mechanism ``assets_stats()``
   itself uses internally (``self.mu = pe.mean_vector(...)``) -- this part
   of the brief's draft matched the real API as-is.
4. ``upperdev``/``lowerret`` are confirmed real constructor/attribute names
   on ``rp.Portfolio`` (risk-measure upper bounds table), so those two goal-
   specific constraints from the brief's draft are used unchanged.
"""

import numpy as np
import pandas as pd
import riskfolio as rp

from backend.app.domain.optimize_schemas import OptimizeRequest

# This project's RiskMeasure enum -> riskfolio-lib's own `rm` short codes.
# All four resolve to LP/QP/SOCP problems per riskfolio-lib's own solver
# table, so CLARABEL (free) handles every one -- no MOSEK/GUROBI needed.
RM_CODES: dict[str, str] = {
    "std_dev": "MV",
    "semi_variance": "MSV",
    "cvar": "CVaR",
    "cdar": "CDaR",
}

_OBJ_CODES: dict[str, str] = {
    "max_sharpe": "Sharpe",
    "min_volatility": "MinRisk",
    "max_return_target_vol": "MaxRet",
    "min_variance": "MinRisk",
}


def _asset_bounds(request: OptimizeRequest, proj_ids: list[str]) -> tuple[list[float], list[float]]:
    """Per-asset (lower, upper) weight fractions (0..1), using an explicit
    fund_bounds override when present, else the request's global
    min/max weight constraint."""
    lower, upper = [], []
    for proj_id in proj_ids:
        bound = request.fund_bounds.get(proj_id)
        lower.append((bound.min_weight_pct if bound else request.constraints.min_weight_pct) / 100)
        upper.append((bound.max_weight_pct if bound else request.constraints.max_weight_pct) / 100)
    return lower, upper


def _build_portfolio(
    request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame
) -> rp.Portfolio:
    proj_ids = list(mu.index)
    port = rp.Portfolio(
        returns=returns[proj_ids],
        sht=not request.constraints.long_only,
        uppersht=0.0 if request.constraints.long_only else 1.0,
    )
    # mu/Sigma are supplied directly (already computed in inputs.py per the
    # request's covarianceMethod/overrides) rather than via assets_stats(),
    # so the solver uses exactly the estimates this request asked for.
    port.mu = (mu / 100).to_frame().T
    port.cov = sigma / 100 / 100

    # Per-asset weight bounds via the general linear-constraint mechanism:
    # A @ w <= b encodes both w_i <= upper_i and -w_i <= -lower_i for every
    # asset. lowerlng/upperlng (scalar, portfolio-wide) stay at their
    # constructor defaults (0/1) as a loose backstop.
    lower, upper = _asset_bounds(request, proj_ids)
    n = len(proj_ids)
    a_upper = np.eye(n)
    a_lower = -np.eye(n)
    port.ainequality = np.vstack([a_upper, a_lower])
    port.binequality = np.array(upper + [-lo for lo in lower]).reshape(-1, 1)

    if request.goal.value == "max_return_target_vol" and request.target_annual_volatility_pct is not None:
        port.upperdev = request.target_annual_volatility_pct / 100
    if request.goal.value == "min_volatility" and request.target_annual_return_pct is not None:
        port.lowerret = request.target_annual_return_pct / 100

    port.rf = request.constraints.risk_free_rate_pct / 100
    return port


def solve_mean_variance(
    request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame
) -> dict[str, float]:
    """Handles max_sharpe, min_volatility, max_return_target_vol, min_variance."""
    port = _build_portfolio(request, mu, sigma, returns)
    obj = _OBJ_CODES[request.goal.value]
    # min_variance always optimizes plain variance (MV) regardless of the
    # request's selected risk_measure -- the other three goals honor it.
    rm = "MV" if request.goal.value == "min_variance" else RM_CODES[request.risk_measure.value]

    w = port.optimization(model="Classic", rm=rm, obj=obj, rf=port.rf, l=0, hist=True)
    if w is None:
        raise RuntimeError("SOLVER_NON_CONVERGENCE")

    weights = {proj_id: float(w.loc[proj_id, "weights"]) * 100 for proj_id in w.index}

    lower, upper = _asset_bounds(request, list(mu.index))
    for i, proj_id in enumerate(mu.index):
        lo, hi = lower[i] * 100, upper[i] * 100
        if weights[proj_id] < lo - 0.5 or weights[proj_id] > hi + 0.5:
            raise RuntimeError("INFEASIBLE_CONSTRAINTS")

    return weights


def solve_risk_parity(
    request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame
) -> dict[str, float]:
    """Risk parity via riskfolio-lib's ``rp.Portfolio.rp_optimization`` --
    equalizes each asset's marginal risk contribution rather than
    optimizing a Sharpe/variance objective, so it is a genuinely different
    algorithm from the mean-variance family above (not the same
    inverse-volatility heuristic under a different name)."""
    port = _build_portfolio(request, mu, sigma, returns)
    rm = RM_CODES[request.risk_measure.value]
    w = port.rp_optimization(model="Classic", rm=rm, rf=port.rf, b=None, hist=True)
    if w is None:
        raise RuntimeError("SOLVER_NON_CONVERGENCE")
    return {proj_id: float(w.loc[proj_id, "weights"]) * 100 for proj_id in w.index}


def solve_hrp(request: OptimizeRequest, returns: pd.DataFrame) -> dict[str, float]:
    """Hierarchical Risk Parity via riskfolio-lib's ``rp.HCPortfolio`` --
    clusters assets by codependence and allocates recursively down the
    dendrogram, with no covariance-matrix inversion at all. The real
    ``rp.HCPortfolio`` constructor and ``optimization()`` signatures
    (checked against riskfolio-lib 7.3.0 installed in
    /private/tmp/sec_open_data_portfolio_backtester_venv) match what the
    brief already specified -- ``HCPortfolio(returns=...)`` then
    ``optimization(model="HRP", codependence=..., rm=..., rf=..., linkage=...)``.

    Deviation from the brief's sample code: the brief's ``HCPortfolio(...)``
    call took only ``returns=``, which silently drops
    ``request.fund_bounds``/min-max weight constraints for HRP requests --
    an inconsistency with ``solve_risk_parity``, which enforces bounds via
    ``_build_portfolio``'s ``ainequality``/``binequality``. Fixed by passing
    the same per-asset bounds (via the existing ``_asset_bounds`` helper) as
    ``w_min``/``w_max`` pd.Series -- confirmed real constructor kwargs on
    ``rp.HCPortfolio`` (riskfolio-lib 7.3.0 source, HCPortfolio.py
    lines 64-107 and 1060-1078), accepting a ``pd.Series`` or scalar,
    clipped to [0, 1]."""
    proj_ids = [fund.proj_id for fund in request.funds]
    lower, upper = _asset_bounds(request, proj_ids)
    hc_port = rp.HCPortfolio(
        returns=returns[proj_ids],
        w_min=pd.Series(lower, index=proj_ids),
        w_max=pd.Series(upper, index=proj_ids),
    )
    rm = RM_CODES[request.risk_measure.value]
    w = hc_port.optimization(
        model="HRP",
        codependence="pearson",
        rm=rm,
        rf=request.constraints.risk_free_rate_pct / 100,
        linkage="single",
    )
    if w is None:
        raise RuntimeError("SOLVER_NON_CONVERGENCE")
    return {proj_id: float(w.loc[proj_id, "weights"]) * 100 for proj_id in w.index}
