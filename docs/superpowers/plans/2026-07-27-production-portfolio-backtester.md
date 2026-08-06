# SEC Open Data Portfolio Backtester Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready Portfolio Backtesting web app using only real SEC Open Data, with no mock data in the production app, while preserving the current mockup separately as a visual reference.

**Architecture:** Keep the current static mockup under `app/mockup-reference/` only. Build the real product as a separate `frontend/` React + TypeScript app connected to a `backend/` FastAPI service. The first production task is to authenticate to SEC Open Data, download the full dataset required for the app, normalize it into local cache tables, and only then build the backtest engine and UI on top of those cached real records.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pandas, numpy, scipy, httpx, SQLite, Parquet, pytest, React + TypeScript + Vite, Recharts or SVG charts, Playwright.

## Global Constraints

- Production data source is **SEC Open Data only**: `https://secopendata.sec.or.th/`, `https://api-portal.sec.or.th/`, and `https://api.sec.or.th/`.
- Production UI must not display mock values, seeded generated numbers, or temporary financial results.
- Existing mockup must not be deleted; move or keep it as visual reference only and label it clearly as non-production.
- Use no external price provider, broker import, broker connection, or manually uploaded transaction history in production scope.
- Use SEC Fund Daily Info NAV data as the primary historical price/value series for backtesting mutual-fund portfolios.
- Use SEC Fund Factsheet metadata only for fund lookup, class information, policy/category, risk, fees, holdings, and report context.
- Pull and cache all SEC datasets needed by the selected MVP before implementing the backtest engine.
- Every task ends with a user verification gate. The implementer must show the user how to verify the result and wait for explicit user confirmation before starting the next task.
- Keep Portfolio Backtesting only. Monte Carlo simulation, portfolio optimization, efficient frontier, and trading execution remain out of scope.
- Preserve the four objective presets: Past Performance, Monthly DCA, Monthly Withdrawal, Rebalancing Impact.
- Always show Benchmark Risk, Drawdown Stress, Diversification Check, and CQF Report after every completed run.
- Every numeric output must be reproducible from cached SEC source files, `run_config.json`, normalized dataset metadata, and formula documentation.

---

## Research Log

**Structural grounding:**

- Professional backtest result pages include equity/equivalent value curves, statistics, reports, logs/events, and downloadable result artifacts; QuantConnect documents result sections and downloadable backtest reports: https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results
- Consumer portfolio backtesting tools commonly expose holdings/weights, date range, initial amount, benchmark, cashflows, rebalancing, dividends/adjustments, CAGR, volatility, Sharpe, drawdown, rolling/annual/monthly returns, correlations, and exports. References used for structure: Portfolio Visualizer analysis page provided by user, testfol.io: https://testfol.io/, PortfolioBacktesting.com: https://www.portfoliobacktesting.com/
- GIPS/CFA performance practice distinguishes time-weighted and money-weighted return presentation and emphasizes consistent treatment of external cashflows, valuation frequency, transaction costs, and non-misleading reporting: https://www.gipsstandards.org/standards/gips-standards-for-firms/gips-standards-handbook-for-firms/ and https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/overview-of-the-global-investment-performance-standards

**Factual grounding for SEC Open Data:**

- SEC Open Data Services presents public datasets and APIs for Thai capital-market data, including funds: https://secopendata.sec.or.th/
- SEC API Developer Portal lists API groups including Fund Daily Info and Fund Factsheet API: https://api-portal.sec.or.th/apis
- SEC portal change log states the new SEC Open API Developer Portal became available on 12 January 2026 and the existing Developer Portal was discontinued on 30 June 2026; this matters because the implementation must target the current portal in July 2026: https://api-portal.sec.or.th/changes
- SEC Open Data API spec mirror captured from the 2026 developer portal shows the current base URL is `https://api.sec.or.th`, authentication uses header `Ocp-Apim-Subscription-Key`, and fund endpoints are under `/v2/fund/...`: https://github.com/Sitthinut/sec-open-data-api-spec
- SEC fund profiles use `GET /v2/fund/general-info/profiles` with query parameters such as `project_info`, `amc_id`, `proj_id`, `latest`, `page_size`, and `next_cursor`; this replaces the older legacy `POST /FundFactsheet/fund/class_fund` assumption for Task 2+.
- SEC daily NAV uses `GET /v2/fund/daily-info/nav` with query parameters `proj_id`, `start_nav_date`, `end_nav_date`, `fund_class_name`, `page_size`, and `next_cursor`; response items include `nav_date`, `net_asset`, and `last_val`, which are the primary series for fund backtesting: https://github.com/Sitthinut/sec-open-data-api-spec/blob/main/spec/categories/fund.json
- SEC factsheet portfolio context should also use current `/v2/fund/factsheet/...` endpoints, for example `asset-allocation` and `top5-holdings`; these are report/context data, not the primary backtest return series.
- pandas time-series `resample()` is the standard implementation primitive for converting daily NAV data to monthly/weekly observations: https://pandas.pydata.org/docs/user_guide/timeseries.html
- FastAPI documents API testing with `TestClient`, which will be used for backend route verification: https://fastapi.tiangolo.com/tutorial/testing/

**Unverified / project-specific facts:**

- The exact authentication header name for the user's SEC API key must be confirmed by running an authenticated smoke request against the user's portal/API subscription. The plan isolates this in Task 2 before any engine work.
- SEC API pagination, rate limits, field names, and allowed historical date range for the user's subscription must be measured with real responses before normalizers are finalized.
- The final MVP universe must be either "user-selected fund list" or "all active funds available through SEC API." To satisfy the user's instruction to pull data first without exploding runtime, Task 3 builds `mvp_fund_universe.csv` from authenticated SEC search results and asks the user to verify it before the full NAV pull.

---

## File Structure

```text
<project-root>/
  README.md
  pyproject.toml
  package.json
  .env.example
  app/
    mockup-reference/
      index.html
      mockup.css
      mockup.js
      Portfolio Backtester.dc.html
    README.md
  backend/
    app/main.py
    app/core/config.py
    app/core/errors.py
    app/domain/enums.py
    app/domain/schemas.py
    app/sec/client.py
    app/sec/endpoints.py
    app/sec/inventory.py
    app/sec/normalizers.py
    app/sec/cache.py
    app/data/quality.py
    app/engine/returns.py
    app/engine/metrics.py
    app/engine/cashflows.py
    app/engine/rebalancing.py
    app/engine/backtest.py
    app/api/funds.py
    app/api/backtests.py
    app/reports/markdown.py
    app/reports/artifacts.py
    tests/fixtures/sec/*.json
    tests/test_sec_client.py
    tests/test_sec_normalizers.py
    tests/test_sec_cache.py
    tests/test_returns.py
    tests/test_metrics.py
    tests/test_backtest_engine.py
    tests/test_api_backtests.py
    tests/test_reproducibility.py
  frontend/
    index.html
    src/main.tsx
    src/api/client.ts
    src/types/backtest.ts
    src/objectives/objectives.ts
    src/components/ObjectivePicker.tsx
    src/components/FundSelector.tsx
    src/components/PortfolioEditor.tsx
    src/components/AssumptionPanel.tsx
    src/components/RunSummary.tsx
    src/components/tabs/*.tsx
    src/pages/BacktestWorkspace.tsx
    src/styles.css
    tests/backtest-workspace.spec.ts
  data/
    sec/raw/
    sec/normalized/
    runs/
  docs/
    sec-data-inventory.md
    data-policy.md
    methodology.md
    formula-reference.md
    user-guide.md
    superpowers/plans/2026-07-27-production-portfolio-backtester.md
```

