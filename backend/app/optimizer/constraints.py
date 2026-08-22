"""Post-solve continuous portfolio constraints.

Riskfolio handles the objective-specific allocation, per-asset bounds, and
group caps. Turnover and tracking error depend on the current portfolio and a
benchmark return series, so they are enforced in one shared projection step
after the objective solve (and after any max-holdings adjustment). The
projection minimizes distance to the objective solution while satisfying all
continuous constraints; infeasible requests fail loudly instead of returning
an allocation that violates a user-selected cap.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from backend.app.domain.optimize_schemas import OptimizeRequest

_PERIODS_PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12}
_TOLERANCE = 1e-5


def turnover_pct(request: OptimizeRequest, weights: dict[str, float]) -> float:
    """One-way turnover in percentage points for the selected fund set."""
    proj_ids = [fund.proj_id for fund in request.funds]
    return sum(abs(weights.get(proj_id, 0.0) - request.current_weight_pct.get(proj_id, 0.0)) for proj_id in proj_ids) / 2


def tracking_error_pct(
    request: OptimizeRequest,
    weights: dict[str, float],
    returns: pd.DataFrame,
    benchmark_returns: pd.Series,
) -> float:
    """Annualized tracking error in percentage points."""
    proj_ids = [fund.proj_id for fund in request.funds]
    portfolio = returns[proj_ids].mul(
        [weights.get(proj_id, 0.0) / 100 for proj_id in proj_ids], axis=1
    ).sum(axis=1)
    aligned = pd.concat([portfolio.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    if len(aligned) < 2:
        return 0.0
    periods_per_year = _PERIODS_PER_YEAR[request.data_frequency.value]
    return float((aligned["portfolio"] - aligned["benchmark"]).std(ddof=1) * np.sqrt(periods_per_year) * 100)


def _asset_bounds(request: OptimizeRequest, proj_ids: list[str]) -> list[tuple[float, float]]:
    bounds: list[tuple[float, float]] = []
    for proj_id in proj_ids:
        bound = request.fund_bounds.get(proj_id)
        lower = bound.min_weight_pct if bound else request.constraints.min_weight_pct
        upper = bound.max_weight_pct if bound else request.constraints.max_weight_pct
        bounds.append((float(lower), float(upper)))
    return bounds


def _initial_point(target: np.ndarray, bounds: list[tuple[float, float]]) -> np.ndarray:
    """Create a bounded starting point close to the requested target."""
    lower = np.array([bound[0] for bound in bounds], dtype=float)
    upper = np.array([bound[1] for bound in bounds], dtype=float)
    point = np.clip(np.nan_to_num(target, nan=0.0), lower, upper)
    if abs(float(point.sum()) - 100.0) <= _TOLERANCE:
        return point

    point = np.clip(np.full(len(bounds), 100.0 / len(bounds)), lower, upper)
    for _ in range(len(bounds) * 2 + 1):
        difference = 100.0 - float(point.sum())
        if abs(difference) <= _TOLERANCE:
            break
        capacity = (upper - point) if difference > 0 else (point - lower)
        available = float(capacity.sum())
        if available <= _TOLERANCE:
            break
        point += difference * capacity / available
        point = np.clip(point, lower, upper)
    return point


def _group_constraint_functions(request: OptimizeRequest, proj_ids: list[str]):
    if not request.constraints.group_constraints_enabled:
        return []
    functions = []
    for group_id, group in request.asset_groups.items():
        indices = [index for index, proj_id in enumerate(proj_ids) if request.fund_groups.get(proj_id) == group_id]
        if not indices:
            continue
        functions.append(lambda weights, indices=indices, maximum=group.max_weight_pct: maximum - weights[indices].sum())
        functions.append(lambda weights, indices=indices, minimum=group.min_weight_pct: weights[indices].sum() - minimum)
    return functions


def _feasible(
    request: OptimizeRequest,
    weights: np.ndarray,
    returns: pd.DataFrame,
    benchmark_returns: pd.Series | None,
    bounds: list[tuple[float, float]],
) -> bool:
    if abs(float(weights.sum()) - 100.0) > 5 * _TOLERANCE:
        return False
    for value, (lower, upper) in zip(weights, bounds, strict=True):
        if value < lower - 5 * _TOLERANCE or value > upper + 5 * _TOLERANCE:
            return False
    if any(function(weights) < -5 * _TOLERANCE for function in _group_constraint_functions(request, [fund.proj_id for fund in request.funds])):
        return False
    if request.constraints.max_turnover_pct is not None:
        candidate = {fund.proj_id: float(weights[index]) for index, fund in enumerate(request.funds)}
        if turnover_pct(request, candidate) > request.constraints.max_turnover_pct + 5 * _TOLERANCE:
            return False
    if request.constraints.max_tracking_error_pct is not None:
        if benchmark_returns is None:
            return False
        candidate = {fund.proj_id: float(weights[index]) for index, fund in enumerate(request.funds)}
        if tracking_error_pct(request, candidate, returns, benchmark_returns) > request.constraints.max_tracking_error_pct + 5 * _TOLERANCE:
            return False
    return True


def enforce_portfolio_constraints(
    request: OptimizeRequest,
    weights: dict[str, float],
    returns: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
) -> dict[str, float]:
    """Project solved weights onto the requested turnover/tracking feasible set."""
    max_turnover = request.constraints.max_turnover_pct
    max_tracking_error = request.constraints.max_tracking_error_pct
    if max_turnover is None and max_tracking_error is None:
        return dict(weights)
    if max_tracking_error is not None and benchmark_returns is None:
        raise ValueError("BENCHMARK_DATA_UNAVAILABLE")

    proj_ids = [fund.proj_id for fund in request.funds]
    bounds = _asset_bounds(request, proj_ids)
    target = np.array([weights.get(proj_id, 0.0) for proj_id in proj_ids], dtype=float)
    # Preserve the sparse solution produced by maxHoldings while projecting
    # it onto continuous turnover/tracking constraints. Without these fixed
    # zero bounds, SLSQP can reintroduce a trimmed asset simply to satisfy a
    # cap, so the final allocation would violate the cardinality constraint
    # it had just been told to honor.
    active_count = int(np.count_nonzero(np.abs(target) > 0.5))
    if request.constraints.max_holdings < len(proj_ids) and active_count <= request.constraints.max_holdings:
        bounds = [
            (0.0, 0.0) if abs(target[index]) <= 0.5 else bound
            for index, bound in enumerate(bounds)
        ]
    start = _initial_point(target, bounds)
    constraints = [{"type": "eq", "fun": lambda candidate: float(candidate.sum() - 100.0)}]
    constraints.extend({"type": "ineq", "fun": function} for function in _group_constraint_functions(request, proj_ids))

    if max_turnover is not None:
        current = np.array([request.current_weight_pct.get(proj_id, 0.0) for proj_id in proj_ids], dtype=float)
        constraints.append({
            "type": "ineq",
            "fun": lambda candidate: float(max_turnover - np.abs(candidate - current).sum() / 2),
        })

    if max_tracking_error is not None and benchmark_returns is not None:
        def tracking_constraint(candidate: np.ndarray) -> float:
            candidate_weights = {proj_id: float(candidate[index]) for index, proj_id in enumerate(proj_ids)}
            return float(max_tracking_error - tracking_error_pct(request, candidate_weights, returns, benchmark_returns))

        constraints.append({"type": "ineq", "fun": tracking_constraint})

    result = minimize(
        lambda candidate: float(np.sum((candidate - target) ** 2)),
        start,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-10, "maxiter": 500},
    )  # type: ignore[call-overload]
    if not result.success or not _feasible(request, result.x, returns, benchmark_returns, bounds):
        raise ValueError("INFEASIBLE_CONSTRAINTS")
    return {proj_id: round(float(result.x[index]), 8) for index, proj_id in enumerate(proj_ids)}
