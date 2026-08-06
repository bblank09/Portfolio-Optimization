"""Additively migrate cached SEC parquet files to a newer target schema.

Run this whenever a change adds fields that older cached parquet files
don't have yet (see docs/8.5-parquet-schema-migration.md for the full
strategy). It never renames, drops, or overwrites existing columns -- it
only adds missing ones with a default value -- so it is always safe to
re-run and never invalidates data already on disk.

Usage:
    python scripts/sec_migrate_schema.py
"""

import json

from backend.app.sec.cache import NORMALIZED_DIR, migrate_schema

# Each entry: (parquet name, {new column: default value}).
#
# fund_status/cancel_date are not persisted by the current
# scripts/sec_build_mvp_universe.py (it only reads them to *filter*
# candidates, see its `if record.get("cancel_date"): continue`), but
# checklist 8.8 (pulling the full SEC universe) needs them stored so a
# later survivorship-bias audit (checklist 3.2) can tell which funds in
# the universe have since closed/merged without re-fetching from SEC.
TARGET_SCHEMAS: dict[str, dict[str, object]] = {
    "fund_classes": {
        "fund_status": "",
        "cancel_date": None,
    },
}


def main() -> None:
    results = {}
    for name, defaults in TARGET_SCHEMAS.items():
        path = NORMALIZED_DIR / f"{name}.parquet"
        if not path.exists():
            results[name] = "skipped (no cached file yet)"
            continue
        added = migrate_schema(name, defaults)
        results[name] = {"added_columns": added} if added else "already up to date"
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
