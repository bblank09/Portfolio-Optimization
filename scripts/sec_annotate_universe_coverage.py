"""Annotate data/sec/mvp_fund_universe.csv with each fund's real NAV
coverage (nav_start, nav_end, nav_months, nav_span_months,
nav_completeness), computed from the cached daily_nav.parquet.

Why: "Backtest cannot calculate with incomplete NAV periods" (raised by
backend/app/engine/backtest.py) is correct, expected behavior -- some
funds are simply young, some report NAV quarterly/semi-annually rather
than daily/monthly after an initial launch window, and none of that is
fabricable. But users had no way to see a fund's actual usable range
*before* filling in the whole form and hitting the error. This script
makes that real, already-known information queryable via /api/funds
(which just returns whatever is in this CSV) without any other backend
change.

Run after any NAV refresh (scripts/sec_download_mvp.py,
scripts/sec_repair_failed_requests.py, scripts/sec_dedupe_fund_classes.py)
so the annotated columns stay in sync with the actual cache.

Usage:
    python -m scripts.sec_annotate_universe_coverage
"""

import pandas as pd

from backend.app.data.quality import compute_month_coverage
from backend.app.sec.cache import NORMALIZED_DIR


def main():
    universe = pd.read_csv("data/sec/mvp_fund_universe.csv")
    nav = pd.read_parquet(NORMALIZED_DIR / "daily_nav.parquet", columns=["proj_id", "nav_date"])
    nav["nav_date"] = pd.to_datetime(nav["nav_date"])

    coverage_rows = [
        {"proj_id": proj_id, **compute_month_coverage(group["nav_date"])} for proj_id, group in nav.groupby("proj_id")
    ]
    coverage = pd.DataFrame(coverage_rows)

    coverage_columns = ["nav_start", "nav_end", "nav_months", "nav_span_months", "nav_completeness"]
    universe = universe.drop(columns=[c for c in coverage_columns if c in universe.columns])
    universe = universe.merge(coverage, on="proj_id", how="left")

    universe.to_csv("data/sec/mvp_fund_universe.csv", index=False)

    missing = universe[universe["nav_start"].isna()]
    low_completeness = universe[universe["nav_completeness"] < 0.9]
    print(
        {
            "funds_annotated": len(universe),
            "funds_with_no_nav_at_all": len(missing),
            "funds_below_90pct_month_completeness": len(low_completeness),
        }
    )


if __name__ == "__main__":
    main()
