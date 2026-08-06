from datetime import date

import pandas as pd

from backend.app.sec.cache import load_nav_panel


def align_nav_panel(panel: pd.DataFrame, frequency: str = "monthly") -> pd.DataFrame:
    sorted_panel = panel.sort_index()
    if frequency == "monthly":
        return cap_incomplete_period_label(sorted_panel.resample("ME").last(), sorted_panel)
    if frequency == "weekly":
        return cap_incomplete_period_label(sorted_panel.resample("W-FRI").last(), sorted_panel)
    if frequency == "daily":
        return sorted_panel.dropna(how="all")
    raise ValueError(f"Unsupported NAV alignment frequency: {frequency}")


def cap_incomplete_period_label(aligned: pd.DataFrame, source_panel: pd.DataFrame) -> pd.DataFrame:
    if aligned.empty or source_panel.empty:
        return aligned
    latest_source_date = source_panel.dropna(how="all").index.max()
    if pd.isna(latest_source_date):
        return aligned

    # Buckets beyond the one holding the latest observation contain nothing at
    # all (a record can exist with a null NAV). Drop them before capping:
    # relabelling such a bucket to the latest observed date would move it behind
    # the preceding row and leave the index non-monotonic, which silently breaks
    # date-range slicing.
    boundary = aligned.index[aligned.index >= latest_source_date]
    if len(boundary):
        aligned = aligned.loc[:boundary[0]]

    if aligned.empty or aligned.index[-1] <= latest_source_date:
        return aligned
    capped = aligned.copy()
    index_values = list(capped.index)
    index_values[-1] = latest_source_date
    capped.index = pd.DatetimeIndex(index_values)
    return capped


def compute_month_coverage(dates: pd.DatetimeIndex | pd.Series) -> dict[str, object]:
    """Summarize how completely a fund's NAV history covers its own span.

    nav_start/nav_end alone can look like a long, healthy history for a
    fund that only reports NAV a few times a year (e.g. daily for a few
    weeks at launch, then quarterly forever after) -- span_months (calendar
    months from first to last observation) stays large while nav_months
    (months actually observed) stays small, so nav_completeness catches
    that case even when the date range alone would not.
    """
    dates = pd.DatetimeIndex(pd.to_datetime(dates)).dropna()
    if dates.empty:
        return {
            "nav_start": None,
            "nav_end": None,
            "nav_months": 0,
            "nav_span_months": 0,
            "nav_completeness": 0.0,
            "nav_gap_count": 0,
            "nav_largest_gap_start": None,
            "nav_largest_gap_end": None,
        }
    start = dates.min()
    end = dates.max()
    observed_periods = dates.to_period("M")
    nav_months = observed_periods.nunique()
    span_months = (end.year - start.year) * 12 + (end.month - start.month) + 1

    expected_periods = pd.period_range(start.to_period("M"), end.to_period("M"), freq="M")
    missing_periods = expected_periods.difference(pd.PeriodIndex(observed_periods.unique()))

    # Group consecutive missing months into gap segments (e.g. 2024-07,
    # 2024-08, 2024-09, 2024-10 -> one segment "2024-07 to 2024-10") so a
    # single real incident reads as one gap, not four.
    gap_segments: list[tuple[pd.Period, pd.Period]] = []
    for period in sorted(missing_periods):
        if gap_segments and period == gap_segments[-1][1] + 1:
            gap_segments[-1] = (gap_segments[-1][0], period)
        else:
            gap_segments.append((period, period))

    largest_gap = max(gap_segments, key=lambda segment: segment[1].ordinal - segment[0].ordinal) if gap_segments else None

    return {
        "nav_start": str(start.date()),
        "nav_end": str(end.date()),
        "nav_months": int(nav_months),
        "nav_span_months": int(span_months),
        "nav_completeness": nav_months / span_months if span_months else 0.0,
        "nav_gap_count": len(gap_segments),
        "nav_largest_gap_start": str(largest_gap[0]) if largest_gap else None,
        "nav_largest_gap_end": str(largest_gap[1]) if largest_gap else None,
    }


