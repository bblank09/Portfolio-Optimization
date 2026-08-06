import csv
from pathlib import Path

from backend.app.sec.client import SecOpenDataClient
from backend.app.sec.endpoints import FUND_PROFILES
from backend.app.sec.normalizers import normalize_fund_class_record, records

# Checklist 8.8: pull the full SEC fund universe rather than a handful of
# keyword searches. MAX_FUNDS is bounded (not "all 4,900 Registered funds")
# because the resulting daily_nav.parquet must stay under GitHub's 100MB
# single-file limit. The original 800-fund pull actually landed at ~24MB
# (~30KB/fund observed, well under the earlier 56MB estimate), so 2,000
# funds projects to roughly 2000 * 30KB =~ 60MB -- still comfortable margin
# below the 100MB hard limit even if the real average runs somewhat higher.
MAX_FUNDS = 2000
PAGE_SIZE = 100

# AUM ranking (see scripts/sec_fetch_fund_aum.py) so a budget-capped universe
# keeps the largest/most-popular fund per category instead of whichever the
# SEC API happened to page first. Missing this file just falls back to the
# original pagination-order fill -- it's a ranking signal, not a hard
# dependency of universe selection.
FUND_AUM_BY_PROJ_ID_PATH = Path("data/sec/fund_aum_by_proj_id.csv")


def load_aum_by_proj_id(path: Path = FUND_AUM_BY_PROJ_ID_PATH) -> dict[str, float]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {row["proj_id"]: float(row["aum"]) for row in csv.DictReader(f) if row.get("aum")}


# These 12 funds are the ones already referenced by the frontend's "Load an
# example portfolio" shortcut and by several backend tests that pick
# universe.iloc[0] and expect it to have full NAV history since 2015 --
# they must stay first in the output and must never be dropped by the
# diversified fill below.
PREFERRED_PROJ_IDS = [
    "M0209_2548",
    "M0155_2547",
    "M0005_2565",
    "M0056_2564",
    "M0187_2563",
    "M0089_2545",
    "M0776_2547",
    "M0359_2552",
    "M0430_2556",
    "M0337_2550",
    "M0084_2545",
    "M0306_2552",
]

FIELDNAMES = [
    "proj_id",
    "unique_id",
    "fund_class_name",
    "class_abbr_name",
    "display_name",
    "search_term",
    "amc_name_th",
    "amc_name_en",
    "policy_desc",
]


def fetch_all_registered_candidates(client: SecOpenDataClient) -> list[dict]:
    """Page through the entire SEC fund-profile catalog (no search filter)
    and return normalized, deduplicated rows for Registered, non-PVD funds.
    """
    candidates = []
    seen = set()
    cursor = ""
    while True:
        params = {"page_size": PAGE_SIZE}
        if cursor:
            params["next_cursor"] = cursor
        payload = client.get(FUND_PROFILES, params)
        page_records = records(payload)
        if not page_records:
            break
        for record in page_records:
            if record.get("fund_status") != "Registered":
                continue
            row = normalize_fund_class_record(record)
            combined_name = f'{row["display_name"]} {row["fund_class_name"]}'.upper()
            if "PVD" in combined_name:
                continue
            key = f'{row["proj_id"]}:{row["fund_class_name"]}'
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "proj_id": row["proj_id"],
                    "unique_id": row["unique_id"],
                    "fund_class_name": row["fund_class_name"],
                    "class_abbr_name": row["class_abbr_name"],
                    "display_name": row["display_name"],
                    # policy_desc is already a clean, small set of official
                    # SEC category labels (e.g. "ตราสารทุน", "ตราสารหนี้",
                    # "ผสม") -- reuse it here instead of an arbitrary search
                    # keyword, and again below as the diversification bucket.
                    "search_term": row["policy_desc"] or "อื่นๆ",
                    "amc_name_th": row["amc_name_th"],
                    "amc_name_en": row["amc_name_en"],
                    "policy_desc": row["policy_desc"],
                }
            )
        cursor = payload.get("next_cursor") if isinstance(payload, dict) else ""
        if not cursor:
            break
    return candidates


def select_universe(
    candidates: list[dict], preferred_proj_ids: list[str], max_funds: int, aum_by_proj_id: dict[str, float] | None = None
) -> list[dict]:
    """Pick up to `max_funds` rows from `candidates`.

    1. Every proj_id in `preferred_proj_ids` that exists in `candidates`
       comes first, in the given order -- these must survive any budget cut.
    2. The remaining budget is filled by round-robin across policy_desc
       categories (via the `search_term` bucket set above), so a capped
       universe still covers equity/fixed-income/mixed/money-market funds
       instead of whatever order the SEC API happens to page them in.
       Within each category, candidates are sorted by AUM descending (see
       scripts/sec_fetch_fund_aum.py) before the round-robin picks them, so
       the funds that survive a budget cut are the largest/most-popular
       ones in their category rather than whichever the API paged first.
       Funds with no resolved AUM sort after every fund with a known AUM,
       keeping their original relative order.
    """
    aum_by_proj_id = aum_by_proj_id or {}
    by_proj_id: dict[str, dict] = {}
    for row in candidates:
        by_proj_id.setdefault(row["proj_id"], row)

    selected: list[dict] = []
    used: set[str] = set()
    for proj_id in preferred_proj_ids:
        if len(selected) >= max_funds:
            return selected
        row = by_proj_id.get(proj_id)
        if row is None or proj_id in used:
            continue
        selected.append(row)
        used.add(proj_id)

    buckets: dict[str, list[dict]] = {}
    for row in candidates:
        if row["proj_id"] in used:
            continue
        buckets.setdefault(row["search_term"], []).append(row)

    for items in buckets.values():
        items.sort(key=lambda row: aum_by_proj_id.get(row["proj_id"], -1), reverse=True)

    bucket_names = sorted(buckets)
    cursors = dict.fromkeys(bucket_names, 0)
    while len(selected) < max_funds:
        added_this_round = False
        for name in bucket_names:
            if len(selected) >= max_funds:
                break
            items = buckets[name]
            index = cursors[name]
            while index < len(items) and items[index]["proj_id"] in used:
                index += 1
            cursors[name] = index
            if index >= len(items):
                continue
            row = items[index]
            cursors[name] = index + 1
            selected.append(row)
            used.add(row["proj_id"])
            added_this_round = True
        if not added_this_round:
            break
    return selected


def main():
    client = SecOpenDataClient()
    candidates = fetch_all_registered_candidates(client)
    if not candidates:
        raise SystemExit("SEC search returned no normalized fund rows. Revisit Task 2 contract capture and field mapping.")

    aum_by_proj_id = load_aum_by_proj_id()
    rows = select_universe(candidates, PREFERRED_PROJ_IDS, MAX_FUNDS, aum_by_proj_id=aum_by_proj_id)
    if not rows:
        raise SystemExit("Universe selection produced zero rows from a non-empty candidate list -- check select_universe().")

    out = Path("data/sec/mvp_fund_universe.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print({"candidate_count": len(candidates), "fund_count": len(rows), "path": str(out)})


if __name__ == "__main__":
    main()
