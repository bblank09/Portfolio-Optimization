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
from backend.app.optimizer import constraints, holdings, inputs

_PERIOD_FREQ = {"monthly": "M", "quarterly": "Q", "annually": "Y"}

# A new floor, not reused from elsewhere -- no equivalent constant existed
# before this module (inputs.py only rejects an empty/all-NaN window, not a
# too-short-for-covariance one). 6 is the absolute minimum, NOT a
# fund-count-independent guarantee: a sample covariance matrix over N funds
# estimated from T observations is singular whenever T <= N, so 6
# observations are only adequate up to a handful of funds. The effective
# floor is therefore scaled with the fund count by
# min_train_observations() below; this constant is just its lower bound.
# Folds below the floor are dropped from the schedule before any solve is
# attempted -- see run_rolling_evaluation.
MIN_TRAIN_OBSERVATIONS = 6

# Volatility and Sharpe are undefined on fewer than two observations
# (metrics.annualized_volatility returns 0.0 and metrics.sharpe_ratio
# returns None below this), so a test window this thin cannot be scored
# honestly and its fold is skipped rather than reported with placeholder
# zeros.
MIN_TEST_OBSERVATIONS = 2


def min_train_observations(fund_count: int) -> int:
    """Minimum training rows a fold needs before a solve is attempted.

    ``2 * fund_count`` keeps the sample covariance matrix comfortably
    non-singular (it needs strictly more observations than assets merely to
    be full rank), with MIN_TRAIN_OBSERVATIONS as the floor for very small
    universes where 2N would be trivially small.
    """
    return max(MIN_TRAIN_OBSERVATIONS, 2 * fund_count)


@dataclass(frozen=True)
class FoldSpec:
    period_label: str
    train_start: pd.Timestamp | None
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def build_fold_schedule(
    index: pd.DatetimeIndex, frequency: str, mode: str = "expanding", lookback_months: int | None = None
) -> list[FoldSpec]:
    """Fold schedule keyed off calendar periods matching ``frequency``
    ("monthly"/"quarterly"/"annually", matching OptimizationFrequency's
    values). ``mode="expanding"`` (default, unchanged from this function's
    original behavior): every fold's training window starts at
    ``index[0]`` (``train_start`` stays ``None``, and the caller slices
    ``returns.loc[:fold.train_end]``, which is expanding because it always
    starts from the same beginning). ``mode="trailing"``: each fold's
    training window is a FIXED length of ``lookback_months`` months
    immediately preceding ``train_end``, sliding forward each fold instead
    of growing -- ``train_start`` is set to the first index row on or after
    ``train_end - lookback_months`` months, clamped to ``index.min()`` if
    the requested lookback would start before the data actually begins.

    Fold i (0-indexed) trains through the last row of calendar period i --
    so fold 0 trains on the first distinct period only -- and is tested on
    calendar period i+1 in full. One fewer fold than there are distinct
    calendar periods in ``index``, because the first period is
    training-only -- there is no preceding period for it to have been
    tested "out of sample" against. This fold COUNT and TEST-period
    behavior is identical in both modes; only each fold's training WINDOW
    start differs.
    """
    if mode == "trailing" and lookback_months is None:
        raise ValueError("lookback_months is required when mode='trailing'")
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
        train_end = train_rows.max()

        train_start = None
        if mode == "trailing" and lookback_months is not None:
            cutoff = train_end - pd.DateOffset(months=lookback_months)
            eligible = index[index >= cutoff]
            train_start = eligible.min() if len(eligible) > 0 else index.min()
            train_start = max(train_start, index.min())

        folds.append(
            FoldSpec(
                period_label=str(test_period),
                train_start=train_start,
                train_end=train_end,
                test_start=test_rows.min(),
                test_end=test_rows.max(),
            )
        )
    return folds


