"""Targeted repair for a small number of failed requests from the last
scripts/sec_download_mvp.py run, without re-running the entire pull.

Reads data/sec/normalized/sec_data_manifest.json + nav_request_ledger.parquet
to find every request whose status is a "blocking" one, resumes exactly
those (proj_id, page_no) pairs -- using the next_cursor already saved in
that page's predecessor raw JSON file when page_no > 1, so pagination state
isn't lost -- and continues fetching any further pages that failed request
never got to. Merges recovered rows into the existing parquet cache and
rewrites the manifest.

Usage:
    python scripts/sec_repair_failed_requests.py
"""

import json
import time
from pathlib import Path

import pandas as pd

from backend.app.sec.cache import NORMALIZED_DIR, write_manifest, write_parquet
from backend.app.sec.client import SecOpenDataClient
from backend.app.sec.endpoints import FUND_DAILY_NAV
from scripts.sec_download_mvp import (
    BASE_SLEEP_SECONDS,
    BLOCKING_STATUSES,
    PAGE_SIZE,
    fetch_with_retry,
    normalize_page_records,
    raw_file_for,
)


def main():
    manifest_path = NORMALIZED_DIR / "sec_data_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_dir = Path(manifest["raw_dir"])
    end_date = manifest["end"]
    start_date = manifest["start"]

    universe = pd.read_csv("data/sec/mvp_fund_universe.csv")
    expected_class_by_proj_id = dict(zip(universe["proj_id"], universe["fund_class_name"], strict=True))

    ledger = pd.read_parquet(NORMALIZED_DIR / "nav_request_ledger.parquet")
    failed = ledger[ledger["status"].isin(BLOCKING_STATUSES)]
    if failed.empty:
        print("No blocking ledger entries found -- nothing to repair.")
        return

    failed_keys = {(row.proj_id, int(row.page_no)) for row in failed.itertuples()}
    print(f"Repairing {len(failed_keys)} failed request(s) across {failed['proj_id'].nunique()} fund(s).")

    client = SecOpenDataClient()
    recovered_rows: list[dict] = []
    recovered_issues: list[dict] = []
    new_ledger_rows: list[dict] = []

    for proj_id, group in failed.groupby("proj_id"):
        expected_fund_class_name = expected_class_by_proj_id.get(proj_id) or None
        start_page = int(group["page_no"].min())
        cursor = ""
        if start_page > 1:
            prior_payload = json.loads(raw_file_for(raw_dir, proj_id, start_page - 1).read_text(encoding="utf-8"))
            cursor = prior_payload.get("next_cursor") or ""

        page_no = start_page - 1
        while True:
            page_no += 1
            params = {
                "proj_id": proj_id,
                "start_nav_date": start_date,
                "end_nav_date": end_date,
                "page_size": PAGE_SIZE,
            }
            if cursor:
                params["next_cursor"] = cursor
            classification, payload, status_code, error = fetch_with_retry(client=client, params=params)
            record_count = len(payload.get("items", [])) if isinstance(payload, dict) else 0
            new_ledger_rows.append(
                {
                    "proj_id": proj_id,
                    "page_no": page_no,
                    "status": classification,
                    "http_status": status_code,
                    "record_count": record_count,
                    "error": error,
                    "next_cursor_present": bool(payload.get("next_cursor")) if isinstance(payload, dict) else False,
                }
            )
            if payload is not None:
                raw_file_for(raw_dir, proj_id, page_no).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            if classification != "success":
                print(f"  still failing: {proj_id} page {page_no} -> {classification} ({error})")
                break
            valid_rows, issues = normalize_page_records(payload, proj_id=proj_id, expected_fund_class_name=expected_fund_class_name)
            recovered_rows.extend(valid_rows)
            recovered_issues.extend(issues)
            cursor = payload.get("next_cursor") if isinstance(payload, dict) else ""
            if not cursor:
                break
            time.sleep(BASE_SLEEP_SECONDS)

    still_blocking = [row for row in new_ledger_rows if row["status"] in BLOCKING_STATUSES]

    # Drop only the specific originally-failed ledger rows we just retried
    # (both to avoid double-counting and because the new rows supersede
    # them) and append what the repair actually produced.
    kept_ledger = ledger[~ledger.apply(lambda row: (row["proj_id"], int(row["page_no"])) in failed_keys, axis=1)]
    final_ledger_rows = kept_ledger.to_dict(orient="records") + new_ledger_rows

    existing_nav = pd.read_parquet(NORMALIZED_DIR / "daily_nav.parquet")
    final_nav_rows = existing_nav.to_dict(orient="records") + recovered_rows

    issues_path = NORMALIZED_DIR / "nav_data_quality_issues.parquet"
    existing_issues = pd.read_parquet(issues_path).to_dict(orient="records") if issues_path.exists() else []
    final_issues = existing_issues + recovered_issues

    write_parquet("daily_nav", final_nav_rows)
    write_parquet("nav_request_ledger", final_ledger_rows)
    if final_issues:
        write_parquet("nav_data_quality_issues", final_issues)

    status_counts = pd.Series([row["status"] for row in final_ledger_rows]).value_counts().to_dict()
    manifest["nav_rows"] = len(final_nav_rows)
    manifest["request_count"] = len(final_ledger_rows)
    manifest["status_counts"] = status_counts
    manifest["skipped_invalid_nav_rows"] = len(final_issues)
    manifest["valid_for_backtest"] = len(still_blocking) == 0 and len(final_nav_rows) > 0
    write_manifest(manifest)

    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    if still_blocking:
        raise SystemExit(f"{len(still_blocking)} request(s) are still failing after repair. Inspect nav_request_ledger.parquet.")
    print(f"Repair complete: recovered {len(recovered_rows)} NAV rows across {len(failed_keys)} originally-failed request(s).")


if __name__ == "__main__":
    main()
