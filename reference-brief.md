# Portfolio Backtesting Web App - Focused Reference Brief

Created: 2026-07-27

Scope: Portfolio Backtesting only.

Out of scope for this brief:

- Monte Carlo simulation
- Portfolio optimization
- Efficient frontier
- Black-Litterman
- Risk parity / HRP
- Trading execution
- Live broker connection

Those topics may be separate future modules, but this project brief now focuses on one clear deliverable: a web UI that lets users backtest a portfolio from historical data, understand the assumptions, inspect the formulas, compare against a benchmark, and export a coursework-ready report.

## Goal

Build a beginner-friendly but academically defensible portfolio backtesting web app for CQF Module 1-2. The user should be able to enter or import holdings, define a historical period, set cashflow and rebalancing assumptions, run a backtest, inspect performance/risk metrics, and export a reproducible report explaining the data, formulas, code flow, results, and limitations.

## Core User Question

"If I had held this portfolio in the past, with these deposits, withdrawals, dividends, costs, and rebalancing rules, what would have happened?"

The app should answer:

- How much would the portfolio be worth?
- Did it beat the benchmark?
- How much risk did it take?
- How bad was the worst drawdown?
- How did contributions or withdrawals affect the path?
- How often did rebalancing happen?
- What formulas produced the results?
- What assumptions and limitations should be stated in the CQF report?

## Main References

| Reference | Use In This Project | Source |
|---|---|---|
| Portfolio Visualizer | Main scope reference for historical portfolio backtesting, benchmark comparison, metrics, drawdowns, and report-style output. | https://www.portfoliovisualizer.com/analysis |
| testfol.io | Best methodology reference for cashflows, rebalancing timing, rebalance bands, inflation adjustment, TWRR/MWRR distinction, rebalancing events, cashflow events, turnover, and metrics. | https://testfol.io/help |
| Portfolio Performance | Best reference for real portfolio accounting, transaction history, TWRR, IRR, fees, taxes, and why cashflows matter. | https://www.portfolio-performance.info/en/ and https://help.portfolio-performance.info/en/about/ |
| Stoculator | Good UI reference for ticker/weight entry, initial investment, dividend reinvestment, cashflow timeline, contribution, withdrawal, rebalancing, benchmark, and results dashboard. | https://stoculator.com/portfolio-backtesting |
| PortfolioBacktesting.com | Simple reference for DCA/monthly investment, annual rebalancing, S&P 500 comparison, and beginner-facing explanations. | https://www.portfoliobacktesting.com/ |
| Backtest Matrix | Education-friendly workflow reference: upload holdings, run backtest, analyze metrics, compare/export. | https://backtestmatrix.com/ |
| QuantConnect Backtest Results | Professional report layout reference: equity curve, runtime statistics, key statistics, rolling statistics, orders/trades/logs, result files, downloadable reports. | https://www.quantconnect.com/docs/v2/local-platform/backtesting/results |
| Webull CSV export | Practical import reference: Webull supports order history CSV export from mobile and desktop. | https://www.webull.com/help/faq/992-Downloading-your-transaction-history |
| Sharpe article index | Theory reference for Sharpe ratio lineage and risk-adjusted performance evaluation. | https://web.stanford.edu/~wfsharpe/art/art1.htm |
| Fama-French factor definitions | Optional benchmark/factor context only if later needed for alpha/beta explanation. Not MVP core. | https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library/f-f_factors.html |

## Evidence Findings

| Claim | Source | Confidence |
|---|---|---|
| Portfolio backtesting should model a user-defined asset allocation over historical data and compare it against a benchmark. | Portfolio Visualizer reference supplied by user; PortfolioBacktesting.com states users define asset allocation/monthly investment and compare against S&P 500. | High |
| Cashflows are core to realistic backtesting because deposits and withdrawals change portfolio value and require different return interpretation. | testfol.io documents multiple cashflow legs and Portfolio Performance explains why broker/simple spreadsheet returns can be wrong when purchases/sales occur. | High |
| Rebalancing needs more than fixed frequency. Rebalance bands, drift thresholds, offsets, and event tables are useful for realistic and explainable runs. | testfol.io help documents periodic rebalancing, cashflow timing, offsets, absolute/relative rebalance bands, average turnover, and rebalancing events. | High |
| A backtest should distinguish time-weighted style performance from money-weighted/cashflow-aware measures when cashflows exist. | testfol.io states portfolio value chart and MWRR account for cashflows while many other statistics ignore cashflows; Portfolio Performance highlights TWRR and IRR. | High |
| Dividend reinvestment and adjusted-price assumptions should be explicit. | Stoculator supports dividend reinvestment and states calculations use adjusted closing prices; testfol.io documents invest-dividends behavior. | High |
| A beginner-friendly backtester benefits from a visual cashflow/rebalancing timeline. | Stoculator exposes a timeline editor for contribution, withdrawal, and rebalancing events. | High |
| Exportable reports and result files improve reproducibility and coursework value. | QuantConnect documents backtest reports and result files; Backtest Matrix advertises CSV/printable HTML export. | High |
| Webull CSV import should start from official CSV export rather than live brokerage integration. | Webull help documents order history CSV export. | High |