---

## Mandatory User Verification Gate

Every task below has a **User Verification Gate**. After completing a task, the implementer must:

1. Show exact commands or browser steps the user can run.
2. State the expected result.
3. Stop and ask: `ยืนยันไหมครับว่า Task N ผ่านแล้ว ให้ไป Task N+1 ต่อ?`
4. Continue only after the user explicitly confirms.

This gate is part of the production process, not optional.

---

## Implementation Tasks

### Task 1: Separate Mockup Reference From Production App

**Files:**
- Create: `app/mockup-reference/README.md`
- Move: `app/index.html` -> `app/mockup-reference/index.html`
- Move: `app/mockup.css` -> `app/mockup-reference/mockup.css`
- Move: `app/mockup.js` -> `app/mockup-reference/mockup.js`
- Move: `app/Portfolio Backtester.dc.html` -> `app/mockup-reference/Portfolio Backtester.dc.html`
- Modify: `README.md`

**Interfaces:**
- Produces a clearly labeled mockup reference folder.
- Produces no production data pipeline yet.

- [ ] **Step 1: Move mockup files without deleting them**

Run:

```bash
mkdir -p "app/mockup-reference"
mv "app/index.html" "app/mockup-reference/index.html"
mv "app/mockup.css" "app/mockup-reference/mockup.css"
mv "app/mockup.js" "app/mockup-reference/mockup.js"
mv "app/Portfolio Backtester.dc.html" "app/mockup-reference/Portfolio Backtester.dc.html"
```

- [ ] **Step 2: Add mockup warning**

Create `app/mockup-reference/README.md`:

```markdown
# Mockup Reference Only

This folder contains the old UI mockup. It is preserved for design reference only.

Production rules:

- Do not use seeded sample data from this folder.
- Do not import `mockup.js` into production code.
- Do not show mock financial values in production UI.
- Production data must come from cached SEC Open Data only.
```

- [ ] **Step 3: Update root README**

README must state:

```markdown
## Production Entry Points

- Mockup reference: `app/mockup-reference/index.html`
- Production frontend: `frontend/`
- Production backend: `backend/`
- Production data source: SEC Open Data only

The production app must not display mock financial data.
```

- [ ] **Step 4: Verify**

Run:

```bash
find "app/mockup-reference" -maxdepth 1 -type f | sort
rg -n "Mockup Reference Only|SEC Open Data only|must not display mock" README.md app/mockup-reference/README.md
```

Expected:

- The old mockup files appear under `app/mockup-reference/`.
- README clearly says production uses SEC Open Data only.

**User Verification Gate:** Ask the user to open `app/mockup-reference/index.html` and confirm it is only the old reference, then ask: `ยืนยันไหมครับว่า Task 1 ผ่านแล้ว ให้ไป Task 2 ต่อ?`

### Task 2: Production Scaffold and SEC API Key Smoke Test

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/sec/client.py`
- Create: `backend/app/sec/endpoints.py`
- Create: `scripts/sec_capture_contract.py`
- Create: `docs/sec-api-contract.md`
- Create: `backend/tests/test_sec_client.py`

**Interfaces:**
- Produces `SecOpenDataClient.get(path: str, params: dict | None = None) -> dict | list`.
- Produces real SEC response fixtures under `backend/tests/fixtures/sec/contract/`.
- Produces `docs/sec-api-contract.md` from real response inspection.
- Consumes environment variable `SEC_API_KEY`.

- [ ] **Step 1: Create dependencies**

`pyproject.toml`:

```toml
[project]
name = "sec-open-data-portfolio-backtester"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.111",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.7",
  "pydantic-settings>=2.2",
  "pandas>=2.2",
  "numpy>=1.26",
  "scipy>=1.13",
  "httpx>=0.27",
  "pyarrow>=16.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-cov>=5.0", "ruff>=0.5", "mypy>=1.10"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["backend/tests"]
```

`.env.example`:

```env
SEC_API_KEY=
SEC_API_BASE_URL=https://api.sec.or.th
DATA_DIR=data
SEC_CACHE_DIR=data/sec
```

- [ ] **Step 2: Implement config and endpoints**

```python
# backend/app/core/config.py
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    sec_api_key: str = ""
    sec_api_base_url: str = "https://api.sec.or.th"
    data_dir: Path = Path("data")
    sec_cache_dir: Path = Path("data/sec")


settings = Settings(_env_file=".env", _env_file_encoding="utf-8")
```

```python
# backend/app/sec/endpoints.py
FUND_AMCS = "/v2/fund/general-info/amcs"
FUND_PROFILES = "/v2/fund/general-info/profiles"
FUND_FACTSHEET_ASSET_ALLOCATION = "/v2/fund/factsheet/asset-allocation"
FUND_FACTSHEET_TOP5_HOLDINGS = "/v2/fund/factsheet/top5-holdings"
FUND_DAILY_NAV = "/v2/fund/daily-info/nav"
FUND_DAILY_DIVIDEND = "/v2/fund/daily-info/dividend-history"
```

- [ ] **Step 3: Implement SEC client with configurable auth headers**

```python
# backend/app/sec/client.py
import httpx
from backend.app.core.config import settings


class SecOpenDataClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key is not None else settings.sec_api_key
        self.base_url = (base_url or settings.sec_api_base_url).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Cache-Control": "no-cache",
            "Accept": "application/json",
        }

    def get(self, path: str, params: dict | None = None):
        url = f"{self.base_url}{path}"
        response = httpx.get(url, headers=self._headers(), params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict | list | None = None):
        url = f"{self.base_url}{path}"
        response = httpx.post(url, headers=self._headers(), json=payload or {}, timeout=30)
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Add local unit test for client header construction only**

This test does **not** prove SEC authentication works. It only verifies that the local client forwards the configured key into the currently assumed header. Real authentication is verified in Step 6.

```python
# backend/tests/test_sec_client.py
from backend.app.sec.client import SecOpenDataClient


def test_sec_client_builds_configured_headers():
    client = SecOpenDataClient(api_key="abc123", base_url="https://api.sec.or.th")
    headers = client._headers()
    assert headers["Ocp-Apim-Subscription-Key"] == "abc123"
    assert headers["Accept"] == "application/json"
```

- [ ] **Step 5: Verify locally**

Run:

```bash
pytest backend/tests/test_sec_client.py -q
```

Expected: PASS. This means the local client builds the configured request shape. It does not mean the SEC API accepted the key.

- [ ] **Step 6: Capture real SEC API contract before writing normalizers**

Create `.env` from `.env.example`, set `SEC_API_KEY`, then run:

```bash
python scripts/sec_capture_contract.py
```

Expected:

- No `401` or `403`.
- Files exist under `backend/tests/fixtures/sec/contract/`.
- `docs/sec-api-contract.md` lists observed top-level response type, record count, and field names for fund search and one daily NAV response.
- If SEC expects a different header or payload, update `SecOpenDataClient` and rerun this step before Task 3.

Create `scripts/sec_capture_contract.py`:

```python
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
    nav_attempts = [{"endpoint": FUND_DAILY_NAV, "params": KNOWN_NAV_SAMPLE, "status": "success", "record_count": len(records(nav_payload))}]
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
        f"- Observed item fields: `{field_names(fund_profiles)}`",
        f"- First observed proj_id: `{first_proj_id}`",
        "",
        "## Daily NAV",
        f"- Endpoint: `GET {FUND_DAILY_NAV}`",
        f"- Query params: `{json.dumps(KNOWN_NAV_SAMPLE, ensure_ascii=False)}`",
        f"- Response type: `{type(nav_payload).__name__}`",
        f"- Observed item fields: `{field_names(nav_payload)}`",
    ]
    Path("docs/sec-api-contract.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
```

**User Verification Gate:** Ask the user to open `docs/sec-api-contract.md` and the two captured JSON fixtures, confirm the observed field names make sense, then ask: `ยืนยันไหมครับว่า Task 2 ผ่านแล้ว ให้ไป Task 3 ต่อ?`

### Task 3: Freeze SEC Response Contract, Then Pull and Cache MVP Data

**Files:**
- Create: `backend/app/sec/inventory.py`
- Create: `backend/app/sec/cache.py`
- Create: `backend/app/sec/normalizers.py`
- Create: `scripts/sec_build_mvp_universe.py`
- Create: `scripts/sec_download_mvp.py`
- Create: `docs/sec-data-inventory.md`
- Create: `data/sec/raw/`
- Create: `data/sec/normalized/`
- Create: `backend/tests/test_sec_normalizers.py`
- Create: `backend/tests/test_sec_cache.py`

**Interfaces:**
- Consumes captured contract fixtures from Task 2.
- Produces normalized files:
  - `data/sec/normalized/fund_classes.parquet`
  - `data/sec/normalized/daily_nav.parquet`
  - `data/sec/normalized/nav_request_ledger.parquet`
  - `data/sec/normalized/sec_data_manifest.json`
- Produces `load_nav_panel(proj_ids: list[str]) -> pd.DataFrame`.

- [ ] **Step 1: Define SEC dataset inventory from observed contract**

`docs/sec-data-inventory.md` must include:

```markdown
# SEC Data Inventory

## Contract Capture

- Source: `backend/tests/fixtures/sec/contract/fund_profiles_SET.json`
- Source: `backend/tests/fixtures/sec/contract/daily_nav_sample.json`
- Contract notes: see `docs/sec-api-contract.md`

## MVP Datasets

1. Fund profile metadata
   - Endpoint: `GET /v2/fund/general-info/profiles`
   - Purpose: fund lookup and class handling
   - Field map must be copied from real contract capture.

2. Fund daily NAV
   - Endpoint: `GET /v2/fund/daily-info/nav`
   - Purpose: historical backtest value series.
   - Field map must be copied from real contract capture.

## Missing Data Classification

- `success`: response returned at least one NAV record.
- `no_nav_for_date`: SEC returned 404 or empty business-valid response for a non-trading/non-NAV date.
- `rate_limited`: SEC returned 429 and retry budget was exhausted.
- `auth_error`: SEC returned 401 or 403.
- `server_error`: SEC returned 5xx and retry budget was exhausted.
- `network_error`: request failed after retry budget.

Runs with `rate_limited`, `auth_error`, `server_error`, or `network_error` in the ledger are not valid for production backtesting until resolved.
```

- [ ] **Step 2: Write normalizer tests against captured real fixtures**

```python
# backend/tests/test_sec_normalizers.py
import json
from pathlib import Path
from backend.app.sec.normalizers import first_record, normalize_daily_nav_record, normalize_fund_class_record


def test_fund_class_normalizer_uses_captured_contract():
    payload = json.loads(Path("backend/tests/fixtures/sec/contract/fund_class_search_SET.json").read_text())
    record = first_record(payload)
    row = normalize_fund_class_record(record)
    assert row["proj_id"]
    assert row["display_name"]


def test_daily_nav_normalizer_uses_captured_contract():
    payload = json.loads(Path("backend/tests/fixtures/sec/contract/daily_nav_sample.json").read_text())
    record = first_record(payload)
    row = normalize_daily_nav_record(record, proj_id=row_proj_id(record))
    assert row["proj_id"]
    assert row["nav_date"]
    assert row["nav_per_unit"] > 0


def row_proj_id(record):
    return record.get("proj_id") or record.get("PROJ_ID") or record.get("project_id") or "captured_proj_id"
```

- [ ] **Step 3: Implement contract-aware normalizers**

The implementer must update these candidate field lists only after inspecting `docs/sec-api-contract.md`.

```python
# backend/app/sec/normalizers.py
from typing import Any


def first_record(payload: Any) -> dict:
    if isinstance(payload, list):
        return payload[0]
    if isinstance(payload, dict):
        for key in ("data", "result", "results", "items"):
            if isinstance(payload.get(key), list) and payload[key]:
                return payload[key][0]
        return payload
    raise ValueError("SEC payload is neither list nor dict")


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
    return {
        "proj_id": proj_id,
        "class_abbr_name": pick(record, ["class_abbr_name", "CLASS_ABBR_NAME", "class_name"], required=False) or "",
        "display_name": pick(record, ["proj_abbr_name", "PROJ_ABBR_NAME", "proj_name_th", "PROJ_NAME_TH", "name_th", "fund_name"], required=False) or proj_id,
        "raw": record,
    }


def normalize_daily_nav_record(record: dict, proj_id: str) -> dict:
    nav_date = str(pick(record, ["nav_date", "NAV_DATE", "date"]))
    nav_per_unit = to_float(pick(record, ["last_val", "LAST_VAL", "nav_per_unit", "NAV_PER_UNIT"]))
    net_asset = to_float(pick(record, ["net_asset", "NET_ASSET", "net_assets"], required=False))
    if nav_per_unit is None or nav_per_unit <= 0:
        raise ValueError(f"Invalid NAV for {proj_id} {nav_date}: {nav_per_unit}")
    return {
        "proj_id": proj_id,
        "nav_date": nav_date,
        "nav_per_unit": nav_per_unit,
        "net_asset": net_asset,
        "last_upd_date": pick(record, ["last_upd_date", "LAST_UPD_DATE", "updated_at"], required=False),
        "raw": record,
    }
```

- [ ] **Step 4: Build MVP universe from normalized SEC search response**

Create `scripts/sec_build_mvp_universe.py`:

