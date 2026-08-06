import json
from pathlib import Path

from backend.app.sec.normalizers import (
    first_record,
    normalize_daily_nav_record,
    normalize_fund_class_record,
)


def test_fund_class_normalizer_uses_captured_contract():
    payload = json.loads(Path("backend/tests/fixtures/sec/contract/fund_profiles_SET.json").read_text())
    record = first_record(payload)
    row = normalize_fund_class_record(record)
    assert row["proj_id"]
    assert row["display_name"]
    assert "fund_class_name" in row
    assert row["amc_name_en"]
    assert row["policy_desc"]


def test_daily_nav_normalizer_uses_captured_contract():
    payload = json.loads(Path("backend/tests/fixtures/sec/contract/daily_nav_sample.json").read_text())
    record = first_record(payload)
    row = normalize_daily_nav_record(record)
    assert row["proj_id"]
    assert row["nav_date"]
    assert row["nav_per_unit"] > 0
    assert row["net_asset"] > 0


def test_daily_nav_normalizer_does_not_persist_the_raw_record():
    # Nothing downstream reads this field (grepped: only ever written, never
    # read), and it roughly doubles daily_nav.parquet's on-disk size --
    # measured at 79.5 bytes/row with it vs. 33.1 bytes/row without, on the
    # real committed cache. Pulling the full SEC fund universe (8.8) needs
    # that headroom to stay under GitHub's 100MB single-file limit.
    payload = json.loads(Path("backend/tests/fixtures/sec/contract/daily_nav_sample.json").read_text())
    record = first_record(payload)
    row = normalize_daily_nav_record(record)
    assert "raw" not in row
