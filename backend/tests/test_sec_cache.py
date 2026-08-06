import pandas as pd
import pytest

from backend.app.data import quality
from backend.app.data.quality import (
    align_nav_panel,
    compute_month_coverage,
    find_longest_complete_window,
    load_aligned_nav_returns,
    validate_nav_panel,
)
from backend.app.sec import cache as sec_cache


def test_find_longest_complete_window_skips_a_shared_gap():
    # Mirrors the real 2024-06 to 2024-11 SEC-wide incident: two funds each
    # individually span the whole range, but the outer intersection of
    # their nav_start/nav_end still contains a real gap. The longest
    # continuous fully-complete run is the pre-gap window here (5 months),
    # tied with the post-gap window (2) -- the earlier/longer one wins.
    index = pd.PeriodIndex(
        ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-11", "2024-12"], freq="M"
    ).to_timestamp(how="end").normalize()
    panel = pd.DataFrame({"A": [1.0] * 7, "B": [1.0] * 7}, index=index)

    window = find_longest_complete_window(panel)

    assert window == ("2024-01-31", "2024-05-31")


def test_find_longest_complete_window_excludes_periods_where_any_fund_is_missing():
    index = pd.PeriodIndex(["2024-01", "2024-02", "2024-03"], freq="M").to_timestamp(how="end").normalize()
    panel = pd.DataFrame({"A": [1.0, 1.0, 1.0], "B": [1.0, None, 1.0]}, index=index)

    window = find_longest_complete_window(panel)

    # Only single-month runs survive on either side of the missing B value.
    assert window in {("2024-01-31", "2024-01-31"), ("2024-03-31", "2024-03-31")}


def test_find_longest_complete_window_returns_none_when_nothing_overlaps():
    index = pd.PeriodIndex(["2024-01", "2024-02"], freq="M").to_timestamp(how="end").normalize()
    panel = pd.DataFrame({"A": [1.0, None], "B": [None, 1.0]}, index=index)

    assert find_longest_complete_window(panel) is None


def test_find_longest_complete_window_returns_none_for_empty_panel():
    assert find_longest_complete_window(pd.DataFrame()) is None


def test_compute_month_coverage_reports_full_coverage_for_consecutive_months():
    dates = pd.to_datetime(["2024-01-15", "2024-02-15", "2024-03-15"])

    coverage = compute_month_coverage(dates)

    assert coverage["nav_start"] == "2024-01-15"
    assert coverage["nav_end"] == "2024-03-15"
    assert coverage["nav_months"] == 3
    assert coverage["nav_span_months"] == 3
    assert coverage["nav_completeness"] == 1.0


def test_compute_month_coverage_flags_a_real_internal_gap():
    # A fund that reports daily for a few weeks at launch, then switches to
    # quarterly reporting, has a real long-term gap distinct from just being
    # a young fund -- span_months (calendar months from first to last
    # observation) stays large while nav_months (months actually observed)
    # stays small, so completeness catches it even though nav_start/nav_end
    # alone would look like a long, healthy history.
    dates = pd.to_datetime(["2022-10-05", "2022-10-06", "2022-12-30", "2026-06-30"])

    coverage = compute_month_coverage(dates)

    assert coverage["nav_months"] == 3
    assert coverage["nav_span_months"] == 45
    assert round(coverage["nav_completeness"], 2) == round(3 / 45, 2)


def test_compute_month_coverage_reports_no_gap_when_complete():
    dates = pd.to_datetime(["2024-01-15", "2024-02-15", "2024-03-15"])

    coverage = compute_month_coverage(dates)

    assert coverage["nav_gap_count"] == 0
    assert coverage["nav_largest_gap_start"] is None
    assert coverage["nav_largest_gap_end"] is None


def test_compute_month_coverage_reports_a_single_gap_precisely():
    # Mirrors the known SEC-wide 2024 incident: one continuous missing
    # window inside an otherwise complete history -- should be nameable as
    # exactly "2024-07 to 2024-10", not just a completeness percentage.
    dates = pd.to_datetime(["2024-05-15", "2024-06-15", "2024-11-15", "2024-12-15"])

    coverage = compute_month_coverage(dates)

    assert coverage["nav_gap_count"] == 1
    assert coverage["nav_largest_gap_start"] == "2024-07"
    assert coverage["nav_largest_gap_end"] == "2024-10"


