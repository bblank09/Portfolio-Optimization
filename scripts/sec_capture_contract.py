import json
from pathlib import Path

from backend.app.sec.client import SecOpenDataClient
from backend.app.sec.endpoints import FUND_DAILY_NAV, FUND_PROFILES

OUT_DIR = Path("backend/tests/fixtures/sec/contract")
KNOWN_NAV_SAMPLE = {
    "proj_id": "M0004_2559",
    "start_nav_date": "2023-07-13",
    "end_nav_date": "2023-07-13",
    "page_size": 5,
}


def records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "result", "results", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def field_names(payload):
    rows = records(payload)
    if rows and isinstance(rows[0], dict):
        return sorted(rows[0].keys())
    if isinstance(payload, dict):
        return sorted(payload.keys())
    return []


def write_json(name, payload):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main():
    client = SecOpenDataClient()
    profile_params = {"project_info": "SET", "page_size": 5}
    fund_profiles = client.get(FUND_PROFILES, profile_params)
    write_json("fund_profiles_SET.json", fund_profiles)

    fund_rows = records(fund_profiles)
    if not fund_rows:
        raise SystemExit("Fund profile search returned no records. Update query params before continuing.")
    first_proj_id = fund_rows[0].get("proj_id")
    if not first_proj_id:
        raise SystemExit("Fund profile record has no proj_id. Inspect fixture and update field mapping.")

    nav_payload = client.get(FUND_DAILY_NAV, KNOWN_NAV_SAMPLE)
    nav_attempts = [
        {
            "endpoint": FUND_DAILY_NAV,
            "params": KNOWN_NAV_SAMPLE,
            "status": "success",
            "record_count": len(records(nav_payload)),
        }
    ]
    if not records(nav_payload):
        write_json("daily_nav_capture_attempts.json", nav_attempts)
        raise SystemExit("Known NAV sample returned no records. Inspect SEC contract before continuing.")
    write_json("daily_nav_sample.json", nav_payload)
    write_json("daily_nav_capture_attempts.json", nav_attempts)

    report = [
        "# SEC API Contract Capture",
        "",
        "## Fund Profiles",
        f"- Endpoint: `GET {FUND_PROFILES}`",
        f"- Query params: `{json.dumps(profile_params, ensure_ascii=False)}`",
        f"- Response type: `{type(fund_profiles).__name__}`",
        f"- Top-level fields: `{sorted(fund_profiles.keys()) if isinstance(fund_profiles, dict) else []}`",
        f"- Observed item fields: `{field_names(fund_profiles)}`",
        f"- First observed proj_id: `{first_proj_id}`",
        "",
        "## Daily NAV",
        f"- Endpoint: `GET {FUND_DAILY_NAV}`",
        f"- Query params: `{json.dumps(KNOWN_NAV_SAMPLE, ensure_ascii=False)}`",
        f"- Response type: `{type(nav_payload).__name__}`",
        f"- Top-level fields: `{sorted(nav_payload.keys()) if isinstance(nav_payload, dict) else []}`",
        f"- Observed item fields: `{field_names(nav_payload)}`",
        f"- Record count: `{len(records(nav_payload))}`",
    ]
    Path("docs/sec-api-contract.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
