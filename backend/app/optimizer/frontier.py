"""Efficient-frontier sweep and GMV/tangency marker extraction.

Deviations from the task brief's sample code (verified against the actually
installed riskfolio-lib 7.3.0 in
/private/tmp/sec_open_data_portfolio_backtester_venv):

1. ``_build_portfolio`` (Task 5, ``backend/app/optimizer/solvers.py``)
   returns a single ``rp.Portfolio`` instance, not a 3-tuple -- the brief's
   ``port, _, _ = _build_portfolio(...)`` does not match its real signature.
   Fixed to ``port = _build_portfolio(...)``.
2. ``rp.Portfolio.efficient_frontier(model, rm, kelly, points, rf, solver,
   hist)`` (confirmed via ``inspect.signature`` and its own docstring)
   returns a DataFrame indexed by asset (rows) with one column per swept
   point -- exactly what the brief assumed (``frontier_weights.T.iterrows()``
   iterates points, ``row[proj_id]`` reads that point's weight for an
   asset). No deviation needed there.
3. The brief's sample Sharpe was plain ``return / volatility`` (no
   risk-free subtraction). Sharpe ratio is excess return over the
   risk-free rate divided by volatility, so this module subtracts
   ``request.constraints.risk_free_rate_pct`` in the numerator, matching
   how ``port.rf`` is used elsewhere in Task 5's ``solvers.py``.

Consistency guarantee (the landmine this task exists to avoid): every
frontier point's ``expectedReturnPct``/``volatilityPct``/``sharpe`` is
derived directly from that same point's ``weights`` dict inside this
module -- never recomputed independently -- so a point can never disagree
with its own displayed weights. ``extract_markers`` enforces the same
guarantee for the GMV and tangency markers by selecting them *from the
already-built frontier list* (``min``/``max`` over ``frontier_points``)
rather than resolving a fresh optimization for either one, so their
(volatilityPct, expectedReturnPct) pairs are always literally present in
the list ``build_frontier`` returned -- guaranteed on the frontier curve by
construction, not merely close to it. The optimal-portfolio marker is the
one deliberate exception: it reflects ``optimal_weights`` from Task 5's
solver (which may carry per-fund bounds or a different objective than the
plain frontier sweep), so it can legitimately sit off the drawn curve --
that is flagged explicitly via its own ``label`` rather than silently
implied to lie on the line.
"""

import contextlib
import io
import logging
from typing import cast

import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.solvers import RM_CODES, _build_portfolio

logger = logging.getLogger("app.optimizer.frontier")

# The chart keeps sub-basis-point geometry so a narrow volatility range does
# not collapse into a staircase after rounding. Only points that are truly
# numerically identical are deduplicated; the UI formats them to two decimal
# places when presenting labels and tables.
_POINT_TOLERANCE = 0.00005


def _portfolio_stats(weights: dict[str, float], mu: pd.Series, sigma: pd.DataFrame) -> tuple[float, float]:
    """Return (expected_return_pct, volatility_pct) computed directly from
    a weights dict -- the single source of truth both build_frontier and
    extract_markers use, so a point's displayed stats can never drift from
    its displayed weights."""
    expected_return = sum(float(mu[proj_id]) * (float(w) / 100) for proj_id, w in weights.items())
    variance = 0.0
    for i, wi in weights.items():
        for j, wj in weights.items():
            variance += (float(wi) / 100) * (float(wj) / 100) * (float(cast(float, sigma.loc[i, j])) / 100 / 100)
    volatility = (variance**0.5) * 100
    return expected_return, volatility


