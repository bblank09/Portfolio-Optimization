import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer import constraints


def _raw_turnover(request: OptimizeRequest, optimal_weights: dict[str, float]) -> float:
    total = 0.0
    for proj_id, optimal in optimal_weights.items():
        current = request.current_weight_pct.get(proj_id, 0.0)
        total += abs(optimal - current)
    return total / 2


def binding_constraints(
    request: OptimizeRequest,
    optimal_weights: dict[str, float],
    returns: pd.DataFrame | None = None,
    benchmark_returns: pd.Series | None = None,
) -> list[dict]:
    """Report only constraints the solver's weights ACTUALLY hit (within a small
    numerical tolerance of the boundary) -- never a constraint just because it
    was configured on the request."""
    findings: list[dict] = []
    fund_names = {fund.proj_id: fund.display_name for fund in request.funds}
    for proj_id, weight in optimal_weights.items():
        bound = request.fund_bounds.get(proj_id)
        max_pct = bound.max_weight_pct if bound else request.constraints.max_weight_pct
        min_pct = bound.min_weight_pct if bound else request.constraints.min_weight_pct
        name = fund_names.get(proj_id, proj_id)
        if max_pct < 100 and abs(weight - max_pct) < 0.05:
            findings.append({"label": f"{name}: max weight", "detail": f"Capped at {max_pct}% -- would hold more if allowed."})
        if min_pct != 0 and abs(weight - min_pct) < 0.05:
            findings.append({"label": f"{name}: min weight", "detail": f"Floored at {min_pct}% -- would hold less if allowed."})

    if request.constraints.max_turnover_pct is not None:
        raw = _raw_turnover(request, optimal_weights)
        if raw >= request.constraints.max_turnover_pct - 0.05:
            findings.append({
                "label": "Max turnover",
                "detail": f"Capped at {request.constraints.max_turnover_pct}% one-way turnover per rebalance -- the full rebalance would have needed {raw:.2f}%.",
            })
    if (
        request.constraints.max_tracking_error_pct is not None
        and returns is not None
        and benchmark_returns is not None
    ):
        tracking_error = constraints.tracking_error_pct(request, optimal_weights, returns, benchmark_returns)
        if tracking_error >= request.constraints.max_tracking_error_pct - 0.05:
            findings.append({
                "label": "Max tracking error",
                "detail": f"Capped at {request.constraints.max_tracking_error_pct}% versus the selected benchmark (realized {tracking_error:.2f}%).",
            })
    return findings


def build_trade_list(request: OptimizeRequest, optimal_weights: dict[str, float]) -> tuple[list[dict], float]:
    fund_names = {fund.proj_id: fund.display_name for fund in request.funds}
    rows = []
    deltas: list[float] = []
    for proj_id, optimal in optimal_weights.items():
        current = request.current_weight_pct.get(proj_id, 0.0)
        delta = round(optimal - current, 2)
        deltas.append(delta)
        action = "buy" if delta > 0.05 else "sell" if delta < -0.05 else "hold"
        rows.append({
            "projId": proj_id,
            "displayName": fund_names.get(proj_id, proj_id),
            "currentWeightPct": round(current, 2),
            "optimalWeightPct": round(optimal, 2),
            "deltaPct": delta,
            "action": action,
        })
    turnover = round(sum(abs(delta) for delta in deltas) / 2, 2)
    return rows, turnover