```python
import csv
from pathlib import Path
from backend.app.sec.client import SecOpenDataClient
from backend.app.sec.endpoints import FUND_PROFILES
from backend.app.sec.normalizers import normalize_fund_class_record


SEARCH_TERMS = ["SET", "ตราสารทุน", "หุ้น", "ตลาดเงิน", "พันธบัตร"]
MAX_FUNDS = 12


def records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "result", "results", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def main():
    client = SecOpenDataClient()
    rows = []
    seen = set()
    for term in SEARCH_TERMS:
        payload = client.get(FUND_PROFILES, {"project_info": term, "page_size": 100})
        for record in records(payload):
            row = normalize_fund_class_record(record)
            if row["proj_id"] in seen:
                continue
            seen.add(row["proj_id"])
            rows.append({k: row[k] for k in ("proj_id", "class_abbr_name", "display_name")} | {"search_term": term})
            if len(rows) >= MAX_FUNDS:
                break
        if len(rows) >= MAX_FUNDS:
            break
    if not rows:
        raise SystemExit("SEC search returned no normalized fund rows. Revisit Task 2 contract capture and field mapping.")
    out = Path("data/sec/mvp_fund_universe.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["proj_id", "class_abbr_name", "display_name", "search_term"])
        writer.writeheader()
        writer.writerows(rows)
    print({"fund_count": len(rows), "path": str(out)})
```

- [ ] **Step 5: Implement cache helpers and NAV request ledger**

```python
# backend/app/sec/cache.py
from pathlib import Path
import json
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


def load_nav_panel(proj_ids: list[str]) -> pd.DataFrame:
    df = pd.read_parquet(NORMALIZED_DIR / "daily_nav.parquet")
    panel = df[df["proj_id"].isin(proj_ids)].pivot_table(index="nav_date", columns="proj_id", values="nav_per_unit", aggfunc="last")
    panel.index = pd.to_datetime(panel.index)
    return panel.sort_index().dropna(how="all")
```

- [ ] **Step 6: Implement rate-limited downloader with explicit error classification**

Create `scripts/sec_download_mvp.py`. It must use business dates, a small throttle, retries, `Retry-After` support, and a request ledger. It must never use `except Exception: continue`.

```python
from datetime import date
import csv
import json
import time
from pathlib import Path
import httpx
import pandas as pd
from backend.app.sec.client import SecOpenDataClient
from backend.app.sec.endpoints import FUND_DAILY_NAV
from backend.app.sec.cache import write_manifest, write_parquet
from backend.app.sec.normalizers import normalize_daily_nav_record


START_DATE = date(2015, 1, 1)
MAX_RETRIES = 4
BASE_SLEEP_SECONDS = 0.25


def business_dates(start: date, end: date) -> list[date]:
    return [ts.date() for ts in pd.bdate_range(start=start, end=end)]


def classify_http_status(status_code: int) -> str:
    if status_code == 404:
        return "no_nav_for_date"
    if status_code == 429:
        return "rate_limited"
    if status_code in (401, 403):
        return "auth_error"
    if 500 <= status_code <= 599:
        return "server_error"
    return "http_error"


def fetch_with_retry(client: SecOpenDataClient, path: str, params: dict) -> tuple[str, object | None, int | None, str]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            payload = client.get(path, params)
            return "success", payload, 200, ""
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            classification = classify_http_status(status_code)
            retry_after = exc.response.headers.get("Retry-After")
            if classification in ("rate_limited", "server_error") and attempt < MAX_RETRIES:
                sleep_for = float(retry_after) if retry_after else BASE_SLEEP_SECONDS * (2 ** attempt)
                time.sleep(sleep_for)
                continue
            return classification, None, status_code, str(exc)
        except httpx.RequestError as exc:
            if attempt < MAX_RETRIES:
                time.sleep(BASE_SLEEP_SECONDS * (2 ** attempt))
                continue
            return "network_error", None, None, str(exc)


def records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "result", "results", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return [payload]
    return []


def main():
    client = SecOpenDataClient()
    funds = list(csv.DictReader(Path("data/sec/mvp_fund_universe.csv").open(encoding="utf-8")))
    if not funds:
        raise SystemExit("Run scripts/sec_build_mvp_universe.py and verify the generated universe before downloading NAV.")

    raw_dir = Path("data/sec/raw/daily_nav")
    raw_dir.mkdir(parents=True, exist_ok=True)
    nav_rows = []
    ledger_rows = []
    end_date = date.today()

    for fund in funds:
        proj_id = fund["proj_id"]
        next_cursor = ""
        page_no = 0
        while True:
            page_no += 1
            params = {
                "proj_id": proj_id,
                "start_nav_date": START_DATE.isoformat(),
                "end_nav_date": end_date.isoformat(),
                "page_size": 100,
            }
            if next_cursor:
                params["next_cursor"] = next_cursor
            classification, payload, status_code, error = fetch_with_retry(client, FUND_DAILY_NAV, params)
            ledger_rows.append({"proj_id": proj_id, "page_no": page_no, "status": classification, "http_status": status_code, "error": error})
            if classification != "success":
                break
            raw_file = raw_dir / f"{proj_id}_{page_no}.json"
            raw_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            for record in records(payload):
                nav_rows.append(normalize_daily_nav_record(record))
            next_cursor = payload.get("next_cursor") if isinstance(payload, dict) else ""
            if not next_cursor:
                break
            time.sleep(BASE_SLEEP_SECONDS)
            for record in records(payload):
                nav_rows.append(normalize_daily_nav_record(record, proj_id=proj_id))
            time.sleep(BASE_SLEEP_SECONDS)

    write_parquet("daily_nav", nav_rows)
    write_parquet("fund_classes", funds)
    write_parquet("nav_request_ledger", ledger_rows)
    blocking_statuses = {"rate_limited", "auth_error", "server_error", "network_error", "http_error"}
    blocking = [row for row in ledger_rows if row["status"] in blocking_statuses]
    manifest = {
        "source": "SEC Open Data",
        "start": START_DATE.isoformat(),
        "end": end_date.isoformat(),
        "fund_count": len(funds),
        "nav_rows": len(nav_rows),
        "request_count": len(ledger_rows),
        "status_counts": pd.Series([row["status"] for row in ledger_rows]).value_counts().to_dict(),
        "valid_for_backtest": len(blocking) == 0,
    }
    write_manifest(manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    if blocking:
        raise SystemExit("SEC NAV download has blocking request failures. Inspect data/sec/normalized/nav_request_ledger.parquet before continuing.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Verify normalized cache and request ledger**

Run:

```bash
pytest backend/tests/test_sec_normalizers.py -q
python scripts/sec_build_mvp_universe.py
python scripts/sec_download_mvp.py
python - <<'PY'
import json
import pandas as pd
from pathlib import Path

