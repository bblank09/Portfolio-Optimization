"""Comparison-portfolio computation for compareAgainst and
benchmarkProjId. See
docs/superpowers/specs/2026-08-10-phase5-comparison-features-design.md for
the full design (why every comparison respects the same fund bounds as the
main solve, why a comparison failure never fails the whole request).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from backend.app.domain.optimize_schemas import ObjectiveGoal, OptimizeRequest
from backend.app.engine import metrics
from backend.app.optimizer import inputs, solvers

logger = logging.getLogger("app.optimize")

_UNIVERSE_PATH = Path("data/sec/mvp_fund_universe.csv")


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
        # Restrict to the optimized fund set and renormalize to 100. Raw
        # passthrough leaked phantom proj_ids the frontend cannot resolve,
        # and scored a partially-invested portfolio under a comparedValue
        # that claims comparability with the fully-invested optimized one
        # (solvers.realized_risk silently drops unknown ids). Degrading with
        # a note beats failing a request whose main solve is fine.
        held = {pid: request.current_weight_pct.get(pid, 0.0) for pid in proj_ids}
        total = sum(held.values())
        if total <= 0:
            return None, None
        dropped = set(request.current_weight_pct) - set(proj_ids)
        note = None
        if dropped or abs(total - 100) > 0.5:
            note = (
                "Current holdings were rescaled to the optimized fund set"
                + (f" (excluded: {', '.join(sorted(dropped))})" if dropped else "")
                + "."
            )
        return {pid: round(v / total * 100, 4) for pid, v in held.items()}, note

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
    # Deliberately broad: riskfolio-lib internals raise bare KeyError /
    # NameError / IndexError on failure (see solvers.py's module docstring
    # and api/optimize.py's comments, e.g. "NameError: The limits of the
    # frontier can't be found"). Any of those escaping here would turn a
    # fully successful main solve into a 500, which is exactly what
    # compareNote exists to prevent.
    except Exception as exc:
        logger.exception("comparison solve failed: compare_against=%s", compare_against)
        return None, f"Comparison against {compare_against} could not be computed: {exc}"


def _resolve_display_name(proj_id: str, request: OptimizeRequest) -> str:
    """The benchmark fund's display name, preferring request.funds (already
    client-supplied, no I/O) and falling back to the same
    mvp_fund_universe.csv backend/app/api/funds.py reads for the fund
    picker -- a benchmark is not necessarily one of the optimized funds, so
    request.funds alone cannot always resolve it."""
    for fund in request.funds:
        if fund.proj_id == proj_id:
            return fund.display_name
    if _UNIVERSE_PATH.exists():
        universe = pd.read_csv(_UNIVERSE_PATH)
        match = universe.loc[universe["proj_id"] == proj_id, "display_name"]
        if not match.empty:
            return str(match.iloc[0])
    return proj_id


def build_benchmark_comparison(
    request: OptimizeRequest, optimal_weights: dict[str, float], returns: pd.DataFrame
) -> dict | None:
    """None when no benchmark was requested. Otherwise loads the
    benchmark's own return series (inputs.load_benchmark_returns --
    raises ValueError("BENCHMARK_DATA_UNAVAILABLE") on insufficient data,
    a hard error for the whole request per this project's decision, so
    that propagates uncaught here rather than being swallowed) and scores
    it against the optimized portfolio's realized return series via
    backend/app/engine/metrics.py's real functions."""
    benchmark_proj_id = request.benchmark_proj_id
    if not benchmark_proj_id:
        return None

    benchmark_returns = inputs.load_benchmark_returns(benchmark_proj_id, request)
    portfolio_returns = inputs.portfolio_return_series(returns, optimal_weights)
    ppy = inputs.periods_per_year(request)

    # Align ONCE, and score both metrics on the same sample. metrics.
    # tracking_error self-aligns (inner join + dropna) but metrics.
    # annualized_return does not -- it annualizes each series over its own
    # length. At daily/weekly frequency the two series can differ in length,
    # which would put an excess return measured over two different horizons
    # next to a tracking error measured on their intersection.
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    portfolio_returns, benchmark_returns = aligned.iloc[:, 0], aligned.iloc[:, 1]

    excess_return_pct = (
        metrics.annualized_return(portfolio_returns, ppy) - metrics.annualized_return(benchmark_returns, ppy)
    ) * 100
    tracking_error_pct = metrics.tracking_error(portfolio_returns, benchmark_returns, ppy) * 100

    return {
        "projId": benchmark_proj_id,
        "displayName": _resolve_display_name(benchmark_proj_id, request),
        "trackingErrorPct": round(tracking_error_pct, 2),
        "excessReturnPct": round(excess_return_pct, 2),
    }