def find_longest_complete_window(panel: pd.DataFrame, freq: str = "M") -> tuple[str, str] | None:
    """Find the longest run of *consecutive* periods where every column in
    `panel` has a value, given an already-aligned (e.g. align_nav_panel)
    panel.

    A naive "latest nav_start .. earliest nav_end" intersection of several
    funds' individual ranges can still contain a gap belonging to any one
    of them (e.g. the 2024-06 to 2024-11 SEC-wide incident, or a quarterly
    reporter's internal gaps) -- backend/app/engine/backtest.py rejects any
    such gap inside the requested range, so a caller (e.g. the frontend's
    "Max" date-range preset) needs the actual longest gap-free window, not
    just the outer bounds, to reliably avoid INSUFFICIENT_NAV_HISTORY.
    """
    if panel.empty or panel.shape[1] == 0:
        return None
    complete = panel.dropna(how="any")
    if complete.empty:
        return None

    periods = pd.PeriodIndex(complete.index, freq=freq)
    best_start_idx = best_end_idx = None
    best_len = 0
    run_start = 0
    for i in range(1, len(periods) + 1):
        boundary = i == len(periods) or periods[i] != periods[i - 1] + 1
        if not boundary:
            continue
        run_len = i - run_start
        if run_len > best_len:
            best_len = run_len
            best_start_idx, best_end_idx = run_start, i - 1
        run_start = i

    if best_start_idx is None:
        return None
    return (str(pd.Timestamp(complete.index[best_start_idx]).date()), str(pd.Timestamp(complete.index[best_end_idx]).date()))


def validate_nav_panel(
    panel: pd.DataFrame,
    *,
    min_complete_observations: int = 12,
    stale_after_days: int = 45,
    as_of: date | pd.Timestamp | None = None,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if panel.empty:
        return [
            {
                "code": "empty_nav_panel",
                "message": "No NAV records available for the selected funds/date range.",
                "severity": "error",
            }
        ]

    sorted_panel = panel.sort_index()
    if sorted_panel.isna().any().any():
        missing_columns = sorted_panel.columns[sorted_panel.isna().any()].tolist()
        issues.append(
            {
                "code": "missing_nav",
                "message": f"Some funds have missing NAV values after alignment: {missing_columns}.",
                "severity": "warning",
            }
        )

    complete = sorted_panel.dropna(how="any")
    if len(complete) < min_complete_observations:
        issues.append(
            {
                "code": "short_history",
                "message": f"Only {len(complete)} complete observations are available; expected at least {min_complete_observations}.",
                "severity": "warning",
            }
        )

    if (sorted_panel <= 0).any().any():
        issues.append(
            {
                "code": "non_positive_nav",
                "message": "NAV contains zero or negative values.",
                "severity": "error",
            }
        )

    reference_date = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.today().normalize()
    last_observed = sorted_panel.apply(lambda col: col.dropna().index.max())
    stale_columns = [
        column
        for column, last_date in last_observed.items()
        if pd.notna(last_date) and (reference_date - pd.Timestamp(last_date)).days > stale_after_days
    ]
    if stale_columns:
        issues.append(
            {
                "code": "stale_nav",
                "message": f"Some funds have stale latest NAV observations: {stale_columns}.",
                "severity": "warning",
            }
        )

    return issues


def load_aligned_nav_returns(
    proj_ids: list[str],
    start_date: str | date,
    end_date: str | date,
    frequency: str = "monthly",
) -> pd.DataFrame:
    panel = load_nav_panel(proj_ids)
    filtered = panel.loc[pd.Timestamp(start_date) : pd.Timestamp(end_date)]
    aligned = align_nav_panel(filtered, frequency=frequency)
    return aligned.pct_change(fill_method=None).dropna(how="all")