## Product Positioning

This app is not "a trading bot" and not "an optimizer." It is a transparent historical portfolio backtester.

Positioning:

- For students: explain formulas, assumptions, process, and limitations for CQF.
- For general users: understand how their portfolio behaved historically.
- For practical investing review: compare current holdings against a benchmark and test DCA, withdrawals, and rebalancing rules.

## Primary Use Cases

### Use Case 1 - Basic Portfolio Backtest

User story: "I want to know how my portfolio would have performed versus SPY."

Inputs:

- Tickers and weights
- Start date / end date
- Initial capital
- Benchmark ticker
- Rebalancing rule
- Dividend assumption

Outputs:

- Ending value
- Total return
- CAGR
- Volatility
- Sharpe ratio
- Max drawdown
- Portfolio vs benchmark chart
- Annual/monthly return table
- Formula explanations

### Use Case 2 - DCA / Monthly Contribution Backtest

User story: "What if I invested $500 every month into this portfolio?"

Inputs:

- Portfolio tickers and weights
- Initial capital
- Monthly contribution amount
- Contribution start/end date
- Contribution timing
- Rebalancing rule
- Benchmark

Outputs:

- Ending value
- Total contributions
- Net invested capital
- Portfolio value over time
- TWRR-style performance
- MWRR/IRR-style performance if implemented
- Cashflow event table
- Difference between return and dollar outcome

### Use Case 3 - Withdrawal / Decumulation Backtest

User story: "What if I withdrew $1,000 every month from this portfolio?"

Inputs:

- Starting capital
- Withdrawal amount
- Withdrawal frequency
- Withdrawal start/end date
- Rebalancing rule
- Inflation adjustment optional

Outputs:

- Ending value
- Total withdrawals
- Whether portfolio reached zero
- Worst drawdown
- Withdrawal event table
- Portfolio value chart
- Caveat that this is historical backtest, not future guarantee

### Use Case 4 - Webull Portfolio Import

User story: "I exported my Webull order history and want to analyze my real holdings."

Inputs:

- Webull CSV order history
- Optional manual mapping if columns differ
- Benchmark
- Date range

Outputs:

- Normalized holdings / transactions
- Current or reconstructed portfolio
- Backtest result
- Data quality warnings
- Import summary in report

MVP note: if no real Webull sample is available, start with manual ticker/weight input and implement CSV parser after a sample file is provided.

### Use Case 5 - CQF Coursework Report

User story: "I need a report that explains code, formulas, assumptions, process, and limitations."

Outputs:

- Data source section
- Input assumptions
- Price alignment process
- Return calculation formulas
- Portfolio value simulation process
- Rebalancing logic
- Cashflow logic
- Metric formulas
- Result charts/tables
- Limitations and bias discussion
- Reproducibility files

## User Flow

### Step 1 - Start

User opens the app and sees the actual backtesting workspace, not a marketing landing page.

Primary controls:

- Import CSV
- Add Portfolio
- Run Backtest
- Export Report

### Step 2 - Define Portfolio

User can choose:

- Manual input: ticker + target weight
- CSV import: Webull order history or holdings file
- Example preset for demo/coursework

Validation:

- Weights must sum to 100%
- Tickers must have available price history
- Currency mismatch should warn the user
- Missing data should show which ticker/date caused the issue

### Step 3 - Set Backtest Assumptions

User configures:

- Start date
- End date
- Initial capital
- Benchmark ticker
- Rebalancing mode
- Cashflow schedule
- Dividend reinvestment / adjusted close
- Transaction cost or annual drag optional

The UI should show a plain-language assumption preview:

```text
Backtest $10,000 from 2015-01-01 to 2025-12-31.
Portfolio: AAPL 30%, MSFT 30%, SPY 40%.
Benchmark: SPY.
Rebalance yearly at year-end.
Invest dividends.
Add $500 monthly at month-end.
```

### Step 4 - Run Engine

The app runs the backtest pipeline:

```text
raw inputs
  -> validated portfolio
  -> price history
  -> adjusted/total-return price series
  -> aligned date index
  -> asset return matrix
  -> portfolio value simulation
  -> cashflow events
  -> rebalancing events
  -> benchmark comparison
  -> metrics
  -> charts
  -> report artifacts
```

