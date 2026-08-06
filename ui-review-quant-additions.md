# UI Review And Quant-Grade Additions

Created: 2026-07-27

Reviewed artifact:

- `Clean portfolio backtesting workspace.zip`
- Extracted files inspected:
  - `Portfolio Backtester.dc.html`
  - `backtestEngine.js`
  - `formulas.js`
  - `.thumbnail`

Review goal: check whether the current UI design has the right portfolio-backtesting inputs/outputs, identify incorrect or misleading parts, and recommend additional professional quant-grade charts, parameters, and report outputs.

## Verdict

The current UI is a strong first prototype for the requested scope. It correctly stays focused on Portfolio Backtesting and already includes the major workflow pieces: portfolio input, benchmark, cashflows, rebalancing, dividends/cost assumptions, results tabs, formula drawer, and export files.

However, it is not yet quant-grade because the prototype mixes real backtest language with synthetic illustrative data, and some calculations/labels would mislead users if treated as actual historical backtest results. The next design pass should keep the layout, but tighten methodology, add missing professional diagnostics, and make data/source assumptions unavoidable.

Verdict: fix-then-ship for design; do not use as methodology/code reference yet.

## What Is Already Correct

| Area | Status | Evidence |
|---|---|---|
| Scope | Correct: no Monte Carlo or Optimization tab appears in the app tabs. | `Portfolio Backtester.dc.html` defines tabs as Overview, Growth, Drawdown, Returns, Metrics, Cashflows, Rebalancing, Report. |
| Workspace-first UI | Correct: opens directly into app workspace with portfolio panel and result tabs, not a marketing page. | Header/actions and left input panel appear immediately. |
| Portfolio input | Mostly correct: ticker/weight rows, add/remove asset, normalize weights, allocation bar, duplicate/empty/weight validation. | `Portfolio Backtester.dc.html` portfolio section and validation logic. |
| Backtest assumptions | Mostly correct: start/end date, initial capital, benchmark, max overlapping history toggle. | Left settings panel. |
| Cashflows | Good MVP base: enable/disable, contribution/withdrawal, amount, frequency, start/end, beginning/end timing. | Cashflow schedule panel. |
| Rebalancing | Good MVP base: none/monthly/quarterly/annual. | Rebalancing rule panel. |
| Dividend/cost assumptions | Good MVP base: adjusted close, dividend reinvestment, annual drag, transaction cost bps. | Dividends & costs panel. |
| Results structure | Correct high-level tabs: overview, growth, drawdown, returns, metrics, cashflows, rebalancing, report. | Result tab definitions. |
| Formula drawer | Correct concept: formulas include variables, interpretation, implementation note, common trap. | `formulas.js`. |
| Export concept | Correct files: report, config, holdings, prices, returns, values, cashflow events, rebalance events, metrics. | Export file list in HTML logic. |

## High-Priority Issues To Fix

### 1. Results look like real historical backtest output, but the engine uses synthetic seeded data

Why it matters: this is the biggest issue. The UI says "Fetching prices" and report says adjusted close / price history, but `backtestEngine.js` generates deterministic random returns from assumed mean/vol profiles. That is fine for a visual prototype, but dangerous for a CQF project if not clearly separated from the real implementation.

Evidence:

- `backtestEngine.js` lines 1-2 state the engine is illustrative and not real market data.
- `backtestEngine.js` lines 32-39 use fixed assumed mean/vol per ticker.
- `Portfolio Backtester.dc.html` line 362 includes "Fetching prices" in progress, but no real fetch occurs.
- Report text says "price history -> adjusted price series" in methodology even though no prices are loaded.

Suggested change:

- In UI prototype: rename progress step to "Generating sample series" until real data exists.
- In real build: add a data-source layer before any metric claim is allowed.
- Add a visible `Data source` control/status: `Sample data`, `Uploaded CSV`, `Yahoo/Stooq/etc.`.

