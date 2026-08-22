"""Fetch each Registered fund's latest reported net_asset (AUM) and its AUM
~1 year ago, so funds can be ranked by size + net-inflow growth within each
policy category before selecting the universe (see select_universe() in
scripts/sec_build_mvp_universe.py).

Cheap relative to a full NAV-history pull: two narrow windows per fund
(recent + ~1-year-ago, page_size=100 each), not full history -- roughly
~9,800 lightweight requests rather than the ~100,000+ a full backfill of
every fund would take.

net_asset is the fund's total net asset value in baht (confirmed against
the real API: K-SET50 reports net_asset ~6.47 billion baht per date), i.e.
real AUM, not a per-unit figure. SEC's fund API has no trading-volume field
-- open-end mutual funds have no secondary market, so there is nothing
resembling stock trading volume to report. AUM growth rate (change in
net_asset beyond what NAV appreciation alone explains) is the closest
available proxy for net subscription activity / "popularity."

Usage:
    python -m scripts.sec_fetch_fund_aum
"""

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from backend.app.sec.client import SecOpenDataClient
from backend.app.sec.normalizers import records
from scripts.sec_build_mvp_universe import fetch_all_registered_candidates
from scripts.sec_download_mvp import PAGE_SIZE, fetch_with_retry

LOOKBACK_WINDOW_DAYS = 45  # generous enough to catch at least one observation even for quarterly reporters
GROWTH_BASELINE_DAYS_AGO = 365


def net_asset_in_window(
    client: SecOpenDataClient, proj_id: str, expected_fund_class_name: str, start_date_iso: str, end_date_iso: str, *, pick: str
) -> tuple[float, str] | None:
    """Return (net_asset, nav_date) for the earliest ("min") or latest
    ("max") observation of the fund's own designated class within a single
    narrow window. A single page_size=100 request only reliably captures
    every observation in the window if the window is narrow enough that a
    daily reporter can't exceed 100 rows in it -- 45 days is safely under
    that for any real reporting frequency this project has seen.
    """
    params = {
        "proj_id": proj_id,
        "start_nav_date": start_date_iso,
        "end_nav_date": end_date_iso,
        "page_size": PAGE_SIZE,
    }
    classification, payload, _status_code, _error = fetch_with_retry(client=client, params=params)
    if classification != "success":
        return None
    candidates = [r for r in records(payload) if r.get("fund_class_name") == expected_fund_class_name]
    if not candidates:
        candidates = records(payload)
    if not candidates:
        return None
    key = (lambda r: r.get("nav_date") or "") if pick == "max" else (lambda r: r.get("nav_date") or "9999-99-99")
    chosen = (max if pick == "max" else min)(candidates, key=key)
    net_asset = chosen.get("net_asset")
    nav_date = chosen.get("nav_date")
    try:
        return (float(net_asset), nav_date) if net_asset is not None and nav_date else None
    except (TypeError, ValueError):
        return None


def main() -> None:
    client = SecOpenDataClient()
    candidates = fetch_all_registered_candidates(client)
    print(json.dumps({"candidate_count": len(candidates)}))

    today = datetime.now(UTC).date()
    recent_end = today
    recent_start = today - timedelta(days=LOOKBACK_WINDOW_DAYS)
    baseline_center = today - timedelta(days=GROWTH_BASELINE_DAYS_AGO)
    baseline_start = baseline_center - timedelta(days=LOOKBACK_WINDOW_DAYS // 2)
    baseline_end = baseline_center + timedelta(days=LOOKBACK_WINDOW_DAYS // 2)

    rows = []
    for index, candidate in enumerate(candidates):
        proj_id = candidate["proj_id"]
        fund_class_name = candidate["fund_class_name"]

        recent = net_asset_in_window(client, proj_id, fund_class_name, recent_start.isoformat(), recent_end.isoformat(), pick="max")
        baseline = net_asset_in_window(client, proj_id, fund_class_name, baseline_start.isoformat(), baseline_end.isoformat(), pick="min")

        aum = recent[0] if recent else None
        aum_year_ago = baseline[0] if baseline else None
        growth = (aum / aum_year_ago - 1) if aum is not None and aum_year_ago not in (None, 0) else None

        rows.append(
            {
                "proj_id": proj_id,
                "fund_class_name": fund_class_name,
                "display_name": candidate["display_name"],
                "policy_desc": candidate["policy_desc"],
                "aum": aum,
                "aum_as_of": recent[1] if recent else None,
                "aum_year_ago": aum_year_ago,
                "aum_year_ago_as_of": baseline[1] if baseline else None,
                "aum_growth_rate": growth,
            }
        )
        if (index + 1) % 200 == 0:
            print(json.dumps({"progress": index + 1, "total": len(candidates)}))

    out_path = Path("data/sec/fund_aum.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["proj_id", "fund_class_name", "display_name", "policy_desc", "aum", "aum_as_of", "aum_year_ago", "aum_year_ago_as_of", "aum_growth_rate"],
        )
        writer.writeheader()
        writer.writerows(rows)

    aum_resolved = sum(1 for row in rows if row["aum"] is not None)
    growth_resolved = sum(1 for row in rows if row["aum_growth_rate"] is not None)
    print(json.dumps({"rows_written": len(rows), "aum_resolved": aum_resolved, "growth_resolved": growth_resolved, "path": str(out_path)}))

    write_aggregated_by_proj_id(out_path)


def write_aggregated_by_proj_id(per_class_path: Path) -> Path:
    """net_asset is reported per share class, not per fund (confirmed
    against the real API: two classes of the same proj_id on the same date
    can report wildly different net_asset, including 0 for an unused
    class) -- a fund's real total AUM is the sum of its classes' assets.
    Ranking on the raw per-class rows would let one popular fund's several
    classes crowd out other funds entirely, and a tiny near-zero class can
    produce nonsensical growth-rate outliers (division by ~0). Aggregating
    to one row per proj_id before ranking fixes both.
    """
    df = pd.read_csv(per_class_path)
    agg = df.groupby("proj_id").agg(
        display_name=("display_name", "first"),
        policy_desc=("policy_desc", "first"),
        aum=("aum", "sum"),
        aum_year_ago=("aum_year_ago", "sum"),
        class_count=("fund_class_name", "count"),
    )
    agg["aum_growth_rate"] = (agg["aum"] / agg["aum_year_ago"] - 1).where(agg["aum_year_ago"] > 0)
    agg = agg[agg["aum"].notna() & (agg["aum"] > 0)].reset_index()

    out_path = Path("data/sec/fund_aum_by_proj_id.csv")
    agg.to_csv(out_path, index=False)
    print(json.dumps({"unique_funds_ranked": len(agg), "path": str(out_path)}))
    return out_path


if __name__ == "__main__":
    main()
