"""Walk-forward rolling out-of-sample evaluation: re-solves the request's
goal on an expanding training window per calendar period, scores the
result on the following held-out period via backend/app/engine/metrics.py.

Deviation from the spec's date math is none -- expanding window, fold
boundaries keyed to calendar periods matching the request's
optimization_frequency, exactly as
docs/superpowers/specs/2026-08-09-phase5-rolling-evaluator-design.md
describes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.engine import metrics
from backend.app.optimizer import inputs, solvers

_PERIOD_FREQ = {"monthly": "M", "quarterly": "Q", "annually": "Y"}

# A new floor, not reused from elsewhere -- no equivalent constant existed
# before this module (inputs.py only rejects an empty/all-NaN window, not a
# too-short-for-covariance one). 6 is a fixed floor, not scaled to fund
# count: this project's own fund-universe finding
# (docs/optimization-assumptions.md) says a usable shortlist is small (a
# handful of funds, not dozens), so a fixed floor comfortably covers a
# 2x2 up to a small double-digit covariance matrix without needing to read
# the fund count to set it. Folds below this floor are dropped from the
# schedule before any solve is attempted -- see run_rolling_evaluation.
MIN_TRAIN_OBSERVATIONS = 6


@dataclass(frozen=True)
class FoldSpec:
    period_label: str
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def build_fold_schedule(index: pd.DatetimeIndex, frequency: str) -> list[FoldSpec]:
    """Expanding-window fold schedule keyed off calendar periods matching
    ``frequency`` ("monthly"/"quarterly"/"annually", matching
    OptimizationFrequency's values). Every fold's training window starts at
    ``index[0]`` (the caller slices ``returns.loc[:fold.train_end]``, which
    is expanding because it always starts from the same beginning); fold
    i's training window ends at the last row of calendar period i+1 (0
    indexed: the second distinct period present), and its test window is
    calendar period i+2 in full. One fewer fold than there are distinct
    calendar periods in ``index``, because the first period is
    training-only -- there is no preceding period for it to have been
    tested "out of sample" against.
    """
    if len(index) == 0:
        return []
    periods = pd.PeriodIndex(index, freq=_PERIOD_FREQ[frequency])
    boundaries = sorted(set(periods))
    folds: list[FoldSpec] = []
    for i in range(len(boundaries) - 1):
        train_period = boundaries[i]
        test_period = boundaries[i + 1]
        train_rows = index[periods == train_period]
        test_rows = index[periods == test_period]
        folds.append(
            FoldSpec(
                period_label=str(test_period),
                train_end=train_rows.max(),
                test_start=test_rows.min(),
                test_end=test_rows.max(),
            )
        )
    return folds


def run_rolling_evaluation(
    request: OptimizeRequest, returns: pd.DataFrame
) -> tuple[list[dict], str | None]:
    """Walk-forward re-optimization: for each fold in the expanding-window
    schedule, re-solves the request's goal on the training slice via the
    exact same dispatch service.py's main solve uses
    (``solvers.solve_for_goal``), applies the result to the held-out test
    slice, and scores it via backend/app/engine/metrics.py. A fold whose
    solve raises is skipped and counted, never fatal to the whole request.

    Raises ``ValueError("INSUFFICIENT_ROLLING_HISTORY")`` -- the bare
    ErrorCode name, same convention as inputs.py/solvers.py, resolved by
    api/optimize.py's existing dynamic lookup with no route change -- when
    fewer than 2 folds have enough training observations to even attempt a
    solve. This check runs before any solve is attempted; a fold failing
    *during* its solve is a different, non-fatal path (see above).
    """
    frequency = request.constraints.optimization_frequency.value
    schedule = build_fold_schedule(returns.index, frequency)
    usable = [f for f in schedule if len(returns.loc[: f.train_end]) >= MIN_TRAIN_OBSERVATIONS]
    if len(usable) < 2:
        raise ValueError("INSUFFICIENT_ROLLING_HISTORY")

    proj_ids = [fund.proj_id for fund in request.funds]
    ppy = inputs.periods_per_year(request)
    risk_free_fraction = request.constraints.risk_free_rate_pct / 100

    folds: list[dict] = []
    failed = 0
    for fold in usable:
        train_returns = returns.loc[: fold.train_end]
        test_returns = returns.loc[fold.test_start : fold.test_end]
        if test_returns.empty:
            failed += 1
            continue
        try:
            mu, sigma = inputs.build_mu_sigma(request, train_returns)
            weights = solvers.solve_for_goal(request, mu, sigma, train_returns)
        except (ValueError, RuntimeError):
            failed += 1
            continue

        aligned = np.array([weights.get(proj_id, 0.0) / 100 for proj_id in proj_ids])
        period_returns = (test_returns[proj_ids] @ aligned).dropna()
        if period_returns.empty:
            failed += 1
            continue

        sharpe = metrics.sharpe_ratio(period_returns, risk_free_fraction, ppy)
        folds.append(
            {
                "periodLabel": fold.period_label,
                "realizedReturnPct": round(metrics.annualized_return(period_returns, ppy) * 100, 2),
                "realizedVolatilityPct": round(metrics.annualized_volatility(period_returns, ppy) * 100, 2),
                "realizedSharpe": round(sharpe, 2) if sharpe is not None else 0.0,
            }
        )

    note = None
    if failed > 0:
        note = (
            f"Rolling validation: {len(folds)} of {len(usable)} folds converged; "
            f"{failed} skipped due to solver non-convergence on thin training windows."
        )
    return folds, note
