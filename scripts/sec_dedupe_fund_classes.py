"""Retroactively filter daily_nav.parquet down to one share class per
proj_id, matching data/sec/mvp_fund_universe.csv's choice where possible.

SEC's daily-info/nav endpoint returns every share class registered under a
proj_id, not just the one the universe build picked. This was fixed at the
source in scripts/sec_download_mvp.py (see normalize_page_records's
expected_fund_class_name filter), but a full-universe pull already
downloaded before that fix has mixed-class rows already on disk -- this
script cleans an existing cache without re-downloading anything.

For ~3.6% of the 800-fund universe (29 funds, as of the first full pull),
SEC's fund-profiles endpoint (used to build the universe) and its
daily-info/nav endpoint (used to download NAV) disagree on the class-name
string for what is presumably the same underlying share class -- e.g. the
universe says "K-SELECT-A(A)" but the NAV endpoint only ever returns
"K-SELECT-A(D)" and "main" for that proj_id. Rather than silently dropping
100% of that fund's data (which would leave a zero-data ghost entry in the
universe that crashes on selection), resolve_class_to_keep() falls back to
whichever class has the most rows -- the closest available approximation
to "the fund's primary series" -- and this script updates the universe CSV
so subsequent downloads use the corrected label directly.

Usage:
    python -m scripts.sec_dedupe_fund_classes
"""

import json

import pandas as pd

from backend.app.sec.cache import NORMALIZED_DIR, write_manifest, write_parquet


def resolve_class_to_keep(fund_class_names: pd.Series, expected_class: str | float) -> str:
    """Pick which single share class's rows to keep for one proj_id.

    Prefers the universe's designated class when it actually appears in
    the downloaded data; otherwise falls back to whichever class has the
    most rows, since SEC's two endpoints occasionally disagree on the
    exact class-name string for the same underlying series.
    """
    if isinstance(expected_class, str) and expected_class in set(fund_class_names):
        return expected_class
    return fund_class_names.value_counts().idxmax()


def main():
    universe = pd.read_csv("data/sec/mvp_fund_universe.csv")
    expected_class_by_proj_id = dict(zip(universe["proj_id"], universe["fund_class_name"], strict=True))

    nav = pd.read_parquet(NORMALIZED_DIR / "daily_nav.parquet")
    before_rows = len(nav)
    before_dupes = int(nav.duplicated(subset=["nav_date", "proj_id"]).sum())
    before_proj_ids = set(nav["proj_id"].unique())

    resolved_class_by_proj_id: dict[str, str] = {}
    fallback_corrections: dict[str, str] = {}
    for proj_id, group in nav.groupby("proj_id"):
        expected = expected_class_by_proj_id.get(proj_id)
        resolved = resolve_class_to_keep(group["fund_class_name"], expected)
        resolved_class_by_proj_id[proj_id] = resolved
        if resolved != expected:
            fallback_corrections[proj_id] = resolved

    keep_mask = nav.apply(lambda row: row["fund_class_name"] == resolved_class_by_proj_id[row["proj_id"]], axis=1)
    cleaned = nav[keep_mask]

    after_rows = len(cleaned)
    after_dupes = int(cleaned.duplicated(subset=["nav_date", "proj_id"]).sum())
    after_proj_ids = set(cleaned["proj_id"].unique())

    write_parquet("daily_nav", cleaned.to_dict(orient="records"))

    manifest_path = NORMALIZED_DIR / "sec_data_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["nav_rows"] = after_rows
        write_manifest(manifest)

    if fallback_corrections:
        universe["fund_class_name"] = universe.apply(
            lambda row: fallback_corrections.get(row["proj_id"], row["fund_class_name"]), axis=1
        )
        universe.to_csv("data/sec/mvp_fund_universe.csv", index=False)

    print(
        {
            "rows_before": before_rows,
            "rows_after": after_rows,
            "rows_dropped": before_rows - after_rows,
            "duplicate_date_proj_id_before": before_dupes,
            "duplicate_date_proj_id_after": after_dupes,
            "proj_ids_before": len(before_proj_ids),
            "proj_ids_after": len(after_proj_ids),
            "proj_ids_lost": sorted(before_proj_ids - after_proj_ids),
            "fallback_class_corrections": fallback_corrections,
        }
    )


if __name__ == "__main__":
    main()