def test_compute_month_coverage_reports_the_largest_of_several_gaps():
    # A quarterly reporter has many small gaps -- nav_gap_count should
    # reflect that there are several, and the "largest gap" fields should
    # point at the biggest one rather than an arbitrary one.
    dates = pd.to_datetime(["2022-10-05", "2022-10-06", "2022-12-30", "2023-06-30", "2026-06-30"])

    coverage = compute_month_coverage(dates)

    assert coverage["nav_gap_count"] == 3
    assert coverage["nav_largest_gap_start"] == "2023-07"
    assert coverage["nav_largest_gap_end"] == "2026-05"


def test_compute_month_coverage_handles_empty_input():
    coverage = compute_month_coverage(pd.to_datetime([]))

    assert coverage["nav_start"] is None
    assert coverage["nav_gap_count"] == 0
    assert coverage["nav_end"] is None
    assert coverage["nav_months"] == 0
    assert coverage["nav_span_months"] == 0
    assert coverage["nav_completeness"] == 0.0


def test_load_nav_panel_pushes_proj_id_filter_down_to_parquet_read(monkeypatch, tmp_path):
    # With the full SEC universe this file will be far too large to load
    # entirely into memory on every backtest request -- read_parquet must be
    # told which proj_ids to keep via `filters`, not asked for everything and
    # filtered in pandas afterward.
    captured = {}

    def fake_read_parquet(path, filters=None, **kwargs):
        captured["path"] = path
        captured["filters"] = filters
        return pd.DataFrame(
            {
                "proj_id": ["FUND_A", "FUND_A"],
                "nav_date": ["2024-01-31", "2024-02-29"],
                "nav_per_unit": [10.0, 11.0],
            }
        )

    monkeypatch.setattr(pd, "read_parquet", fake_read_parquet)

    sec_cache.load_nav_panel(["FUND_A", "FUND_B"])

    assert captured["filters"] == [("proj_id", "in", ["FUND_A", "FUND_B"])]


def test_migrate_schema_adds_missing_columns_with_defaults(monkeypatch, tmp_path):
    # Pulling the full SEC universe (checklist 8.8) needs new columns on
    # fund_classes (e.g. fund_status, cancel_date, for survivorship-bias
    # auditing) that the currently-committed cache doesn't have yet.
    monkeypatch.setattr(sec_cache, "NORMALIZED_DIR", tmp_path)
    sec_cache.write_parquet("fund_classes", [{"proj_id": "A", "display_name": "Fund A"}])

    added = sec_cache.migrate_schema("fund_classes", {"fund_status": "", "cancel_date": None})

    assert added == ["fund_status", "cancel_date"]
    migrated = pd.read_parquet(tmp_path / "fund_classes.parquet")
    assert migrated["fund_status"].tolist() == [""]
    assert migrated["cancel_date"].tolist() == [None]
    # Existing data must survive the migration untouched.
    assert migrated["proj_id"].tolist() == ["A"]
    assert migrated["display_name"].tolist() == ["Fund A"]


def test_migrate_schema_is_idempotent_and_never_overwrites_existing_values(monkeypatch, tmp_path):
    monkeypatch.setattr(sec_cache, "NORMALIZED_DIR", tmp_path)
    sec_cache.write_parquet("fund_classes", [{"proj_id": "A", "fund_status": "Registered"}])

    added = sec_cache.migrate_schema("fund_classes", {"fund_status": ""})

    assert added == []
    migrated = pd.read_parquet(tmp_path / "fund_classes.parquet")
    assert migrated["fund_status"].tolist() == ["Registered"]


def test_migrate_schema_raises_a_clear_error_for_an_unknown_dataset(monkeypatch, tmp_path):
    monkeypatch.setattr(sec_cache, "NORMALIZED_DIR", tmp_path)

    with pytest.raises(FileNotFoundError):
        sec_cache.migrate_schema("does_not_exist", {"col": None})


def test_align_nav_panel_monthly_last_value():
    panel = pd.DataFrame(
        {"FUND_A": [10.0, 11.0, 12.0], "FUND_B": [20.0, 22.0, 24.0]},
        index=pd.to_datetime(["2024-01-02", "2024-01-31", "2024-02-29"]),
    )
    aligned = align_nav_panel(panel, frequency="monthly")
    assert list(aligned.index.strftime("%Y-%m-%d")) == ["2024-01-31", "2024-02-29"]
    assert aligned.loc[pd.Timestamp("2024-01-31"), "FUND_A"] == 11.0


def test_align_nav_panel_weekly_last_value():
    panel = pd.DataFrame(
        {"FUND_A": [10.0, 11.0, 12.0]},
        index=pd.to_datetime(["2024-01-02", "2024-01-04", "2024-01-08"]),
    )
    aligned = align_nav_panel(panel, frequency="weekly")
    assert list(aligned.index.strftime("%Y-%m-%d")) == ["2024-01-05", "2024-01-08"]
    assert aligned.iloc[0]["FUND_A"] == 11.0


