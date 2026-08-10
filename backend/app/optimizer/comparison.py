"""Comparison-portfolio computation for compareAgainst and
benchmarkProjId. See
docs/superpowers/specs/2026-08-10-phase5-comparison-features-design.md for
the full design (why every comparison respects the same fund bounds as the
main solve, why a comparison failure never fails the whole request).
"""

from __future__ import annotations

import pandas as pd

from backend.app.domain.optimize_schemas import ObjectiveGoal, OptimizeRequest
from backend.app.optimizer import solvers


def _clamp_and_renormalize(
    raw: dict[str, float], lower: list[float], upper: list[float], proj_ids: list[str]
) -> dict[str, float]:
    """Water-filling clamp: distributes 1.0 of budget proportionally to
    `raw`'s relative shares, pinning any fund that would exceed its bound
    to that bound and redistributing the remainder among the still-free
    funds, one violation at a time until none remain. Returns percentages
    (0..100) summing to 100, not fractions.

    Example: 3 equal-raw-share funds, A capped at 20% (below its 1/3 raw
    share) -> A pins at 20%, remaining 80% splits evenly across B/C (40%
    each) -- see test_clamp_and_renormalize_respects_a_tight_cap.
    """
    w = {pid: max(raw.get(pid, 0.0), 0.0) for pid in proj_ids}
    lo = dict(zip(proj_ids, lower))
    hi = dict(zip(proj_ids, upper))
    fixed_total = 0.0
    free = set(proj_ids)
    for _ in range(len(proj_ids)):
        remaining_budget = 1.0 - fixed_total
        free_raw_sum = sum(w[p] for p in free)
        if free_raw_sum > 0:
            share = {p: w[p] / free_raw_sum * remaining_budget for p in free}
        else:
            share = {p: remaining_budget / len(free) for p in free} if free else {}
        violator = None
        for p in free:
            if share[p] > hi[p] + 1e-9:
                violator = (p, hi[p])
                break
            if share[p] < lo[p] - 1e-9:
                violator = (p, lo[p])
                break
        if violator is None:
            for p in free:
                w[p] = share[p]
            break
        p, bound = violator
        w[p] = bound
        fixed_total += bound
        free.discard(p)
    return {pid: round(w[pid] * 100, 4) for pid in proj_ids}


def _equal_weighted_weights(request: OptimizeRequest, proj_ids: list[str]) -> dict[str, float]:
    raw = {pid: 1.0 / len(proj_ids) for pid in proj_ids}
    lower, upper = solvers._asset_bounds(request, proj_ids)
    return _clamp_and_renormalize(raw, lower, upper, proj_ids)


def _inverse_volatility_weights(request: OptimizeRequest, sigma: pd.DataFrame, proj_ids: list[str]) -> dict[str, float]:
    vol = pd.Series(sigma.values.diagonal(), index=sigma.index) ** 0.5
    inv_vol = {pid: (1.0 / vol[pid] if vol[pid] > 0 else 0.0) for pid in proj_ids}
    total = sum(inv_vol.values())
    raw = {pid: (inv_vol[pid] / total if total > 0 else 1.0 / len(proj_ids)) for pid in proj_ids}
    lower, upper = solvers._asset_bounds(request, proj_ids)
    return _clamp_and_renormalize(raw, lower, upper, proj_ids)


def build_comparison_weights(
    request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame
) -> tuple[dict[str, float] | None, str | None]:
    """Dispatches on request.constraints.compare_against. Returns
    (weights, note) -- note is only non-None when compare_against was
    requested but weights could not be produced (a solve failure on the
    comparison path never fails the whole request, per this project's
    non-blocking-secondary-feature principle)."""
    compare_against = request.constraints.compare_against.value
    proj_ids = list(mu.index)

    if compare_against == "none":
        return None, None

    if compare_against == "current":
        if not request.current_weight_pct:
            return None, None
        return dict(request.current_weight_pct), None

    if compare_against == "equal_weighted":
        return _equal_weighted_weights(request, proj_ids), None

    if compare_against == "inverse_volatility":
        return _inverse_volatility_weights(request, sigma, proj_ids), None

    # max_sharpe / risk_parity: reuse the exact same dispatch the main
    # solve uses, with only the goal swapped -- same mu/sigma/returns/
    # constraints, so the comparison is genuinely apples-to-apples.
    alt_request = request.model_copy(update={"goal": ObjectiveGoal(compare_against)})
    try:
        return solvers.solve_for_goal(alt_request, mu, sigma, returns), None
    except (ValueError, RuntimeError) as exc:
        return None, f"Comparison against {compare_against} could not be computed: {exc}"
