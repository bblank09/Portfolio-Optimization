from itertools import pairwise

import pandas as pd
import pytest

from backend.app.optimizer.rolling import build_fold_schedule


def test_monthly_schedule_has_one_fold_per_month_after_the_first():
    # 6 distinct calendar months of daily data -> 5 folds (month 1 is
    # training-only, has no preceding period to be "out of sample" against).
    index = pd.date_range("2021-01-01", "2021-06-30", freq="D")
    folds = build_fold_schedule(index, "monthly")
    assert len(folds) == 5
    assert folds[0].period_label == "2021-02"


def test_expanding_window_train_end_grows_each_fold():
    index = pd.date_range("2021-01-01", "2021-06-30", freq="D")
    folds = build_fold_schedule(index, "monthly")
    train_ends = [f.train_end for f in folds]
    assert train_ends == sorted(train_ends)
    # Every train_end after the first is strictly later than the previous
    # fold's -- the window expands, it never resets or shrinks.
    assert all(later > earlier for earlier, later in pairwise(train_ends))


def test_test_window_covers_the_full_following_period():
    index = pd.date_range("2021-01-01", "2021-03-31", freq="D")
    folds = build_fold_schedule(index, "monthly")
    assert len(folds) == 2
    first_fold = folds[0]
    assert first_fold.test_start == pd.Timestamp("2021-02-01")
    assert first_fold.test_end == pd.Timestamp("2021-02-28")


def test_quarterly_frequency_groups_by_quarter():
    index = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    folds = build_fold_schedule(index, "quarterly")
    # 8 distinct quarters across 2020-2021 -> 7 folds.
    assert len(folds) == 7
    assert folds[0].period_label == "2020Q2"


def test_annual_frequency_groups_by_year():
    index = pd.date_range("2016-01-01", "2019-12-31", freq="D")
    folds = build_fold_schedule(index, "annually")
    assert len(folds) == 3
    assert folds[0].period_label == "2017"


def test_empty_index_produces_no_folds():
    assert build_fold_schedule(pd.DatetimeIndex([]), "monthly") == []


def test_single_calendar_period_produces_no_folds():
    index = pd.date_range("2021-01-01", "2021-01-31", freq="D")
    assert build_fold_schedule(index, "monthly") == []


def test_expanding_mode_leaves_train_start_none():
    index = pd.date_range("2021-01-01", "2021-06-30", freq="D")
    folds = build_fold_schedule(index, "monthly")  # mode defaults to "expanding"
    assert all(f.train_start is None for f in folds)


def test_trailing_mode_sets_a_fixed_length_train_start():
    # 8 months of daily data, monthly cadence, 2-month lookback.
    index = pd.date_range("2021-01-01", "2021-08-31", freq="D")
    folds = build_fold_schedule(index, "monthly", mode="trailing", lookback_months=2)
    assert len(folds) == 7  # 8 distinct months -> 7 folds, same count as expanding mode
    for fold in folds:
        assert fold.train_start is not None
    # Fold 0 (train_end = 2021-01-31) is excluded from the fixed-length
    # check below: a 2-month lookback from Jan 31 would need data starting
    # in November 2020, which doesn't exist, so fold 0's train_start
    # legitimately clamps to index.min() and its window is only 30 days.
    # That clamping behavior is exactly what
    # test_trailing_mode_train_start_is_clamped_to_available_history
    # verifies separately. Folds 1+ have enough prior history for the true
    # 2-month window, so only those are checked here -- this is the
    # concrete, discriminating assertion that would fail if trailing mode
    # silently fell back to expanding behavior.
    for fold in folds[1:]:
        window_days = (fold.train_end - fold.train_start).days
        assert 55 <= window_days <= 65


def test_trailing_mode_train_start_is_clamped_to_available_history():
    # Fold 0 (earliest) with a 2-month lookback on data that only goes back
    # to index[0] itself -- the trailing window cannot start before the
    # data actually begins, so train_start must clamp to index[0] rather
    # than requesting data that doesn't exist.
    index = pd.date_range("2021-01-01", "2021-08-31", freq="D")
    folds = build_fold_schedule(index, "monthly", mode="trailing", lookback_months=2)
    assert folds[0].train_start >= index.min()
    assert folds[0].train_start <= index.min() + pd.Timedelta(days=31)  # first fold's train_end is end of Feb; a 2-month lookback from there lands close to index[0] itself


def test_build_fold_schedule_rejects_trailing_mode_without_lookback_months():
    index = pd.date_range("2020-01-31", periods=12, freq="ME")
    with pytest.raises(ValueError, match="lookback_months is required when mode='trailing'"):
        build_fold_schedule(index, "monthly", mode="trailing")
