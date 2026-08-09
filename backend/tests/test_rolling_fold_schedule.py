from itertools import pairwise

import pandas as pd

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