### Step 5 - Results

Results should be tabbed but not overwhelming.

Recommended tabs:

1. Overview
2. Growth
3. Drawdown
4. Returns
5. Risk Metrics
6. Cashflows
7. Rebalancing
8. Report

### Step 6 - Explain

Each metric should have a formula drawer:

- Formula
- Variables
- Implementation note
- Interpretation
- Common trap

Example formulas:

```text
Simple return:
r_t = P_t / P_{t-1} - 1

Portfolio return:
r_{p,t} = sum_i w_{i,t-1} r_{i,t}

CAGR:
(V_T / V_0)^(1 / years) - 1

Annualized volatility:
std(r_p) * sqrt(252)

Sharpe ratio:
mean(r_p - r_f_daily) / std(r_p - r_f_daily) * sqrt(252)

Drawdown:
DD_t = V_t / max(V_0...V_t) - 1

Maximum drawdown:
min(DD_t)

Beta:
cov(r_p, r_b) / var(r_b)
```

### Step 7 - Export

Export package:

- `report.md` or `report.html`
- `run_config.json`
- `holdings_normalized.csv`
- `prices_aligned.csv`
- `returns_matrix.csv`
- `portfolio_values.csv`
- `cashflow_events.csv`
- `rebalance_events.csv`
- `metrics.json`

## Input Parameters

### Portfolio Definition

| Input | Type | Required | Notes |
|---|---|---|---|
| Portfolio name | Text | No | Used in saved runs and report labels. |
| Ticker | Text/search | Yes | Asset symbol. |
| Target weight | Percent | Yes | Must sum to 100%. |
| Quantity | Number | Later | Needed for Webull CSV/current holdings. |
| Current price | Number/fetched | Later | Needed for current allocation and trade plan. |
| Asset class | Select | No | Useful for allocation chart. |
| Currency | Select | Later | Warn on mixed currency. |

### Backtest Window

| Input | Type | Required | Notes |
|---|---|---|---|
| Start date | Date | Yes | Historical start. |
| End date | Date/latest | Yes | Historical end. |
| Initial capital | Number | Yes | Default $10,000. |
| Benchmark | Ticker | Yes | Default SPY for US equity context. |
| Use max overlapping history | Toggle | No | Useful when tickers have different histories. |
| Risk-free rate | Number/source | No | Needed for Sharpe and Treynor. |
| Adjust for inflation | Toggle | Later | Useful for real return/withdrawal analysis. |

### Cashflows

| Input | Type | Required | Notes |
|---|---|---|---|
| Enable cashflows | Toggle | No | Default off. |
| Cashflow type | Select | No | Contribution or withdrawal. |
| Amount type | Select | No | Fixed amount first; percent withdrawal later. |
| Amount | Number | If enabled | Positive contribution or withdrawal amount. |
| Frequency | Select | If enabled | One-time, weekly, monthly, quarterly, yearly. |
| Start date | Date | If enabled | Default backtest start. |
| End date | Date/none | No | Allows contribution phase. |
| Timing / offset | Select | No | Beginning/end of period or nth trading day. |
| Allocation method | Select | No | Target weights first; underweight-only later. |

### Rebalancing

| Input | Type | Required | Notes |
|---|---|---|---|
| Rebalance mode | Select | Yes | None, periodic, bands, periodic + bands. |
| Frequency | Select | If periodic | Monthly, quarterly, semiannual, annual. |
| Offset | Select/number | No | Last trading day default. |
| Absolute drift threshold | Percent | If bands | e.g. 5%. |
| Relative drift threshold | Percent | If bands | e.g. 25%. |
| Min trade size | Number | Later | Avoid unrealistic tiny trades. |
| Whole shares only | Toggle | Later | Practical brokerage mode. |

### Dividends, Costs, And Drag

| Input | Type | Required | Notes |
|---|---|---|---|
| Use adjusted close | Toggle | Yes | Default on. |
| Reinvest dividends | Toggle | No | If data supports dividend events. |
| Annual drag / expense ratio | Percent | No | Simple fee approximation. |
| Transaction cost | Fixed/bps | No | Useful when DCA/rebalancing creates many trades. |
| Slippage | bps | No | Advanced assumption. |
| Tax mode | Select | Later | Keep out of MVP unless required. |

### Output Configuration

| Input | Type | Required | Notes |
|---|---|---|---|
| Return frequency | Select | No | Daily default; monthly table output. |
| Rolling window | Months | No | Later for rolling returns/volatility. |
| Metrics set | Select | No | Basic / CQF. |
| Export format | Select | Yes | Markdown/HTML first. |
| Include formulas | Toggle | Yes | Default on for CQF. |
| Include assumptions | Toggle | Yes | Default on. |
| Include limitations | Toggle | Yes | Default on. |