manifest = json.loads(Path("data/sec/normalized/sec_data_manifest.json").read_text())
nav = pd.read_parquet("data/sec/normalized/daily_nav.parquet")
ledger = pd.read_parquet("data/sec/normalized/nav_request_ledger.parquet")
print(manifest)
print(nav.groupby("proj_id")["nav_date"].agg(["min", "max", "count"]))
print(ledger["status"].value_counts())
PY
```

Expected:

- `sec_data_manifest.json`, `daily_nav.parquet`, and `nav_request_ledger.parquet` exist.
- `manifest["valid_for_backtest"]` is `true`.
- Ledger has no `rate_limited`, `auth_error`, `server_error`, `network_error`, or `http_error` rows.
- `no_nav_for_date` rows are visible and treated differently from request failures.
- Each MVP fund has enough successful NAV observations for backtesting.

**User Verification Gate:** Show the user the manifest, NAV coverage table, and ledger status counts. Ask the user to confirm the fund universe and cached NAV coverage before moving on: `ยืนยันไหมครับว่า Task 3 ผ่านแล้ว ให้ไป Task 4 ต่อ?`

### Task 4: SEC-Only Domain Contracts

**Files:**
- Create: `backend/app/domain/enums.py`
- Create: `backend/app/domain/schemas.py`
- Create: `backend/tests/test_schemas.py`
- Create: `frontend/src/types/backtest.ts`

**Interfaces:**
- Produces `BacktestRequest` where assets are SEC fund `proj_id` values, not stock tickers.
- Produces `BacktestResult` contract.

- [ ] **Step 1: Write schema test**

```python
# backend/tests/test_schemas.py
import pytest
from pydantic import ValidationError
from backend.app.domain.schemas import BacktestRequest


