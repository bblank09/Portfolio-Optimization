from scripts.sec_download_mvp import normalize_page_records


def test_normalize_page_records_skips_a_genuinely_invalid_nav_without_crashing():
    # Real SEC data for one fund (M0247_2562, 2019-06-17) has a literal 0.0
    # NAV on one day -- normalize_daily_nav_record correctly rejects that as
    # invalid, but a full-universe pull processes hundreds of funds in one
    # run and must not let a single bad day in one fund's history crash the
    # entire download. The bad row is skipped and recorded (not fabricated
    # or forward-filled) -- every other row on the page must still be kept.
    payload = {
        "items": [
            {"proj_id": "M0247_2562", "nav_date": "2019-06-17", "last_val": "0", "net_asset": "1000000"},
            {"proj_id": "M0247_2562", "nav_date": "2019-06-18", "last_val": "10.5", "net_asset": "1050000"},
        ]
    }

    valid_rows, issues = normalize_page_records(payload, proj_id="M0247_2562")

    assert len(valid_rows) == 1
    assert valid_rows[0]["nav_date"] == "2019-06-18"
    assert len(issues) == 1
    assert issues[0]["proj_id"] == "M0247_2562"
    assert issues[0]["nav_date"] == "2019-06-17"
    assert "Invalid NAV" in issues[0]["error"]


def test_normalize_page_records_returns_all_rows_when_none_are_invalid():
    payload = {
        "items": [
            {"proj_id": "FUND_A", "nav_date": "2024-01-01", "last_val": "10.0", "net_asset": "1000"},
            {"proj_id": "FUND_A", "nav_date": "2024-01-02", "last_val": "10.1", "net_asset": "1010"},
        ]
    }

    valid_rows, issues = normalize_page_records(payload, proj_id="FUND_A")

    assert len(valid_rows) == 2
    assert issues == []


def test_normalize_page_records_keeps_only_the_designated_share_class():
    # SEC's daily-info/nav endpoint returns EVERY share class under a
    # proj_id, not just the one the universe build picked -- e.g. real data
    # for M0000_2552 mixes "HIDIV-AR" and "HIDIV-D" rows with genuinely
    # different NAV values for the same date. Without filtering to the
    # universe's chosen class, load_nav_panel's pivot_table (aggfunc="last")
    # would silently mix NAV series from two different share classes into
    # one Frankenstein history for the same proj_id.
    payload = {
        "items": [
            {"proj_id": "M0000_2552", "fund_class_name": "HIDIV-AR", "nav_date": "2023-07-20", "last_val": "7.6334", "net_asset": "1000"},
            {"proj_id": "M0000_2552", "fund_class_name": "HIDIV-D", "nav_date": "2023-07-20", "last_val": "9.9999", "net_asset": "1000"},
        ]
    }

    valid_rows, issues = normalize_page_records(payload, proj_id="M0000_2552", expected_fund_class_name="HIDIV-AR")

    assert len(valid_rows) == 1
    assert valid_rows[0]["fund_class_name"] == "HIDIV-AR"
    assert valid_rows[0]["nav_per_unit"] == 7.6334
    assert issues == []


def test_normalize_page_records_keeps_everything_when_no_class_is_designated():
    payload = {
        "items": [
            {"proj_id": "FUND_A", "fund_class_name": "main", "nav_date": "2024-01-01", "last_val": "10.0", "net_asset": "1000"},
        ]
    }

    valid_rows, issues = normalize_page_records(payload, proj_id="FUND_A", expected_fund_class_name=None)

    assert len(valid_rows) == 1
