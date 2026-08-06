import json
from pathlib import Path

import pandas as pd

NORMALIZED_DIR = Path("data/sec/normalized")


def write_parquet(name: str, rows: list[dict]) -> Path:
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    path = NORMALIZED_DIR / f"{name}.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def write_manifest(manifest: dict) -> Path:
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    path = NORMALIZED_DIR / "sec_data_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def migrate_schema(name: str, defaults: dict[str, object]) -> list[str]:
    """Additively bring an existing cached parquet up to a target schema.

    Only ever *adds* columns (with the given default value) -- it never
    renames, drops, or overwrites an existing column's values, so a
    partially-migrated cache is always still readable by both old and new
    code, and re-running the migration is always a safe no-op. This is the
    strategy for schema changes driven by pulling more fields from SEC
    (e.g. fund_status/cancel_date on fund_classes once the full fund
    universe is fetched, checklist 8.8) without invalidating or having to
    re-download the whole cache.
    """
    path = NORMALIZED_DIR / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No cached parquet named {name!r} at {path}")
    df = pd.read_parquet(path)
    added = [column for column in defaults if column not in df.columns]
    if not added:
        return []
    for column in added:
        df[column] = defaults[column]
    df.to_parquet(path, index=False)
    return added


def load_nav_panel(proj_ids: list[str]) -> pd.DataFrame:
    # `filters` is pushed down into the parquet read itself (row-group
    # pruning via pyarrow) so only the requested funds' rows are ever
    # materialized -- reading the whole file first and filtering in pandas
    # does not scale once the cache holds the full SEC fund universe.
    df = pd.read_parquet(NORMALIZED_DIR / "daily_nav.parquet", filters=[("proj_id", "in", proj_ids)])
    panel = df[df["proj_id"].isin(proj_ids)].pivot_table(
        index="nav_date",
        columns="proj_id",
        values="nav_per_unit",
        aggfunc="last",
    )
    panel.index = pd.to_datetime(panel.index)
    return panel.sort_index().dropna(how="all")