def valid_request():
    return {
        "objective": "monthly_dca",
        "assets": [{"proj_id": "M0001_2550", "display_name": "Fund A", "weight": 60}, {"proj_id": "M0002_2550", "display_name": "Fund B", "weight": 40}],
        "start_date": "2020-01-31",
        "end_date": "2024-12-31",
        "initial_capital": 10000,
        "benchmark_proj_id": "M0001_2550",
        "cashflow": {"enabled": True, "type": "contribution", "amount": 500, "frequency": "monthly", "timing": "end"},
        "rebalancing": {"mode": "annual"},
        "costs": {"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
        "data": {"source": "sec_open_data", "price_field": "nav_per_unit"},
    }


def test_valid_sec_backtest_request():
    request = BacktestRequest(**valid_request())
    assert request.assets[0].proj_id == "M0001_2550"


def test_weights_must_sum_to_100():
    payload = valid_request()
    payload["assets"][0]["weight"] = 50
    with pytest.raises(ValidationError):
        BacktestRequest(**payload)
```

- [ ] **Step 2: Implement schemas**

```python
# backend/app/domain/enums.py
from enum import StrEnum


class Objective(StrEnum):
    past_performance = "past_performance"
    monthly_dca = "monthly_dca"
    monthly_withdrawal = "monthly_withdrawal"
    rebalancing_impact = "rebalancing_impact"


class Frequency(StrEnum):
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"


class CashflowType(StrEnum):
    contribution = "contribution"
    withdrawal = "withdrawal"


class CashflowTiming(StrEnum):
    beginning = "beginning"
    end = "end"


class RebalanceMode(StrEnum):
    none = "none"
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
```

```python
# backend/app/domain/schemas.py
from datetime import date
from pydantic import BaseModel, Field, model_validator
from .enums import CashflowTiming, CashflowType, Frequency, Objective, RebalanceMode


class SecFundAllocation(BaseModel):
    proj_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    weight: float = Field(ge=0, le=100)


class CashflowRule(BaseModel):
    enabled: bool
    type: CashflowType
    amount: float = Field(ge=0)
    frequency: Frequency
    timing: CashflowTiming


class RebalanceRule(BaseModel):
    mode: RebalanceMode


class CostAssumptions(BaseModel):
    transaction_bps: float = Field(ge=0)
    slippage_bps: float = Field(ge=0)
    annual_drag_pct: float = Field(ge=0)


class DataAssumptions(BaseModel):
    source: str = "sec_open_data"
    price_field: str = "nav_per_unit"


class BacktestRequest(BaseModel):
    objective: Objective
    assets: list[SecFundAllocation] = Field(min_length=1, max_length=20)
    start_date: date
    end_date: date
    initial_capital: float = Field(gt=0)
    benchmark_proj_id: str
    cashflow: CashflowRule
    rebalancing: RebalanceRule
    costs: CostAssumptions
    data: DataAssumptions

    @model_validator(mode="after")
    def validate_request(self):
        total = sum(asset.weight for asset in self.assets)
        if abs(total - 100) > 0.01:
            raise ValueError(f"weights must sum to 100, got {total:.4f}")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.data.source != "sec_open_data":
            raise ValueError("production data source must be sec_open_data")
        return self
```

- [ ] **Step 3: Verify**

Run:

```bash
pytest backend/tests/test_schemas.py -q
```

Expected: PASS.

**User Verification Gate:** Show the passing schema tests and ask: `ยืนยันไหมครับว่า Task 4 ผ่านแล้ว ให้ไป Task 5 ต่อ?`

### Task 5: SEC NAV Quality and Alignment

**Files:**
- Create: `backend/app/data/quality.py`
- Create: `backend/tests/test_sec_cache.py`

**Interfaces:**
- Produces `load_aligned_nav_returns(proj_ids, start_date, end_date, frequency="monthly") -> pd.DataFrame`.
- Produces visible quality issues for missing NAV, short history, stale data, and insufficient overlap.

- [ ] **Step 1: Write tests**

```python
# backend/tests/test_sec_cache.py
import pandas as pd
from backend.app.data.quality import align_nav_panel, validate_nav_panel


def test_align_nav_panel_monthly_last_value():
    panel = pd.DataFrame(
        {"FUND_A": [10.0, 11.0, 12.0], "FUND_B": [20.0, 22.0, 24.0]},
        index=pd.to_datetime(["2024-01-02", "2024-01-31", "2024-02-29"]),
    )
    aligned = align_nav_panel(panel, frequency="monthly")
    assert list(aligned.index.strftime("%Y-%m-%d")) == ["2024-01-31", "2024-02-29"]
    assert aligned.loc[pd.Timestamp("2024-01-31"), "FUND_A"] == 11.0


def test_validate_nav_panel_flags_missing_values():
    panel = pd.DataFrame({"FUND_A": [10.0, None]}, index=pd.to_datetime(["2024-01-31", "2024-02-29"]))
    issues = validate_nav_panel(panel)
    assert any(issue["code"] == "missing_nav" for issue in issues)
```

- [ ] **Step 2: Implement quality functions**

```python
# backend/app/data/quality.py
import pandas as pd


def align_nav_panel(panel: pd.DataFrame, frequency: str = "monthly") -> pd.DataFrame:
    if frequency == "monthly":
        return panel.resample("M").last().dropna(how="all")
    if frequency == "weekly":
        return panel.resample("W-FRI").last().dropna(how="all")
    return panel.sort_index()


def validate_nav_panel(panel: pd.DataFrame) -> list[dict[str, str]]:
    issues = []
    if panel.empty:
        issues.append({"code": "empty_nav_panel", "message": "No NAV records available for the selected funds/date range."})
    if panel.isna().any().any():
        issues.append({"code": "missing_nav", "message": "Some funds have missing NAV values after alignment."})
    if len(panel.dropna(how="any")) < 12:
        issues.append({"code": "short_history", "message": "Less than 12 complete observations are available."})
    if (panel <= 0).any().any():
        issues.append({"code": "non_positive_nav", "message": "NAV contains zero or negative values."})
    return issues
```

- [ ] **Step 3: Verify**

Run:

```bash
pytest backend/tests/test_sec_cache.py -q
python - <<'PY'
from backend.app.sec.cache import load_nav_panel
from backend.app.data.quality import align_nav_panel, validate_nav_panel
import pandas as pd
universe = pd.read_csv("data/sec/mvp_fund_universe.csv")
panel = load_nav_panel(universe["proj_id"].tolist())
aligned = align_nav_panel(panel)
print(aligned.tail())
print(validate_nav_panel(aligned))
PY
```

Expected:

- Unit tests pass.
- Real SEC cached NAV aligns to monthly observations.
- Quality issues are printed and understood before engine work starts.

**User Verification Gate:** Ask the user to inspect latest aligned NAV rows and quality issues, then ask: `ยืนยันไหมครับว่า Task 5 ผ่านแล้ว ให้ไป Task 6 ต่อ?`

### Task 6: Formula Engine for SEC Fund NAV Backtesting

**Files:**
- Create: `backend/app/engine/returns.py`
- Create: `backend/app/engine/metrics.py`
- Create: `backend/tests/test_returns.py`
- Create: `backend/tests/test_metrics.py`
- Create: `docs/formula-reference.md`

**Interfaces:**
- Produces TWRR, MWRR/IRR, CAGR, volatility, Sharpe, Sortino, Calmar, max drawdown, beta, alpha, tracking error, information ratio, correlation.

- [ ] **Step 1: Write formula tests**

```python
# backend/tests/test_returns.py
import pandas as pd
from backend.app.engine.returns import simple_returns, time_weighted_return


def test_simple_returns_from_nav():
    nav = pd.DataFrame({"FUND_A": [10.0, 11.0, 9.9]})
    returns = simple_returns(nav)
    assert round(float(returns.iloc[0]["FUND_A"]), 6) == 0.10
    assert round(float(returns.iloc[1]["FUND_A"]), 6) == -0.10


def test_twrr_links_returns():
    assert round(time_weighted_return(pd.Series([0.10, -0.10])), 6) == -0.01
```

```python
# backend/tests/test_metrics.py
import pandas as pd
from backend.app.engine.metrics import max_drawdown, beta_alpha


def test_max_drawdown():
    assert round(max_drawdown(pd.Series([100, 120, 90, 150])), 6) == -0.25


def test_beta_alpha_returns_floats():
    beta, alpha = beta_alpha(pd.Series([0.02, 0.01, -0.01]), pd.Series([0.01, 0.02, -0.02]), 0.0, 12)
    assert isinstance(beta, float)
    assert isinstance(alpha, float)
```

- [ ] **Step 2: Implement functions**

Use pure functions only. Do not import FastAPI or SEC client into formula modules.

```python
# backend/app/engine/returns.py
import pandas as pd
from scipy.optimize import brentq


def simple_returns(nav: pd.DataFrame) -> pd.DataFrame:
    return nav.pct_change().dropna(how="any")


def time_weighted_return(period_returns: pd.Series) -> float:
    return float((1 + period_returns).prod() - 1)


def money_weighted_return(cashflows: list[tuple[float, float]]) -> float | None:
    def npv(rate: float) -> float:
        return sum(amount / ((1 + rate) ** period) for period, amount in cashflows)
    try:
        return float(brentq(npv, -0.999, 10.0))
    except ValueError:
        return None
```

```python
# backend/app/engine/metrics.py
import numpy as np
import pandas as pd


def annualized_return(returns: pd.Series, periods_per_year: int) -> float:
    years = len(returns) / periods_per_year
    return float((1 + returns).prod() ** (1 / years) - 1)


def annualized_volatility(returns: pd.Series, periods_per_year: int) -> float:
    return float(returns.std(ddof=0) * np.sqrt(periods_per_year))


def max_drawdown(values: pd.Series) -> float:
    return float((values / values.cummax() - 1).min())


def beta_alpha(portfolio: pd.Series, benchmark: pd.Series, risk_free_rate: float, periods_per_year: int) -> tuple[float, float]:
    aligned = pd.concat([portfolio, benchmark], axis=1).dropna()
    aligned.columns = ["portfolio", "benchmark"]
    beta = float(aligned["portfolio"].cov(aligned["benchmark"]) / aligned["benchmark"].var(ddof=1))
    port_cagr = annualized_return(aligned["portfolio"], periods_per_year)
    bench_cagr = annualized_return(aligned["benchmark"], periods_per_year)
    alpha = port_cagr - (risk_free_rate + beta * (bench_cagr - risk_free_rate))
    return beta, float(alpha)
```

- [ ] **Step 3: Verify**

Run:

```bash
pytest backend/tests/test_returns.py backend/tests/test_metrics.py -q
```

Expected: PASS.

**User Verification Gate:** Show the exact formula tests and passing result, then ask: `ยืนยันไหมครับว่า Task 6 ผ่านแล้ว ให้ไป Task 7 ต่อ?`

### Task 7: Backtest Engine Using Cached SEC NAV Only

**Files:**
- Create: `backend/app/engine/cashflows.py`
- Create: `backend/app/engine/rebalancing.py`
- Create: `backend/app/engine/backtest.py`
- Create: `backend/tests/test_backtest_engine.py`

**Interfaces:**
- Consumes `BacktestRequest` and cached aligned NAV panel.
- Produces `BacktestResult` with summary, series, events, tables, and quality metadata.

- [ ] **Step 1: Write engine test**

```python
# backend/tests/test_backtest_engine.py
import pandas as pd
from backend.app.domain.schemas import BacktestRequest
from backend.app.engine.backtest import run_backtest


def test_sec_nav_backtest_with_monthly_dca():
    request = BacktestRequest(
        objective="monthly_dca",
        assets=[{"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50}, {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50}],
        start_date="2020-01-31",
        end_date="2020-04-30",
        initial_capital=1000,
        benchmark_proj_id="FUND_A",
        cashflow={"enabled": True, "type": "contribution", "amount": 100, "frequency": "monthly", "timing": "end"},
        rebalancing={"mode": "monthly"},
        costs={"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
        data={"source": "sec_open_data", "price_field": "nav_per_unit"},
    )
    nav = pd.DataFrame({"FUND_A": [10, 11, 9.9, 12], "FUND_B": [20, 21, 18.9, 22]}, index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"]))
    result = run_backtest(request, nav)
    assert result["summary"]["ending_value"] > 0
    assert result["summary"]["cashflow_count"] == 3
    assert result["summary"]["rebalance_count"] == 3
```

- [ ] **Step 2: Implement cashflow/rebalancing/backtest**

The engine must:

- Allocate initial capital by target weights.
- Convert NAV changes into fund returns.
- Apply scheduled contributions/withdrawals.
- Apply monthly/quarterly/annual rebalancing.
- Deduct transaction/slippage costs when rebalancing.
- Use benchmark fund `benchmark_proj_id` from SEC NAV panel.
- Produce no mock values.

- [ ] **Step 3: Verify**

Run:

```bash
pytest backend/tests/test_backtest_engine.py -q
python - <<'PY'
import pandas as pd
from backend.app.sec.cache import load_nav_panel
from backend.app.data.quality import align_nav_panel
from backend.app.domain.schemas import BacktestRequest
from backend.app.engine.backtest import run_backtest

universe = pd.read_csv("data/sec/mvp_fund_universe.csv")
proj_ids = universe["proj_id"].tolist()
nav = align_nav_panel(load_nav_panel(proj_ids))
request = BacktestRequest(
    objective="past_performance",
    assets=[{"proj_id": proj_ids[0], "display_name": universe.iloc[0]["display_name"], "weight": 50}, {"proj_id": proj_ids[1], "display_name": universe.iloc[1]["display_name"], "weight": 50}],
    start_date=str(nav.index.min().date()),
    end_date=str(nav.index.max().date()),
    initial_capital=100000,
    benchmark_proj_id=proj_ids[0],
    cashflow={"enabled": False, "type": "contribution", "amount": 0, "frequency": "monthly", "timing": "end"},
    rebalancing={"mode": "annual"},
    costs={"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
    data={"source": "sec_open_data", "price_field": "nav_per_unit"},
)
result = run_backtest(request, nav)
print(result["summary"])
PY
```

Expected:

- Unit test passes.
- Real SEC cached NAV produces a non-empty summary.
- No mock/random/sample data is used.

**User Verification Gate:** Show the real SEC backtest summary to the user and ask: `ยืนยันไหมครับว่า Task 7 ผ่านแล้ว ให้ไป Task 8 ต่อ?`

### Task 8: Backtest API and SEC Fund API

**Files:**
- Create: `backend/app/api/funds.py`
- Create: `backend/app/api/backtests.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_backtests.py`

**Interfaces:**
- Produces `GET /api/funds` from cached SEC fund universe.
- Produces `POST /api/backtests` using cached SEC NAV only.

- [ ] **Step 1: Write API test**

```python
# backend/tests/test_api_backtests.py
from fastapi.testclient import TestClient
from backend.app.main import app


def test_health_endpoint():
    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
```

- [ ] **Step 2: Implement API**

```python
# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title="SEC Open Data Portfolio Backtester", version="0.1.0")


@app.get("/api/health")
def health():
    return {"status": "ok", "data_source": "sec_open_data"}
```

Backtest route must:

- Reject any `data.source` not equal to `sec_open_data`.
- Load only `data/sec/normalized/daily_nav.parquet`.
- Return quality issues if NAV is missing or too short.
- Persist `request.json` and `result.json` under `data/runs/{run_id}`.

- [ ] **Step 3: Verify**

Run:

```bash
pytest backend/tests/test_api_backtests.py -q
uvicorn backend.app.main:app --reload --port 8000
```

Then in another terminal:

```bash
curl http://localhost:8000/api/health
```

Expected:

```json
{"status":"ok","data_source":"sec_open_data"}
```

**User Verification Gate:** Ask the user to run the health check and one `POST /api/backtests` from the generated API docs at `http://localhost:8000/docs`, then ask: `ยืนยันไหมครับว่า Task 8 ผ่านแล้ว ให้ไป Task 9 ต่อ?`

### Task 9: Production Frontend With SEC Data Only

**Files:**
- Create: `package.json`
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/types/backtest.ts`
- Create: `frontend/src/objectives/objectives.ts`
- Create: `frontend/src/components/FundSelector.tsx`
- Create: `frontend/src/components/PortfolioEditor.tsx`
- Create: `frontend/src/components/AssumptionPanel.tsx`
- Create: `frontend/src/components/RunSummary.tsx`
- Create: `frontend/src/pages/BacktestWorkspace.tsx`
- Create: `frontend/src/styles.css`

**Interfaces:**
- Consumes `GET /api/funds`.
- Consumes `POST /api/backtests`.
- Produces UI matching current mockup flow but using only real API results.

- [ ] **Step 1: Create frontend app**

The UI must:

- Show "SEC Open Data" as data source.
- Show no legacy import controls.
- Show no mock or seeded financial outputs.
- Disable run until at least one SEC fund is selected and weights sum to 100%.
- Preserve objective presets and editable inputs.
- Render all output tabs only after a successful real API response.

- [ ] **Step 2: Add production data-source guard**

In `frontend/src/api/client.ts`, reject any result where `data_source !== "sec_open_data"`:

```ts
export function assertSecOnly(result: unknown) {
  const data = result as { data_source?: string };
  if (data.data_source && data.data_source !== "sec_open_data") {
    throw new Error("Production app accepts SEC Open Data results only.");
  }
}
```

- [ ] **Step 3: Verify**

Run:

```bash
npm --prefix frontend install
npm --prefix frontend run build
npm --prefix frontend run dev
```

Open:

```text
http://localhost:5173
```

Expected:

- Fund selector is populated from cached SEC data through the backend.
- Running a backtest calls the backend and displays real SEC-based results.
- Browser search on the production page finds no `mock` or `seeded`.

**User Verification Gate:** Ask the user to run one objective from the browser and verify the visible result uses SEC fund names/NAV-derived numbers, then ask: `ยืนยันไหมครับว่า Task 9 ผ่านแล้ว ให้ไป Task 10 ต่อ?`

### Task 10: CQF Report and Reproducible Artifacts

**Files:**
- Create: `backend/app/reports/markdown.py`
- Create: `backend/app/reports/artifacts.py`
- Create: `backend/tests/test_report_markdown.py`
- Create: `backend/tests/test_reproducibility.py`
- Create: `scripts/sec_verify_run_reproducibility.py`
- Create: `docs/formula-reference.md`
- Create: `docs/methodology.md`

**Interfaces:**
- Produces report exports from real SEC cached data and run result only.
- Produces `verify_run_reproducibility(run_id: str) -> dict` that reloads the cached request and SEC NAV cache, reruns the backtest, and diffs stored metrics.

- [ ] **Step 1: Write report test**

```python
# backend/tests/test_report_markdown.py
from backend.app.reports.markdown import render_cqf_report


def test_report_mentions_sec_open_data_and_limitations():
    report = render_cqf_report(
        request={"objective": "past_performance", "assets": [{"proj_id": "FUND_A", "weight": 100}]},
        result={"summary": {"ending_value": 1200, "cagr": 0.1, "max_drawdown": -0.2}},
        manifest={"source": "SEC Open Data", "nav_rows": 1000},
        quality_issues=[],
    )
    assert "SEC Open Data" in report
    assert "Formula Reference" in report
    assert "Limitations" in report
```

- [ ] **Step 2: Implement report**

The report must include:

- Objective.
- SEC dataset manifest.
- Selected fund IDs/classes.
- Input assumptions.
- NAV alignment method.
- Cashflow method.
- Rebalancing method.
- Formula reference.
- Performance/risk results.
- Benchmark risk.
- Drawdown stress.
- Diversification check.
- Data quality issues.
- Limitations.

- [ ] **Step 3: Add reproducibility verifier**

```python
# scripts/sec_verify_run_reproducibility.py
import json
import math
import sys
from pathlib import Path
from backend.app.data.quality import align_nav_panel
from backend.app.domain.schemas import BacktestRequest
from backend.app.engine.backtest import run_backtest
from backend.app.sec.cache import load_nav_panel


SUMMARY_KEYS = ["ending_value", "net_invested", "cagr", "volatility", "max_drawdown", "beta", "alpha"]
TOLERANCE = 1e-8


def verify_run_reproducibility(run_id: str) -> dict:
    run_dir = Path("data/runs") / run_id
    request_payload = json.loads((run_dir / "request.json").read_text())
    stored_result = json.loads((run_dir / "result.json").read_text())
    request = BacktestRequest(**request_payload)
    proj_ids = [asset.proj_id for asset in request.assets]
    if request.benchmark_proj_id not in proj_ids:
        proj_ids.append(request.benchmark_proj_id)
    nav = align_nav_panel(load_nav_panel(proj_ids))
    recomputed = run_backtest(request, nav)
    diffs = {}
    for key in SUMMARY_KEYS:
        stored = stored_result["summary"].get(key)
        new = recomputed["summary"].get(key)
        if stored is None or new is None:
            diffs[key] = {"stored": stored, "recomputed": new, "abs_diff": None, "match": stored == new}
            continue
        abs_diff = abs(float(stored) - float(new))
        diffs[key] = {"stored": stored, "recomputed": new, "abs_diff": abs_diff, "match": abs_diff <= TOLERANCE}
    ok = all(item["match"] for item in diffs.values())
    return {"run_id": run_id, "ok": ok, "tolerance": TOLERANCE, "diffs": diffs}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/sec_verify_run_reproducibility.py <run_id>")
    result = verify_run_reproducibility(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(1)
```

```python
# backend/tests/test_reproducibility.py
from scripts.sec_verify_run_reproducibility import SUMMARY_KEYS


def test_reproducibility_summary_keys_are_explicit():
    assert "ending_value" in SUMMARY_KEYS
    assert "max_drawdown" in SUMMARY_KEYS
    assert "alpha" in SUMMARY_KEYS
```

- [ ] **Step 4: Verify report and reproducibility**

Run:

```bash
pytest backend/tests/test_report_markdown.py backend/tests/test_reproducibility.py -q
python - <<'PY'
from pathlib import Path
run_dirs = sorted(Path("data/runs").glob("*"))
print(run_dirs[-1] if run_dirs else "No runs yet")
PY
```

Then export a report from the UI, open the downloaded markdown, and run:

```bash
python scripts/sec_verify_run_reproducibility.py <run_id>
```

Expected:

- Report references SEC Open Data.
- Report contains no mock language.
- Report has formulas and reproducibility artifacts.
- Reproducibility verifier exits with status `0`.
- Verifier output shows `ok: true` and metric diffs within tolerance.

**User Verification Gate:** Ask the user to inspect the exported report and confirm it is acceptable for CQF structure before Task 11: `ยืนยันไหมครับว่า Task 10 ผ่านแล้ว ให้ไป Task 11 ต่อ?`

### Task 11: Production Hardening and Final Runbook

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `docs/user-guide.md`
- Create: `docs/data-policy.md`
- Modify: `README.md`

**Interfaces:**
- Produces final local production run path.

- [ ] **Step 1: Add runbook**

README must include:

```markdown
## Production Local Run

1. Create `.env` with `SEC_API_KEY`.
2. Install backend dependencies.
3. Run `python scripts/sec_capture_contract.py`.
4. Run `python scripts/sec_build_mvp_universe.py`.
5. User verifies `data/sec/mvp_fund_universe.csv`.
6. Run `python scripts/sec_download_mvp.py`.
7. Verify `data/sec/normalized/sec_data_manifest.json` and `data/sec/normalized/nav_request_ledger.parquet`.
8. Start backend with `uvicorn backend.app.main:app --reload --port 8000`.
9. Start frontend with `npm --prefix frontend run dev`.
10. Open `http://localhost:5173`.
```

- [ ] **Step 2: Add final no-mock audit**

Run:

```bash
rg -n "mock|seeded|temporary financial" backend frontend
```

Expected:

- Matches are allowed only in `app/mockup-reference/README.md` or historical notes that are explicitly labeled non-production.
- No production code imports mock data.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
npm --prefix frontend run build
python scripts/sec_capture_contract.py
python scripts/sec_build_mvp_universe.py
python scripts/sec_download_mvp.py
```

Expected:

- Backend tests pass.
- Frontend build passes.
- SEC data downloader refreshes real cached records.
- SEC data manifest has `valid_for_backtest: true`.
- NAV request ledger has no blocking request statuses.

**User Verification Gate:** Ask the user to complete one full browser run and export one report, then ask: `ยืนยันไหมครับว่า Task 11 ผ่านแล้ว จบ production implementation ได้?`

---

## End-to-End Production Flow

1. User keeps old mockup in `app/mockup-reference/` for visual comparison only.
2. User sets `SEC_API_KEY` in `.env`.
3. System authenticates to SEC Open Data.
4. User verifies MVP fund universe from SEC lookup.
5. System downloads all selected funds' daily NAV history from SEC before engine/UI implementation.
6. System writes raw JSON and normalized Parquet files with a manifest.
7. User verifies cached NAV coverage.
8. User opens production frontend.
9. User selects objective preset.
10. User selects SEC funds and weights.
11. User configures date range, benchmark fund, cashflows, rebalancing, costs.
12. UI posts request to backend.
13. Backend loads cached SEC NAV only.
14. Backend validates NAV quality and aligns observations.
15. Engine calculates returns, cashflows, rebalancing, metrics, drawdowns, benchmark risk, diversification.
16. Backend saves run artifacts.
17. UI renders all output tabs.
18. User exports CQF report and JSON artifacts.

---

## Acceptance Criteria

- Production app has no mock financial values.
- Production app uses SEC Open Data only.
- SEC data is pulled and cached before real backtest engine implementation proceeds.
- SEC NAV download records request status in `nav_request_ledger.parquet` and treats rate limits/network/server/auth failures as blocking.
- User can verify and confirm after every task before the next task starts.
- Backtests use SEC daily NAV `last_val` normalized as `nav_per_unit`.
- Every result can be reproduced from SEC cached files, request JSON, result JSON, and formula docs.
- `scripts/sec_verify_run_reproducibility.py <run_id>` exits with status `0` for accepted production runs.
- Four objective presets remain available.
- Always-on outputs remain available after every successful run.
- CQF report cites SEC Open Data as source and explains formulas, assumptions, limitations, and data quality.

## Self-Review

**Spec coverage:** The revised plan separates mockup from production, makes SEC Open Data the only source, requires full data pull before engine/UI, and adds user verification gates to every task.

**Temporary-data scan:** Production tasks contain no generated financial results. Task 3 builds the fund universe from authenticated SEC search results before any NAV download.

**Type consistency:** The production domain uses `proj_id`, `benchmark_proj_id`, `sec_open_data`, and `nav_per_unit` consistently across backend, frontend, data cache, and report tasks.