### 2. Cashflow runs report total return and CAGR in a misleading way

Why it matters: with contributions/withdrawals, ending value divided by initial capital is not a meaningful investment return. It blends investment performance with external deposits. This is exactly why the brief asks for TWRR/MWRR distinction.

Evidence:

- `backtestEngine.js` lines 122-123 compute CAGR from `endingValue / initialCapital`.
- `backtestEngine.js` lines 181-182 compute total return and CAGR the same way even when cashflows exist.
- `formulas.js` line 15 says full MWRR/IRR is phase 2.

Suggested change:

- If cashflows are enabled, label current dollar output as `Ending value`, not performance return.
- Add separate metrics:
  - `Net invested capital`
  - `Net profit`
  - `TWRR`
  - `MWRR / IRR`
  - `Ending value / net invested`, labelled as a simple dollar multiple, not CAGR.
- Hide or caveat CAGR unless computed from a cashflow-neutral return stream.

### 3. `Use adjusted close` and `Reinvest dividends` do not affect the engine

Why it matters: users can toggle assumptions that do not change results. That creates false confidence and weakens the CQF explanation.

Evidence:

- UI exposes `Use adjusted close` and `Reinvest dividends`.
- `buildEngineInput()` only passes portfolio, benchmark, dates, capital, rebalance, cashflow, annual drag, and transaction cost.
- `useAdjClose` and `reinvestDividends` are not included in engine input.

Suggested change:

- For visual prototype: mark these as disabled/sample-only or include them in the run config and report as non-operational.
- For real build: data loader must explicitly choose adjusted close / total return series, and dividend reinvestment should be modeled only if dividend event data is available.

### 4. Rebalancing events are random, not calculated from asset-level portfolio drift

Why it matters: the Rebalancing tab currently looks professional, but the before/after weights are random. A real rebalance table must come from simulated holdings or asset value weights.

Evidence:

- `backtestEngine.js` lines 102-114 generate `drift` and `before` weights using random numbers rather than asset-level price paths.

Suggested change:

- Real engine should track per-asset shares/value:
  - start with target weights
  - update each asset value using its own return
  - compute drifted weights before rebalance
  - trade back to target weights
  - record turnover/cost/trades

### 5. Export report button does not export from the header

Why it matters: the top action says "Export report", but it only navigates to the Report tab. That is a UI contract mismatch.

Evidence:

- Header `Export report` calls `goToReport`.
- Actual downloads appear as separate buttons inside the Report tab.

Suggested change:

- Rename header button to `View report`, or make it open a menu with `report.md`, `run_config.json`, `All files`.

### 6. Validation is missing date/capital/cashflow sanity checks

Why it matters: quant tools fail silently when dates and amounts are invalid. The current validation covers weights, empty tickers, duplicates, and asset count, but not enough for backtesting.

Evidence:

- Validation logic checks weights, empty ticker, duplicate ticker, and empty portfolio.
- No check for start date after end date, zero/negative capital, negative cashflow amount, cashflow dates outside run, invalid benchmark, or missing engine/data source.

Suggested change:

Add validation:

- start date < end date
- initial capital > 0
- benchmark non-empty and not duplicated ambiguously
- cashflow amount >= 0
- cashflow start/end inside backtest window or visibly clipped
- rebalance frequency compatible with data frequency
- no negative weights in MVP

## Medium-Priority UI/UX Issues