def build_frontier(
    request: OptimizeRequest,
    mu: pd.Series,
    sigma: pd.DataFrame,
    returns: pd.DataFrame,
    points: int = 80,
) -> list[dict]:
    """Sweep riskfolio-lib's real efficient frontier for the request's
    selected risk measure and return 80 points, each with weights and
    stats derived from those same weights (see module docstring)."""
    # apply_goal_targets=False: the sweep needs an UNCONSTRAINED portfolio.
    # See the comment at that flag in solvers._build_portfolio -- inheriting
    # the max_return_target_vol goal's `upperdev` ceiling made riskfolio raise
    # `NameError: The limits of the frontier can't be found` on every such
    # request. The goal's real constraint still applies to the actual solve;
    # its optimum is plotted as a marker on this unconstrained curve.
    port = _build_portfolio(request, mu, sigma, returns, apply_goal_targets=False)
    rm = RM_CODES[request.risk_measure.value]
    # riskfolio-lib 7.3.0's efficient_frontier has no `verbose` switch: it
    # `print()`s solver diagnostics straight to stdout. Capture them so they
    # land in the application log instead of polluting raw process output.
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        frontier_weights = port.efficient_frontier(model="Classic", rm=rm, rf=port.rf, points=points, hist=True)
    noise = captured.getvalue().strip()
    if noise:
        logger.warning("riskfolio efficient_frontier diagnostics: %s", noise.replace("\n", " | "))
    if frontier_weights is None or frontier_weights.empty:
        raise RuntimeError("SOLVER_NON_CONVERGENCE")

    proj_ids = list(mu.index)
    result = []
    for _, row in frontier_weights.T.iterrows():
        weights = {proj_id: float(row[proj_id]) * 100 for proj_id in proj_ids}
        expected_return, volatility = _portfolio_stats(weights, mu, sigma)
        sharpe = (expected_return - request.constraints.risk_free_rate_pct) / volatility if volatility > 0 else 0.0
        result.append(
            {
                # Keep analytical precision in the response. Consumers can
                # format for display, but rounding here makes a narrow
                # frontier (e.g. 19.18% to 19.26% volatility) visibly jagged.
                "volatilityPct": round(volatility, 6),
                "expectedReturnPct": round(expected_return, 6),
                "sharpe": round(sharpe, 6),
                "weights": {k: round(v, 6) for k, v in weights.items()},
            }
        )
    return _dedupe_points(result, requested=points)


def _dedupe_points(result: list[dict], *, requested: int) -> list[dict]:
    """Collapse numerically-identical frontier points.

    A near-degenerate fund set (e.g. two funds with correlation ~1) makes
    riskfolio return `points` rows that are all the same portfolio. Returning
    a stack of duplicates presents a collapsed frontier as if it were a real
    curve. Deduping is the smaller change than inventing a new error code:
    the caller sees a shorter `frontier` list -- one point in the fully
    degenerate case -- and the reduction is logged.
    """
    distinct: list[dict] = []
    for point in result:
        if any(
            abs(point["volatilityPct"] - kept["volatilityPct"]) <= _POINT_TOLERANCE
            and abs(point["expectedReturnPct"] - kept["expectedReturnPct"]) <= _POINT_TOLERANCE
            for kept in distinct
        ):
            continue
        distinct.append(point)
    if len(distinct) < requested:
        logger.warning(
            "frontier sweep collapsed: %d of %d requested points were numerically distinct",
            len(distinct), requested,
        )
    return distinct


def extract_markers(
    frontier_points: list[dict],
    optimal_weights: dict[str, float],
    mu: pd.Series,
    sigma: pd.DataFrame,
) -> tuple[dict, dict | None, dict | None]:
    """Locate the optimal/GMV/tangency marker points.

    GMV and tangency are picked *from frontier_points itself* (min
    volatility / max Sharpe among the already-built list), so their
    coordinates are guaranteed to be points literally on the frontier this
    module computed -- never independently recomputed. The optimal marker
    reflects Task 5's solver output for the request's actual goal/bounds,
    which may legitimately differ from the plain frontier sweep (e.g. a
    tighter per-fund bound), so it is computed from ``optimal_weights``
    directly and labeled accordingly rather than assumed to lie on the
    curve.
    """
    optimal_return, optimal_volatility = _portfolio_stats(optimal_weights, mu, sigma)
    optimal_marker = {
        "volatilityPct": round(optimal_volatility, 2),
        "expectedReturnPct": round(optimal_return, 2),
        "label": "Your optimal portfolio",
    }
    if not frontier_points:
        return optimal_marker, None, None

    gmv_point = min(frontier_points, key=lambda p: p["volatilityPct"])
    tangency_point = max(frontier_points, key=lambda p: p["sharpe"])
    gmv_marker = {
        "volatilityPct": gmv_point["volatilityPct"],
        "expectedReturnPct": gmv_point["expectedReturnPct"],
        "label": "Global minimum variance",
    }
    tangency_marker = {
        "volatilityPct": tangency_point["volatilityPct"],
        "expectedReturnPct": tangency_point["expectedReturnPct"],
        "label": "Max Sharpe (tangency)",
    }
    return optimal_marker, gmv_marker, tangency_marker
