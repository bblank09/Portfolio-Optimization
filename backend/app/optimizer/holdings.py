"""Greedy post-solve heuristic for maxHoldings (a cardinality cap). Exact
enforcement needs a Mixed-Integer solver -- confirmed via riskfolio-lib
7.3.0's own `card` parameter (constructs a boolean CVXPY variable) and a
direct test that HiGHS (the only free MI-capable solver installed) cannot
solve a mixed boolean + SOCP problem, only pure MILP. This project's risk
measures (std_dev/semi-variance/CVaR/CDaR) are all SOCP-based, so exact
cardinality is out of reach without MOSEK/GUROBI, which this project does
not use. See
docs/superpowers/specs/2026-08-10-phase5-portfolio-constraints-design.md
for the full research finding.
"""

from __future__ import annotations

import pandas as pd

from backend.app.domain.optimize_schemas import FundBound, OptimizeRequest
from backend.app.optimizer import solvers

# A weight below this (in percent) is treated as "not really held" --
# the same +/-0.5 percentage-point tolerance solvers.solve_mean_variance
# already applies in its post-solve bound check, so a fund the solver left
# at solver noise does not count against the cardinality cap.
_MIN_HOLDING_PCT = 0.5


def enforce_max_holdings(
    request: OptimizeRequest,
    mu: pd.Series,
    sigma: pd.DataFrame,
    returns: pd.DataFrame,
    *,
    initial_weights: dict[str, float] | None = None,
) -> tuple[dict[str, float], str | None]:
    """Solves once via the normal dispatch (or uses initial_weights as the
    initial solve, when provided, e.g. robust.resample_and_solve's Monte
    Carlo average); if more funds hold weight than
    request.constraints.max_holdings allows, iteratively pins the
    smallest-weight fund's bounds to zero (via a per-request fund_bounds
    override -- the same mechanism FundBound already provides, no new
    pinning mechanism) and re-solves, one fund at a time, until the held
    count is within the cap or a solve fails. A mid-loop failure returns
    the last successfully-solved weights (which may still exceed the cap)
    with a constraintNote explaining the shortfall -- never a hard error,
    the main solve result is always returned.
    """
    max_holdings = request.constraints.max_holdings
    # initial_weights lets a caller supply an already-computed initial
    # solve (e.g. robust.resample_and_solve's Monte Carlo average) instead
    # of a plain solve_for_goal call -- only the INITIAL solve is
    # substitutable; every trim-loop re-solve below still calls plain
    # solve_for_goal (re-running 500 resamples per trimmed fund would be
    # far too expensive, and is out of this parameter's scope).
    weights = initial_weights if initial_weights is not None else solvers.solve_for_goal(request, mu, sigma, returns)
    held = [pid for pid, w in weights.items() if w > _MIN_HOLDING_PCT]
    if len(held) <= max_holdings:
        return weights, None

    current_request = request
    last_good_weights = weights
    dropped: list[str] = []

    while True:
        held = [pid for pid, w in last_good_weights.items() if w > _MIN_HOLDING_PCT]
        if len(held) <= max_holdings:
            break

        smallest = min(held, key=lambda pid: last_good_weights[pid])
        candidate_bounds = dict(current_request.fund_bounds)
        candidate_bounds[smallest] = FundBound(min_weight_pct=0.0, max_weight_pct=0.0)
        candidate_request = current_request.model_copy(update={"fund_bounds": candidate_bounds})

        try:
            candidate_weights = solvers.solve_for_goal(candidate_request, mu, sigma, returns)
        except (ValueError, RuntimeError):
            progress = (
                f"{len(dropped)} fund(s) dropped ({', '.join(dropped)})"
                if dropped
                else "no fund could be dropped"
            )
            note = (
                f"Could not fully trim to the {max_holdings}-holding cap: "
                f"{progress} before the solve became "
                "infeasible; showing the last successful allocation."
            )
            return last_good_weights, note

        dropped.append(smallest)
        current_request = candidate_request
        last_good_weights = candidate_weights

    note = f"Trimmed {len(dropped)} fund(s) to satisfy the {max_holdings}-holding cap: {', '.join(dropped)}."
    return last_good_weights, note