| Issue | Why It Matters | Suggested Change |
|---|---|---|
| Overview metric cards visually collide in the thumbnail. | Screenshot shows values/units overlapping, especially Total Return/CAGR/Volatility. | Reduce overview density, use 3-column grid on medium widths, or make metric cards taller. |
| No axis labels or y-axis scale on charts. | A quant user needs units and scale. | Add y-axis labels, hover/tooltips, and start/end/peak labels. |
| Monthly heatmap cells have no visible month labels. | Good for compactness, weak for report readability. | Add month header row and color legend. |
| No asset allocation chart after results. | Users need to see target allocation and drift. | Add target allocation chart and optional final allocation chart. |
| No data quality panel. | Backtests are only as credible as data alignment. | Add Data Quality tab/section: ticker coverage, missing dates, overlap window, adjusted-close basis. |
| No report download as one package. | CQF submission benefits from bundled reproducibility. | Add `Download all` zip action in Report tab. |
| No settings for risk-free rate. | Sharpe/alpha currently hard-code 2% annual risk-free rate. | Add risk-free input/source. |
| No slippage input. | Brief mentioned transaction cost/slippage separately. | Add slippage bps or combine under "Trading cost model" with clear formula. |

## Quant-Grade Additions Recommended

### A. Add Professional Charts

| Chart | Priority | Why Add It | Source Support |
|---|---:|---|---|
| Cumulative return / growth of initial capital | Must | Already present; keep as primary chart. | Portfolio Visualizer, QuantStats, QuantConnect |
| Drawdown / underwater chart | Must | Already present; core risk diagnostic. | Portfolio Visualizer, QuantStats, QuantConnect |
| Annual returns table | Must | Already present; useful for CQF report. | PortfolioBacktest.com, PortfolioMetrics |
| Monthly returns heatmap | Must | Already present; improve labels/legend. | QuantStats, PortfolioMetrics |
| Rolling 12-month return | Should | Shows regime behavior, not just full-period average. | PortfolioMetrics and pfolio discuss rolling metrics. |
| Rolling volatility | Should | Shows changing risk through time. | QuantStats and PortfolioMetrics list rolling volatility. |
| Rolling Sharpe / Sortino | Should | Shows risk-adjusted performance stability. | QuantStats and PortfolioMetrics list rolling Sharpe/Sortino. |
| Rolling beta vs benchmark | Should | Shows benchmark sensitivity over time. | QuantStats, PortfolioMetrics, jQuantStats list rolling beta/Greeks. |
| Return distribution histogram | Should | Shows skew, tails, outliers, and non-normality. | QuantStats has histogram/distribution plots. |
| Drawdown periods table | Should | Shows worst drawdowns, start date, trough, recovery date, duration. | QuantStats has drawdown periods; QuantConnect has drawdown recovery. |
| Correlation matrix | Should | Shows asset diversification and benchmark relationship. | PortfolioMetrics includes correlations/covariance; testfol.io includes correlation/beta matrices. |
| Asset allocation target vs final/drift | Should | Rebalancing explanation needs before/after allocation. | Portfolio Performance and Stoculator expose allocation views. |
| Turnover and cost-drag chart | Could | Shows impact of rebalancing/cost assumptions. | testfol.io documents turnover/tax/cost outputs. |
| Net invested vs portfolio value | Must when cashflows on | Already present; keep and label clearly. | testfol.io cashflow-aware value path. |
| Cashflow timeline | Should | Helps users understand DCA/withdrawal timing. | Stoculator timeline reference. |

### B. Add Professional Metrics

Current prototype has:

- Ending value
- Total return
- CAGR
- Volatility
- Sharpe
- Sortino
- Calmar
- Max drawdown
- Beta
- Alpha
- Tracking error
- Information ratio
- Correlation
- Turnover/rebalance count
- Cashflow totals

Recommended additions:

| Metric | Priority | Why Add It | Source Support |
|---|---:|---|---|
| TWRR | Must if cashflows exist | Separates strategy performance from investor cash timing. | Portfolio Performance, testfol.io |
| MWRR / IRR | Should | Shows actual investor dollar experience with cashflows. | Portfolio Performance, testfol.io |
| Net profit | Must | Easier for general users than total return when cashflows exist. | Practical reporting need |
| Drawdown duration / recovery time | Should | Max drawdown magnitude alone misses time-under-water. | QuantConnect drawdown recovery; QuantStats drawdown periods |
| Average drawdown | Should | More stable risk picture than one max event. | testfol.io metrics |
| Ulcer Index | Should for quant-grade | Captures depth and duration of drawdowns. | testfol.io and QuantStats |
| Ulcer Performance Index | Could | Return per unit of ulcer risk. | testfol.io and QuantStats |
| VaR 95/99 | Could | Standard risk metric; caveat normal/historical method. | QuantConnect, empyrical, jQuantStats |
| CVaR / Expected Shortfall | Could | Better tail-loss measure than VaR. | empyrical, jQuantStats |
| Skewness / kurtosis | Could | Shows non-normal return behavior. | empyrical/QuantStats |
| Tail ratio | Could | Upside-tail vs downside-tail balance. | empyrical/QuantStats |
| Up/down capture ratios | Could | Shows behavior in benchmark up/down periods. | empyrical |
| Treynor ratio | Could | Excess return per unit of beta risk. | QuantConnect |
| R-squared | Could | How much benchmark explains portfolio movement. | QuantStats/jQuantStats |
| Best/worst rolling period | Should | More robust than only best/worst month/year. | Rolling metrics sources |

### C. Add Professional Parameters

| Parameter | Priority | Why Add It |
|---|---:|---|
| Data source selector | Must | Real vs sample/uploaded/vendor data must be explicit. |
| Price basis | Must | Adjusted close / raw close / total-return series. |
| Data frequency | Should | Daily vs monthly affects annualization, beta, rolling metrics. |
| Risk-free rate | Must | Sharpe, Sortino, alpha, Treynor depend on it. |
| Benchmark initial cashflow treatment | Should | Decide whether benchmark receives same contributions/withdrawals. |
| Cashflow allocation method | Should | Target weights, proportional, underweight-only, cash sleeve. |
| Rebalance timing | Should | Beginning/end of period; before/after cashflow. |
| Rebalance offset | Could | Last trading day vs nth trading day before period-end. |
| Rebalance bands | Should | Absolute/relative drift thresholds. |
| Slippage bps | Should | Separate from commission/transaction cost. |
| Minimum trade size | Could | Prevents unrealistic tiny rebalances. |
| Whole shares only | Could | Practical brokerage realism. |
| Reporting currency | Could | Prevents mixed-currency confusion. |
| Inflation adjustment | Could | Useful for long-horizon withdrawal analysis. |
| Missing data handling | Must | Drop asset, forward-fill, overlap-only, or fail run. |
| Corporate action handling | Must in real build | Splits/dividends can materially alter returns. |

### D. Add Report Sections

Current report is a good start but should add:

- Data quality and coverage table
- Backtest configuration table
- Price basis and corporate-action assumption
- Cashflow methodology
- Rebalancing methodology
- Annualization convention
- Risk-free-rate convention
- Benchmark construction and cashflow treatment
- Metric definitions table
- Chart appendix
- Reproducibility appendix
- Known limitations and bias checklist

## Research Findings