def run_rolling_evaluation(
    request: OptimizeRequest,
    returns: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
) -> tuple[list[dict], str | None]:
    """Walk-forward re-optimization: for each fold in the expanding-window
    schedule, re-solves the request's goal on the training slice via the
    exact same dispatch service.py's main solve uses
    (``solvers.solve_for_goal``), applies the result to the held-out test
    slice, and scores it via backend/app/engine/metrics.py. A fold whose
    solve raises, or whose test window is too thin to compute volatility
    and Sharpe on (fewer than MIN_TEST_OBSERVATIONS observations), is
    skipped and counted, never fatal to the whole request.

    Returns ``(folds, note)``. The note, when present, reports what actually
    happened by cause -- how many scheduled folds were dropped before any
    solve for insufficient training history, and how many were skipped
    during scoring -- rather than attributing every skip to one guessed
    cause.

    Raises ``ValueError("INSUFFICIENT_ROLLING_HISTORY")`` -- the bare
    ErrorCode name, same convention as inputs.py/solvers.py, resolved by
    api/optimize.py's existing dynamic lookup with no route change -- when
    fewer than 2 folds have enough training observations to even attempt a
    solve. This check runs before any solve is attempted; a fold failing
    *during* its solve is a different, non-fatal path (see above).
    """
    frequency = request.constraints.optimization_frequency.value
    # ``.value`` normally, but ``model_copy(update=...)`` (used by tests to
    # swap constraints without re-validating the whole request) assigns the
    # raw string as-is rather than re-parsing it into the StrEnum, so this
    # must tolerate a plain str here too.
    raw_mode = request.constraints.rolling_window_mode
    mode = raw_mode.value if hasattr(raw_mode, "value") else raw_mode
    lookback_months = request.constraints.lookback_period_months if mode == "trailing" else None
    schedule = build_fold_schedule(pd.DatetimeIndex(returns.index), frequency, mode=mode, lookback_months=lookback_months)
    train_floor = min_train_observations(len(request.funds))
    usable = [
        f
        for f in schedule
        if len(returns.loc[(f.train_start if f.train_start is not None else returns.index[0]) : f.train_end])
        >= train_floor
    ]
    dropped_by_training_floor = len(schedule) - len(usable)
    if len(usable) < 2:
        raise ValueError("INSUFFICIENT_ROLLING_HISTORY")

    proj_ids = [fund.proj_id for fund in request.funds]
    ppy = inputs.periods_per_year(request)
    risk_free_fraction = request.constraints.risk_free_rate_pct / 100

    folds: list[dict] = []
    skipped = 0
    for fold in usable:
        train_start = fold.train_start if fold.train_start is not None else returns.index[0]
        train_returns = returns.loc[train_start : fold.train_end]
        test_returns = returns.loc[fold.test_start : fold.test_end]
        # Cheap pre-check: a test window this thin can never be scored (see
        # the post-alignment check below), so skip before paying for a solve
        # whose result would be thrown away.
        if len(test_returns) < MIN_TEST_OBSERVATIONS:
            skipped += 1
            continue
        try:
            mu, sigma = inputs.build_mu_sigma(request, train_returns)
            weights = holdings.enforce_max_holdings(request, mu, sigma, train_returns)[0]
            train_benchmark = None
            if request.constraints.max_tracking_error_pct is not None:
                if benchmark_returns is None:
                    raise ValueError("BENCHMARK_DATA_UNAVAILABLE")
                train_benchmark = benchmark_returns.loc[train_start:fold.train_end]
            weights = constraints.enforce_portfolio_constraints(
                request, weights, train_returns, train_benchmark
            )
            # Inside the try so a column-selection KeyError is counted as a
            # skipped fold like any other per-fold failure, rather than
            # escaping as an unhandled error.
            period_returns = inputs.portfolio_return_series(test_returns, weights, proj_ids)
        except (KeyError, ValueError, RuntimeError):
            skipped += 1
            continue

        # Volatility and Sharpe are undefined below two observations, and
        # metrics.py signals that with 0.0 / None -- neither of which may be
        # reported as if it were a measurement. Skip the fold instead. This
        # is what makes e.g. monthly data at a monthly cadence (one
        # observation per test window by construction) report nothing rather
        # than a column of fabricated zeros.
        if len(period_returns) < MIN_TEST_OBSERVATIONS:
            skipped += 1
            continue

        sharpe = metrics.sharpe_ratio(period_returns, risk_free_fraction, ppy)
        if sharpe is None:
            skipped += 1
            continue

        # The fold's OWN test-period compounded return, not annualized --
        # comparable to a single bar in a rolling chart, not to CAGR.
        # Annualizing it (as an earlier revision did) turned a single
        # quarter's move into a (1+r)^4 figure that is neither comparable
        # across folds of differing length nor compoundable fold-to-fold in
        # a growth-of-100 style chart.
        period_return = float(np.prod(1.0 + period_returns.to_numpy(dtype=float))) - 1.0
        folds.append(
            {
                "periodLabel": fold.period_label,
                "realizedReturnPct": round(period_return * 100, 2),
                "realizedVolatilityPct": round(metrics.annualized_volatility(period_returns, ppy) * 100, 2),
                "realizedSharpe": round(sharpe, 2),
            }
        )

    note = None
    if dropped_by_training_floor > 0 or skipped > 0:
        note = (
            f"Rolling validation: {len(folds)} of {len(schedule)} scheduled folds produced a "
            f"result ({dropped_by_training_floor} folds dropped for insufficient training "
            f"history, {skipped} skipped during scoring)."
        )
    return folds, note