def test_align_nav_panel_caps_incomplete_month_to_latest_observation():
    panel = pd.DataFrame(
        {"FUND_A": [10.0, 11.0]},
        index=pd.to_datetime(["2024-07-01", "2024-07-24"]),
    )
    aligned = align_nav_panel(panel, frequency="monthly")
    assert list(aligned.index.strftime("%Y-%m-%d")) == ["2024-07-24"]
    assert aligned.iloc[0]["FUND_A"] == 11.0


def test_align_nav_panel_rejects_unknown_frequency():
    panel = pd.DataFrame({"FUND_A": [10.0]}, index=pd.to_datetime(["2024-01-02"]))
    with pytest.raises(ValueError, match="Unsupported NAV alignment frequency"):
        align_nav_panel(panel, frequency="hourly")


def test_validate_nav_panel_flags_missing_values():
    panel = pd.DataFrame({"FUND_A": [10.0, None]}, index=pd.to_datetime(["2024-01-31", "2024-02-29"]))
    issues = validate_nav_panel(panel, as_of=pd.Timestamp("2024-03-15"))
    assert any(issue["code"] == "missing_nav" for issue in issues)


def test_validate_nav_panel_flags_short_history():
    panel = pd.DataFrame({"FUND_A": [10.0, 11.0]}, index=pd.to_datetime(["2024-01-31", "2024-02-29"]))
    issues = validate_nav_panel(panel, min_complete_observations=3, as_of=pd.Timestamp("2024-03-15"))
    assert any(issue["code"] == "short_history" for issue in issues)


def test_validate_nav_panel_flags_stale_nav():
    panel = pd.DataFrame({"FUND_A": [10.0]}, index=pd.to_datetime(["2024-01-31"]))
    issues = validate_nav_panel(panel, stale_after_days=30, as_of=pd.Timestamp("2024-03-15"))
    assert any(issue["code"] == "stale_nav" for issue in issues)


def test_load_aligned_nav_returns_from_cached_sec_data():
    returns = load_aligned_nav_returns(["M0209_2548", "M0337_2550"], "2020-01-01", "2021-12-31")
    assert not returns.empty
    assert {"M0209_2548", "M0337_2550"}.issubset(set(returns.columns))


def test_load_aligned_nav_returns_does_not_forward_fill_missing_nav(monkeypatch):
    panel = pd.DataFrame(
        {"FUND_A": [10.0, None, 12.0]},
        index=pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-31"]),
    )
    monkeypatch.setattr(quality, "load_nav_panel", lambda proj_ids: panel)

    returns = load_aligned_nav_returns(["FUND_A"], "2024-01-01", "2024-03-31")

    assert returns.empty


def test_align_nav_panel_keeps_the_index_ordered_when_trailing_months_are_empty():
    # A record whose NAV is null creates a bucket with no observation. Capping
    # that bucket's month-end label down to the latest observed date would place
    # it before the preceding row, leaving a non-monotonic index that breaks
    # date-range slicing.
    panel = pd.DataFrame(
        {"FUND_A": [10.0, 11.0, None, None]},
        index=pd.to_datetime(["2024-01-31", "2024-02-15", "2024-02-29", "2024-03-31"]),
    )

    aligned = align_nav_panel(panel)

    assert aligned.index.is_monotonic_increasing
    assert not aligned.index.has_duplicates
    # The last label is capped to the latest observation, not left at 2024-03-31.
    assert aligned.index[-1] == pd.Timestamp("2024-02-15")
    assert aligned["FUND_A"].tolist() == [10.0, 11.0]


def test_align_nav_panel_still_caps_a_partial_final_month():
    panel = pd.DataFrame(
        {"FUND_A": [10.0, 11.0]},
        index=pd.to_datetime(["2024-01-31", "2024-02-15"]),
    )

    aligned = align_nav_panel(panel)

    assert [str(stamp.date()) for stamp in aligned.index] == ["2024-01-31", "2024-02-15"]


def test_min_complete_observations_scales_with_daily_frequency():
    from backend.app.api.backtests import min_complete_observations_for

    # 12 monthly observations is a ~1 year bar; the same "about a year" bar for
    # daily data is ~252 business days, not 12 calendar days.
    assert min_complete_observations_for("monthly") == 12
    assert min_complete_observations_for("daily") == 252
