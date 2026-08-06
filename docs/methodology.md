# SEC Open Data Portfolio Backtester Methodology

This document describes the production backtesting workflow used by the application. The system is intentionally SEC-only: all portfolio return, benchmark, risk, and report outputs are derived from cached SEC Open Data mutual-fund NAV files.

## 1. Data Source

- Source: SEC Open Data API.
- Local normalized file: `data/sec/normalized/daily_nav.parquet`.
- Dataset manifest: `data/sec/normalized/sec_data_manifest.json`.
- Primary identifier: `proj_id`.
- Price field: NAV per unit.

The downloader stores raw/normalized SEC data before the frontend backtest runs. A production result should be traceable to the cached SEC files and the exact `request.json` persisted for the run.

## 2. Portfolio Definition

The user selects SEC funds and assigns target weights. Required portfolio inputs are:

- SEC funds and weights.
- Start date.
- End date.
- Initial capital.
- Benchmark fund.

Optional assumptions are:

- Cashflows: recurring contribution or withdrawal with a selected frequency and timing.
- Costs: transaction cost, slippage, and annual drag.
- Rebalancing mode.
- Risk-free rate for Sharpe and alpha-style interpretation.

Weights are treated as target allocation percentages and should sum to 100%.

## 3. NAV Alignment

Daily SEC NAV observations are loaded from the local normalized cache and aligned into a portfolio panel:

1. Filter to the selected funds plus benchmark fund.
2. Resample and align the complete selected-fund cache to the application analysis frequency, currently month-end.
3. If the final cache resampling label falls after its latest observed NAV date, relabel that final row to the latest observed date.
4. Slice the aligned panel to the requested date range and record quality issues when data is missing, sparse, or insufficient.
5. The engine slices the same aligned panel for calculation and rejects the calculation if a selected asset has a missing NAV period or an internal calendar month is absent.

This avoids compressing time, skipping scheduled cashflows, or mixing unmatched selected-fund periods in portfolio-level metrics. Benchmark gaps remain missing and are excluded from matched-period comparisons. A requested end date before the cache's final incomplete period does not independently create or cap a partial month-end row.

## 4. Return Calculation

Fund period returns are calculated from NAV:

```text
r_t = NAV_t / NAV_{t-1} - 1
```

Missing NAV observations are not forward-filled when calculating returns, so a missing period and the return immediately following it remain unavailable for comparison.

Portfolio time-weighted returns are calculated from the simulated portfolio path after market moves, costs, and rebalancing. External cashflows are removed from the period-performance return using the configured timing, so contributions and withdrawals do not themselves create investment returns.

## 5. Cashflow Treatment

When recurring cashflows are enabled:

- Contributions add cash at the selected monthly, quarterly, or annual schedule and beginning/end-of-period timing.
- Withdrawals remove cash at the selected schedule and timing, capped at the portfolio value available when they are applied.
- Total contributed and total withdrawn are reported separately.
- TWRR is kept separate from net invested capital so contribution size does not masquerade as investment skill.

Cashflows are practical user assumptions, not market forecasts.

## 6. Rebalancing

If rebalancing is disabled, holdings drift naturally with realized fund returns. If rebalancing is enabled, holdings are reset toward target weights at the configured schedule.

The rebalancing report section should show:

- Rebalance count.
- Turnover or trade activity when available.
- Cost impact.
- Difference between drifted and rebalanced outcomes where the selected objective is Rebalancing Impact.

## 7. Costs

The model supports:

- Transaction cost in basis points.
- Slippage in basis points.
- Annual drag as a percentage.

Costs are deducted from the simulated portfolio path and reported as `total_costs`.

## 8. Benchmark Risk

Benchmark comparison uses the selected SEC benchmark fund. The benchmark curve starts on the same first NAV date and at the same initial-capital value as the portfolio equity curve, then compounds benchmark NAV returns without portfolio cashflows or trading costs. Benchmark-relative metrics align benchmark and cashflow-neutral portfolio returns by date. The report includes:

- Benchmark excess return.
- Beta.
- Alpha.
- Tracking error.
- Information ratio when available.

These measures explain whether the portfolio return came with more or less benchmark-relative risk.

## 9. Drawdown Stress

Drawdown analysis covers historical maximum drawdown and simple stress shocks. The standard report includes:

- Maximum drawdown.
- Estimated value after -10%, -20%, and -35% shocks.
- Value after repeating the historical maximum drawdown.

This section is meant to answer "how bad could this have felt?" in plain portfolio terms.

## 10. Diversification Check

Diversification output should summarize concentration and relationships among selected funds. Depending on available data, this can include:

- Fund weights.
- Contribution to portfolio risk.
- Correlation to portfolio or benchmark.
- Concentration warnings.

This is a diagnostic, not an optimizer.

## 11. Reproducibility

Every persisted run stores:

- `data/runs/<run_id>/request.json`
- `data/runs/<run_id>/result.json`
- `data/runs/<run_id>/cqf_report.md` after report generation

The reproducibility verifier reruns the current engine from `request.json` and the current local normalized SEC NAV cache, then compares selected summary outputs with the saved `result.json` using a tolerance of `1e-8`. It does not restore the NAV-cache snapshot, dependency versions, engine version, or report output that existed when the run was created.

Run it from the project root after installing the Python dependencies and ensuring `data/sec/normalized/daily_nav.parquet` is available. No SEC API key is required to verify an already cached run.

```bash
python3 scripts/sec_verify_run_reproducibility.py <run_id>
```

A passing verifier means the selected saved summary metrics can be regenerated by the current local engine from the recorded request and current local NAV cache. It is not proof that every saved artifact or the original execution environment has been reproduced bit-for-bit.

## 12. Limitations

This system is historical portfolio backtesting only. It is not a forecast, recommendation engine, tax calculator, broker execution simulator, or suitability assessment. Results depend on SEC NAV availability and the assumptions in the saved request.
