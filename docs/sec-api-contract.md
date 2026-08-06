# SEC API Contract Capture

## Fund Profiles
- Endpoint: `GET /v2/fund/general-info/profiles`
- Query params: `{"project_info": "SET", "page_size": 5}`
- Response type: `dict`
- Top-level fields: `['items', 'message', 'next_cursor', 'page_size']`
- Observed item fields: `['cancel_date', 'comp_name_en', 'comp_name_th', 'exchange_rate_protection_policy', 'feederfund_country', 'feederfund_master_fund', 'fund_class_description', 'fund_class_detail', 'fund_class_isin_code', 'fund_class_name', 'fund_class_tax_incentive_type', 'fund_status', 'init_date', 'invest_country_flag', 'investment_policy_desc', 'last_upd_date', 'management_style', 'policy_desc', 'proj_abbr_name', 'proj_id', 'proj_name_en', 'proj_name_th', 'proj_retail_type', 'proj_term_day', 'proj_term_flag', 'proj_term_month', 'proj_term_year', 'regis_date', 'regis_id', 'unique_id']`
- First observed proj_id: `M0209_2548`

## Daily NAV
- Endpoint: `GET /v2/fund/daily-info/nav`
- Query params: `{"proj_id": "M0004_2559", "start_nav_date": "2023-07-13", "end_nav_date": "2023-07-13", "page_size": 5}`
- Response type: `dict`
- Top-level fields: `['items', 'message', 'next_cursor', 'page_size']`
- Observed item fields: `['buy_price', 'buy_swap_price', 'fund_class_name', 'last_upd_date', 'last_val', 'nav_date', 'net_asset', 'proj_id', 'sell_price', 'sell_swap_price', 'unique_id']`
- Record count: `1`