"""Monte Carlo resampling (Michaud-style) for robustOptimization.
Verified via live research against the real PortfolioVisualizer tool that
"Robust Optimization: Yes/No" uses resampling-based Monte Carlo, not
riskfolio-lib's own Worst-Case mean-variance model -- a different
technique. See
docs/superpowers/specs/2026-08-10-phase5-return-method-lookback-robust-design.md
for the full research/design rationale.

Applies ONLY to the main solve (per design decision) -- never the rolling
evaluator's per-fold solves, never the comparison portfolio's solve, and
never re-run inside holdings.enforce_max_holdings's trim loop (only its
initial solve).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer import inputs, solvers

RESAMPLE_COUNT = 500
MIN_SUCCESSFUL_FRACTION = 0.5

# Fixed seed, deliberately NOT derived from request contents: this project's
# reproducibility invariant ("every result is reproducible from the parquet
# cache alone") requires that the same request produces byte-identical
# weights on every call. A fresh default_rng() per call broke that.
RESAMPLE_SEED = 20260810


def resample_and_solve(
    request: OptimizeRequest, mu: pd.Series, sigma: pd.DataFrame, returns: pd.DataFrame
) -> tuple[dict[str, float], str | None]:
    """Bootstrap-resamples returns' rows (with replacement) RESAMPLE_COUNT
    times, recomputes mu/Sigma per resample via inputs.build_mu_sigma
    (same estimation logic, no new formula), solves via
    solvers.solve_for_goal, and averages the WEIGHTS of every
    successfully-solved resample -- Michaud resampling's defining step.

    A resample whose solve fails is skipped, not fatal. If fewer than
    RESAMPLE_COUNT * MIN_SUCCESSFUL_FRACTION resamples succeed, falls back
    to a single-shot solve on the ORIGINAL mu/sigma with an explanatory
    note -- never a hard error.

    Note: covariance_method="ewma" depends on chronological row order for
    its halflife weighting; bootstrap resampling scrambles that order, so
    EWMA combined with robust optimization produces a covariance estimate
    that no longer means "more recent observations weighted more heavily"
    within each resample. This is a known limitation, not a bug -- sample
    and shrinkage covariance (the common case) are unaffected since they
    don't depend on row order.
    """
    proj_ids = list(mu.index)
    n_obs = len(returns)
    rng = np.random.default_rng(RESAMPLE_SEED)

    successful_weights: list[dict[str, float]] = []
    for _ in range(RESAMPLE_COUNT):
        sample_idx = rng.integers(0, n_obs, size=n_obs)
        resampled_returns = returns.iloc[sample_idx].reset_index(drop=True)
        try:
            resampled_mu, resampled_sigma = inputs.build_mu_sigma(request, resampled_returns)
            weights = solvers.solve_for_goal(request, resampled_mu, resampled_sigma, resampled_returns)
        except (ValueError, RuntimeError):
            continue
        successful_weights.append(weights)

    required = int(RESAMPLE_COUNT * MIN_SUCCESSFUL_FRACTION)
    if len(successful_weights) < required:
        fallback_weights = solvers.solve_for_goal(request, mu, sigma, returns)
        note = (
            f"Robust optimization fell back to a single-shot solve: only "
            f"{len(successful_weights)} of {RESAMPLE_COUNT} resamples converged "
            f"(need at least {required})."
        )
        return fallback_weights, note

    total_runs = len(successful_weights)
    averaged = {pid: 0.0 for pid in proj_ids}
    for weights in successful_weights:
        for pid in proj_ids:
            averaged[pid] += weights.get(pid, 0.0)
    averaged = {pid: round(v / total_runs, 4) for pid, v in averaged.items()}
    # Per-fund rounding can leave the total a hair off 100; put the residual
    # back on the largest holding (rather than rescaling every fund, which
    # would need a second rounding pass and could drift again) so the
    # returned weights always sum to exactly 100.
    rounded_total = sum(averaged.values())
    if averaged and rounded_total > 0:
        largest = max(averaged, key=lambda pid: averaged[pid])
        averaged[largest] = round(averaged[largest] + (100.0 - rounded_total), 4)
    note = f"Robust optimization: averaged {total_runs} of {RESAMPLE_COUNT} resamples."
    return averaged, note
