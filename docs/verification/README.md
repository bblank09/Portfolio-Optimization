# Manual Verification Sample — Phase 4.3/4.4

This folder holds the real backtest runs used for the manual Excel
cross-check in item 4.4 (calculate every metric independently in Excel,
compare to the app's output to 6 decimal places).

Two runs are provided because one run alone can't exercise every tab: a run
with cashflow/rebalancing disabled leaves the Cashflows and Rebalancing tabs
empty, so there is nothing in them to check. Run 2 exists specifically to
give those two tabs real, non-zero, traceable numbers.

## Run 1 — base case (Summary, Growth, Drawdown, Returns, Metrics)

- **Portfolio**: K-SET50 (`M0209_2548`) 60%, M-S50 (`M0155_2547`) 40%
- **Benchmark**: K-SET50
- **Period**: 2023-01-31 to 2023-05-31 (4 monthly return periods — short on
  purpose, so every number can be traced back to 5 NAV points per fund by hand)
- **Initial capital**: 100,000; **risk-free rate**: 2%/yr
- **No cashflow, no rebalancing, no transaction costs** — kept off so the
  first manual pass isn't also debugging cashflow/rebalancing timing at the
  same time.
- **Run ID**: `run_20260802_031617_66dd285d`
- Files: `4.3-request.json`, `4.3-result.json`, `4.3-report.md`,
  `4.3-raw-nav-inputs.csv` (the 5 month-end NAV-per-unit points per fund,
  pulled directly from `data/sec/normalized/daily_nav.parquet`).
- Covers: Summary, Growth, Drawdown, Returns, Metrics, Benchmark Risk,
  Diversification, Asset Risk and Allocation.
- Known result: the app reports a `short_history` quality warning ("Only 5
  complete observations are available; expected at least 12") — expected
  and correct for a deliberately short window, not an error.

## Run 2 — cashflow + rebalancing (Cashflows, Rebalancing tabs)

Same portfolio, benchmark, period, capital, and risk-free rate as Run 1,
plus:

- **Cashflow**: enabled, contribution of 2,000, monthly, applied at end of period
- **Rebalancing**: monthly mode (rebalances back to 60/40 every period)
- **Costs**: 5 bps transaction + 5 bps slippage (so rebalance cost is
  non-zero and worth checking by hand, not just turnover)
- **Run ID**: `run_20260802_033353_9ce1844c`
- Files: `4.3b-request.json`, `4.3b-result.json`, `4.3b-report.md`
- Result has real data in every relevant tab:
  - 4 cashflow events, 2,000 each → `total_contributed = 108,000`
    (100,000 initial + 4 × 2,000)
  - 4 rebalance events with real turnover and cost figures — smallest at
    2023-02-28 (turnover ≈ 0.0000692, cost ≈ 0.0069), largest at
    2023-05-31 (turnover ≈ 0.006353, cost ≈ 0.6436), growing each month as
    the two funds' returns diverge more and the 60/40 target drifts further
    before each correction.
  - `total_costs = 0.7053307147697524` (sum of all 4 rebalance costs; no
    annual drag configured, so this is 100% rebalance cost)
- Covers: Cashflow Accounting (`total_contributed`/`total_withdrawn`) and
  Rebalance Turnover and Cost, in addition to everything Run 1 covers
  (all Summary/Metrics figures naturally shift slightly because of the
  added contributions and cost drag).

## Files

Both runs were executed against the real running app (`uvicorn`) hitting
the real cached SEC NAV data — not synthetic fixtures — and are also
persisted by the app itself under `data/runs/<run_id>/`; the copies here
are for convenience while building the Excel sheet.
