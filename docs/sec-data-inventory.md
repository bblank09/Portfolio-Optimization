# SEC Data Inventory

## Contract Capture

- Source: `backend/tests/fixtures/sec/contract/fund_profiles_SET.json`
- Source: `backend/tests/fixtures/sec/contract/daily_nav_sample.json`
- Contract notes: see `docs/sec-api-contract.md`

## MVP Datasets

1. Fund profile metadata
   - Endpoint: `GET /v2/fund/general-info/profiles`
   - Purpose: fund lookup, class handling, product display, and policy context.
   - Field map copied from real contract capture: `proj_id`, `unique_id`, `proj_abbr_name`, `proj_name_th`, `proj_name_en`, `fund_class_name`, `fund_class_description`, `policy_desc`, `fund_status`, `init_date`, `regis_date`, `cancel_date`.

2. Fund daily NAV
   - Endpoint: `GET /v2/fund/daily-info/nav`
   - Purpose: historical backtest value series.
   - Field map copied from real contract capture: `proj_id`, `unique_id`, `fund_class_name`, `nav_date`, `last_val`, `net_asset`, `sell_price`, `buy_price`, `last_upd_date`.

## Missing Data Classification

- `success`: response returned at least one NAV record.
- `empty_response`: SEC returned a successful response with no records for the requested fund/date range.
- `rate_limited`: SEC returned 429 and retry budget was exhausted.
- `auth_error`: SEC returned 401 or 403.
- `server_error`: SEC returned 5xx and retry budget was exhausted.
- `network_error`: request failed after retry budget.
- `http_error`: SEC returned another non-success HTTP status.

Runs with `rate_limited`, `auth_error`, `server_error`, `network_error`, or `http_error` in the ledger are not valid for production backtesting until resolved.
