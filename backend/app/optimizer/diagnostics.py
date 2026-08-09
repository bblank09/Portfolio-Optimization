from backend.app.domain.optimize_schemas import OptimizeRequest


def _raw_turnover(request: OptimizeRequest, optimal_weights: dict[str, float]) -> float:
    if not any(w > 0 for w in request.current_weight_pct.values()):
        return 0.0
    total = 0.0
    for proj_id, optimal in optimal_weights.items():
        current = request.current_weight_pct.get(proj_id, 0.0)
        total += abs(optimal - current)
    return total / 2


def binding_constraints(request: OptimizeRequest, optimal_weights: dict[str, float]) -> list[dict]:
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
        if min_pct > 0 and abs(weight - min_pct) < 0.05:
            findings.append({"label": f"{name}: min weight", "detail": f"Floored at {min_pct}% -- would hold less if allowed."})

    if request.constraints.max_turnover_pct is not None:
        raw = _raw_turnover(request, optimal_weights)
        if raw > request.constraints.max_turnover_pct:
            findings.append({
                "label": "Max turnover",
                "detail": f"Capped at {request.constraints.max_turnover_pct}% one-way turnover per rebalance -- the full rebalance would have needed {raw:.2f}%.",
            })
    return findings


def build_trade_list(request: OptimizeRequest, optimal_weights: dict[str, float]) -> tuple[list[dict], float]:
    if not any(w > 0 for w in request.current_weight_pct.values()):
        return [], 0.0
    fund_names = {fund.proj_id: fund.display_name for fund in request.funds}
    rows = []
    for proj_id, optimal in optimal_weights.items():
        current = request.current_weight_pct.get(proj_id, 0.0)
        delta = round(optimal - current, 2)
        action = "buy" if delta > 0.05 else "sell" if delta < -0.05 else "hold"
        rows.append({
            "projId": proj_id,
            "displayName": fund_names.get(proj_id, proj_id),
            "currentWeightPct": round(current, 2),
            "optimalWeightPct": round(optimal, 2),
            "deltaPct": delta,
            "action": action,
        })
    turnover = round(sum(abs(row["deltaPct"]) for row in rows) / 2, 2)
    return rows, turnover