## Output Metrics

### Basic Metrics

- Start value
- End value
- Total return
- CAGR
- Annualized volatility
- Best year/month
- Worst year/month
- Maximum drawdown
- Benchmark return
- Excess return vs benchmark

### Risk / CQF Metrics

- Sharpe ratio
- Sortino ratio
- Calmar ratio
- Beta vs benchmark
- Alpha vs benchmark
- Tracking error
- Information ratio
- Correlation to benchmark

### Cashflow Metrics

- Initial capital
- Total contributions
- Total withdrawals
- Net invested capital
- Ending value
- Cashflow-adjusted value path
- MWRR/IRR if implemented
- Cashflow event table

### Rebalancing Metrics

- Number of rebalances
- Average rebalances per year
- Turnover per rebalance
- Average annual turnover
- Rebalance event table
- Estimated transaction-cost drag

## Feature Priority

### MVP Must Have

- Manual ticker/weight input
- Validate weights sum to 100%
- Historical price loader with cache
- Adjusted close/total-return price mode
- Start/end date
- Initial capital
- Benchmark comparison
- Rebalancing: none, monthly, quarterly, annual
- Cashflow: none, monthly contribution, monthly withdrawal
- Growth chart
- Drawdown chart
- Annual/monthly return table
- Basic and CQF metrics
- Formula drawer
- Export report

### Should Have

- Webull CSV import once sample file is available
- Cashflow event table
- Rebalance event table
- Rebalance bands
- Transaction cost/slippage assumptions
- Saved local runs
- Data quality warnings
- Markdown/HTML report export

### Could Have Later

- Multiple portfolios side by side
- Rolling returns
- Rolling volatility
- Rolling Sharpe
- Inflation-adjusted backtest
- Percent withdrawals
- Whole-share simulation
- Tax-lot estimates
- SEC filing/fundamental context

### Explicitly Not In This Brief

- Monte Carlo simulation
- Portfolio optimization
- Efficient frontier
- Factor regression as a separate tool
- Trading automation
- Live Webull API

## CQF Methodology Scope

Core theory to explain in the report:

- Data source and adjusted prices
- Simple returns vs log returns
- Portfolio weighted returns
- Rebalancing mechanics
- Cashflow mechanics
- Time-weighted vs money-weighted return intuition
- CAGR
- Volatility
- Covariance/correlation
- Sharpe ratio
- Sortino ratio
- Maximum drawdown
- Calmar ratio
- CAPM beta and alpha
- Benchmark comparison
- Transaction cost/slippage assumptions
- Bias and limitations:
  - Past performance is not future performance
  - Survivorship bias
  - Lookahead bias
  - Data vendor limitations
  - Missing dividend/corporate action data
  - Currency mismatch
  - Tax omission
  - Overinterpretation of historical period

## UI Structure

### First Screen

Use an application workspace:

- Left panel: portfolio input
- Center: results tabs
- Right drawer: assumptions/formulas
- Top toolbar: Import CSV, Run Backtest, Export Report

Avoid a marketing landing page. The user should start doing the backtest immediately.

### Results Tabs

1. Overview
2. Growth
3. Drawdown
4. Returns
5. Metrics
6. Cashflows
7. Rebalancing
8. Report

### Assumptions Drawer

Show the current run in plain language:

- Date range
- Initial capital
- Benchmark
- Rebalancing rule
- Cashflow rule
- Dividend setting
- Cost setting
- Data source

### Formula Drawer

Every metric card should include "Formula" and "Interpretation" actions.

## Recommended Build Direction

Build the first version around "coursework-grade historical backtest":

1. User inputs portfolio.
2. App validates weights and tickers.
3. App fetches historical adjusted prices.
4. App aligns dates across assets and benchmark.
5. App calculates asset returns.
6. App simulates portfolio value with cashflows and rebalancing.
7. App calculates metrics.
8. App renders charts/tables.
9. App exports report and reproducibility files.

This gives a focused project that is deep enough for CQF without mixing in Monte Carlo or optimization before the backtesting engine is correct.

## Gaps To Resolve Before Building

- Need a real Webull CSV sample to map columns correctly.
- Need to choose historical price source and check licensing/limits.
- Need to decide whether MVP uses adjusted close only or explicit dividend events.
- Need to decide whether MWRR/IRR is required in MVP or phase 2.
- Need to decide report export format: Markdown/HTML first, PDF later.
- Need to confirm CQF report language and required submission format.
