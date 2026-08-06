from typing import Any


def records(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "result", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        return [payload]
    return []


def first_record(payload: Any) -> dict:
    rows = records(payload)
    if not rows:
        raise ValueError("SEC payload does not contain any records")
    return rows[0]


def pick(record: dict, names: list[str], required: bool = True):
    for name in names:
        if name in record and record[name] not in (None, ""):
            return record[name]
    if required:
        raise KeyError(f"None of the expected SEC fields were present: {names}. Observed: {sorted(record.keys())}")
    return None


def to_float(value):
    if value in (None, "", "-"):
        return None
    return float(str(value).replace(",", ""))


def normalize_fund_class_record(record: dict) -> dict:
    proj_id = str(pick(record, ["proj_id", "PROJ_ID", "project_id"]))
    unique_id = pick(record, ["unique_id", "UNIQUE_ID"], required=False)
    fund_class_name = pick(record, ["fund_class_name", "FUND_CLASS_NAME", "class_name"], required=False)
    display_name = (
        pick(record, ["proj_abbr_name", "PROJ_ABBR_NAME"], required=False)
        or pick(record, ["proj_name_th", "PROJ_NAME_TH", "proj_name_en", "PROJ_NAME_EN"], required=False)
        or proj_id
    )
    return {
        "proj_id": proj_id,
        "unique_id": str(unique_id) if unique_id else "",
        "fund_class_name": str(fund_class_name) if fund_class_name else "",
        "class_abbr_name": str(fund_class_name) if fund_class_name else "",
        "display_name": str(display_name),
        "proj_name_th": str(pick(record, ["proj_name_th", "PROJ_NAME_TH"], required=False) or ""),
        "proj_name_en": str(pick(record, ["proj_name_en", "PROJ_NAME_EN"], required=False) or ""),
        "fund_status": str(pick(record, ["fund_status", "FUND_STATUS"], required=False) or ""),
        "policy_desc": str(pick(record, ["policy_desc", "POLICY_DESC"], required=False) or ""),
        "amc_name_th": str(pick(record, ["comp_name_th", "COMP_NAME_TH"], required=False) or ""),
        "amc_name_en": str(pick(record, ["comp_name_en", "COMP_NAME_EN"], required=False) or ""),
        "raw": record,
    }


def normalize_daily_nav_record(record: dict, proj_id: str | None = None) -> dict:
    resolved_proj_id = str(proj_id or pick(record, ["proj_id", "PROJ_ID", "project_id"]))
    nav_date = str(pick(record, ["nav_date", "NAV_DATE", "date"]))
    nav_per_unit = to_float(pick(record, ["last_val", "LAST_VAL", "nav_per_unit", "NAV_PER_UNIT"]))
    net_asset = to_float(pick(record, ["net_asset", "NET_ASSET", "net_assets"], required=False))
    if nav_per_unit is None or nav_per_unit <= 0:
        raise ValueError(f"Invalid NAV for {resolved_proj_id} {nav_date}: {nav_per_unit}")
    return {
        "proj_id": resolved_proj_id,
        "unique_id": str(pick(record, ["unique_id", "UNIQUE_ID"], required=False) or ""),
        "fund_class_name": str(pick(record, ["fund_class_name", "FUND_CLASS_NAME"], required=False) or ""),
        "nav_date": nav_date,
        "nav_per_unit": nav_per_unit,
        "net_asset": net_asset,
        "sell_price": to_float(pick(record, ["sell_price", "SELL_PRICE"], required=False)),
        "buy_price": to_float(pick(record, ["buy_price", "BUY_PRICE"], required=False)),
        "last_upd_date": pick(record, ["last_upd_date", "LAST_UPD_DATE", "updated_at"], required=False),
    }