| Claim | Source | Confidence |
|---|---|---|
| Professional backtest statistics commonly include Sharpe, Sortino, alpha, beta, annual standard deviation/variance, information ratio, tracking error, Treynor ratio, portfolio turnover, VaR, and drawdown recovery. | QuantConnect backtest statistics docs: https://www.quantconnect.com/docs/v2/cloud-platform/api-reference/backtest-management/read-backtest/backtest-statistics | High |
| A portfolio backtester can expose rebalancing events, cashflow events, average turnover per rebalance, turnover per year, correlation/beta matrices, and tax/cost drag outputs. | testfol.io help: https://testfol.io/help | High |
| Quant-focused reports commonly include metrics, plots, and HTML tear sheets; chart families include returns, drawdowns, rolling statistics, monthly heatmaps, histograms, and yearly returns. | QuantStats GitHub: https://github.com/ranaroussi/quantstats | High |
| Common performance/risk metric libraries include annual return/CAGR, annual volatility, Sharpe, Calmar, max drawdown, Omega, Sortino, skew, kurtosis, tail ratio, VaR, CVaR, alpha, beta, and capture ratios. | empyrical docs/GitHub: https://github.com/quantopian/empyrical and https://empyrical.ml4trading.io/stats.html | High |
| Portfolio analytics should distinguish metric types: daily return distribution metrics, price-point metrics, and rolling metrics. Rolling metrics help explore trends through time. | pfolio help: https://www.pfolio.io/help/time-series-data-and-metric-types | High |
| Interactive dashboards for portfolio analytics often include cumulative returns, drawdowns, monthly heatmaps, rolling beta, rolling volatility, correlations, covariance, return quantiles, and asset allocation views. | PortfolioMetrics backtesting page: https://portfoliometrics.net/backtesting | Medium - source also includes Monte Carlo/optimization modules, but cited only for backtesting chart families. |
| Portfolio-native analytics benefit from turnover, cost modeling, cost-impact sweeps, and interactive self-contained reports. | jQuantStats GitHub: https://github.com/tschm/jquantstats | Medium - newer library, but claims align with quant workflow needs. |

## Recommended Next UI Revision

### Keep

- Current workspace layout.
- Left assumptions panel.
- Eight result tabs.
- Formula drawer.
- Report export concept.
- Cashflow and rebalancing as first-class settings.

### Change

1. Add a `Data` section above Backtest Settings:
   - Source: Sample / Uploaded CSV / Price API.
   - Price basis: Adjusted close / raw close.
   - Frequency: Daily / monthly.
   - Coverage status.

2. Add a `Risk-free rate` field:
   - Manual annual rate.
   - Default visibly stated.

3. Expand Rebalancing advanced settings:
   - Timing: before/after cashflow.
   - Offset.
   - Bands: absolute/relative drift.
   - Min trade size.

4. Add a `Data Quality` view:
   - Ticker coverage start/end.
   - Missing prices.
   - Effective overlapping date range.
   - Benchmark coverage.
   - Corporate-action/adjusted-price status.

5. Add chart tabs or sub-tabs:
   - Rolling Metrics: rolling return, volatility, Sharpe, beta.
   - Distribution: return histogram, quantiles, skew/kurtosis.
   - Correlation: asset/benchmark correlation matrix.
   - Drawdown Details: worst drawdown periods table.

6. Fix overview responsiveness:
   - 4 columns only on wide screens.
   - 2 columns on medium.
   - 1 column on mobile.
   - Prevent value/unit overlap.

7. Rename or rewire export action:
   - `View report` if it navigates.
   - `Export` if it downloads.

## Minimum Quant-Professional MVP

If keeping scope tight, this is the minimum next target:

Inputs:

- Tickers/weights
- Data source
- Price basis
- Start/end
- Initial capital
- Benchmark
- Risk-free rate
- Cashflow schedule
- Rebalance frequency
- Rebalance timing
- Transaction cost/slippage

Outputs:

- Growth chart
- Drawdown chart
- Annual returns table
- Monthly returns heatmap
- Metrics table
- Cashflow event table
- Rebalance event table
- Data quality table
- Formula drawer
- Report export

Quant-grade additions for first serious version:

- TWRR and MWRR/IRR when cashflows exist
- Rolling 12-month return/volatility/Sharpe/beta
- Return distribution histogram and quantiles
- Worst drawdown periods table with recovery duration
- Correlation matrix
- Turnover and cost-drag summary

## Final Recommendation

Do not redesign from scratch. The structure is right. Make the next pass a methodology-hardening pass:

1. Replace synthetic engine language with explicit sample/prototype labeling.
2. Add data-source and data-quality UX.
3. Fix cashflow return reporting.
4. Add rolling/distribution/correlation/drawdown-detail diagnostics.
5. Tighten report export and formula definitions.

After those changes, the UI will be much closer to a professional quant backtesting workspace while staying within the Portfolio Backtesting-only scope.
