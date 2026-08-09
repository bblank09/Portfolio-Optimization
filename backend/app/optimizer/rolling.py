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

import pandas as pd

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
