# Claude UI Design Handoff - Portfolio Backtesting Web App

Use this file as the first prompt for Claude when continuing the project as a UI/UX design task.

## Copy/Paste Prompt For Claude

```text
<context>
You are helping design a web UI for a CQF Module 1-2 coursework project.

Project name:
Portfolio Backtesting Web App

Project folder:
Project/Backtest Portfolio Webull:SEC OPENAI/

The project scope is Portfolio Backtesting only.

Do NOT design or include:
- Monte Carlo simulation
- Portfolio optimization
- Efficient frontier
- Black-Litterman
- Risk parity / HRP
- Trading execution
- Live broker connection
- Authentication
- Subscription/paywall features
- Marketing landing page

The app should open directly into a usable backtesting workspace.

Primary reference brief:
reference-brief.md

Main references:
- Portfolio Visualizer: https://www.portfoliovisualizer.com/analysis
- testfol.io help: https://testfol.io/help
- Portfolio Performance: https://www.portfolio-performance.info/en/
- Portfolio Performance manual: https://help.portfolio-performance.info/en/about/
- Stoculator: https://stoculator.com/portfolio-backtesting
- PortfolioBacktesting.com: https://www.portfoliobacktesting.com/
- Backtest Matrix: https://backtestmatrix.com/
- QuantConnect backtest results: https://www.quantconnect.com/docs/v2/local-platform/backtesting/results
- Webull CSV export: https://www.webull.com/help/faq/992-Downloading-your-transaction-history
</context>

<product_goal>
Design a beginner-friendly but academically defensible portfolio backtesting web app.

The user should be able to:
1. Enter or import a portfolio.
2. Validate tickers, weights, dates, and assumptions.
3. Set historical backtest assumptions.
4. Add DCA/contribution or withdrawal cashflows.
5. Set rebalancing rules.
6. Run a historical backtest.
7. Inspect performance, risk, cashflow, and rebalancing results.
8. Open formula explanations for each metric.
9. Export a coursework-ready report and reproducibility files.

Core user question:
"If I had held this portfolio in the past, with these deposits, withdrawals, dividends, costs, and rebalancing rules, what would have happened?"
</product_goal>

<target_users>
Primary users:
- CQF student preparing a Module 1-2 project.
- General investor who understands tickers and weights but does not want a complicated quant tool.

The UI should be approachable for general users but transparent enough that a student can explain the code, formulas, assumptions, workflow, and limitations to an instructor.
</target_users>

<required_user_flow>
Design the UI around this end-to-end flow:

1. Open app.
   - User lands directly in a backtesting workspace.
   - No marketing hero page.

2. Define portfolio.
   - Manual ticker + weight input.
   - Optional Webull CSV import entry point.
   - Optional example portfolio for demo.

3. Validate inputs.
   - Weights sum to 100%.
   - Tickers are not empty or duplicated.
   - Price history exists.
   - Missing data is shown clearly.
   - User can normalize weights or fix manually.

4. Set backtest period.
   - Start date.
   - End date.
   - Initial capital.
   - Benchmark ticker, default SPY.
   - Use max overlapping history toggle.

5. Set cashflow schedule.
   - No cashflow.
   - Monthly contribution.
   - Monthly withdrawal.
   - Amount.
   - Start/end date.
   - Timing: beginning/end of period.

6. Set rebalancing rule.
   - None.
   - Monthly.
   - Quarterly.
   - Annual.
   - Later/advanced: rebalance bands.

7. Set dividends/cost assumptions.
   - Use adjusted close, default on.
   - Reinvest dividends if data supports it.
   - Transaction cost.
   - Annual drag/expense ratio.
   - Slippage as advanced setting.

8. Review assumptions.
   - Show plain-language preview before running.
   - Example:
     "Backtest $10,000 from 2015-01-01 to 2025-12-31. Portfolio: AAPL 30%, MSFT 30%, SPY 40%. Benchmark: SPY. Add $500 monthly at month-end. Rebalance yearly. Use adjusted close."

9. Run backtest.
   - Show progress states:
     validating inputs
     fetching prices
     aligning dates
     calculating returns
     simulating portfolio
     calculating metrics
     generating report

10. View results.
   - Overview.
   - Growth.
   - Drawdown.
   - Returns.
   - Metrics.
   - Cashflows.
   - Rebalancing.
   - Report.

11. Inspect formulas.
   - Metric cards should expose formula, variables, interpretation, implementation note, and common trap.

12. Export.
   - Report markdown/html.
   - run_config.json.
   - holdings_normalized.csv.
   - prices_aligned.csv.
   - returns_matrix.csv.
   - portfolio_values.csv.
   - cashflow_events.csv.
   - rebalance_events.csv.
   - metrics.json.
</required_user_flow>

<required_screens>
Design these screens or views:

1. Main Workspace
   - Left panel: portfolio input and assumptions.
   - Center panel: result tabs.
   - Right drawer: assumptions and formulas.
   - Top toolbar: Import CSV, Load Example, Run Backtest, Export Report.

2. Portfolio Builder
   - Ticker table.
   - Weight input.
   - Add/remove asset.
   - Normalize weights action.
   - Allocation donut or bar chart.
   - Validation messages.

3. Backtest Settings
   - Date range.
   - Initial capital.
   - Benchmark.
   - Cashflow schedule.
   - Rebalancing rule.
   - Dividends/cost assumptions.

4. Assumption Review
   - Plain-language summary.
   - Data warnings.
   - Run readiness state.

5. Results Overview
   - Ending value.
   - Total return.
   - CAGR.
   - Volatility.
   - Sharpe ratio.
   - Max drawdown.
   - Benchmark CAGR.
   - Excess return.
   - Contributions/withdrawals if enabled.
   - Rebalance count.

6. Growth Tab
   - Portfolio value chart.
   - Benchmark value chart.
   - Net invested capital line if cashflows exist.
   - Cashflow markers.

7. Drawdown Tab
   - Underwater chart.
   - Portfolio vs benchmark drawdown.
   - Worst drawdown callout.

8. Returns Tab
   - Annual returns table.
   - Monthly returns heatmap.
   - Best/worst period callouts.

9. Metrics Tab
   - Group metrics into Performance, Risk, Risk-adjusted, Benchmark-relative.
   - Every metric has a formula action.

10. Cashflows Tab
   - Total contributions.
   - Total withdrawals.
   - Net invested capital.
   - Event table.
   - TWRR/MWRR note.

11. Rebalancing Tab
   - Rebalance event table.
   - Before/after weights.
   - Turnover.
   - Estimated cost drag.

12. Report Tab
   - Auto-generated report preview.
   - Sections: Objective, Inputs, Data Source, Assumptions, Methodology, Metrics/Formulas, Results, Benchmark Comparison, Discussion, Limitations, Appendix.
</required_screens>

<design_constraints>
- The app should feel like a serious financial analysis workspace, not a marketing SaaS homepage.
- Keep the first screen operational and compact.
- Use clear panels, tabs, tables, charts, and drawers.
- Avoid decorative cards inside cards.
- Avoid large hero sections, oversized marketing copy, or fluffy explanations.
- Use familiar icons for import, run, export, add, remove, warning, info, formula, and settings.
- Make formulas available but not forced into the main flow.
- Keep beginner defaults visible and advanced assumptions tucked into drawers/accordions.
- Make warnings clear and specific.
- The design must support desktop first, but include mobile/responsive behavior.
- The user should always know: inputs, assumptions, result, and how the result was calculated.
</design_constraints>

<output_format>
Produce a UI design specification, not code yet.

Include:
1. Product framing in 5-8 bullets.
2. Information architecture.
3. End-to-end user journey.
4. Screen-by-screen UI description.
5. Component inventory.
6. Form fields and validation states.
7. Empty/loading/error/success states.
8. Chart/table requirements.
9. Formula drawer behavior.
10. Report export behavior.
11. Responsive layout notes.
12. A concise MVP UI scope.
13. A list of what NOT to build.

Be specific enough that a frontend developer can build the UI from your answer.
</output_format>

<acceptance_criteria>
The design is done when:
- It clearly supports only Portfolio Backtesting.
- It does not include Monte Carlo or Optimization features.
- It covers the full user flow from input to export.
- It includes all required result tabs.
- It includes cashflows and rebalancing as first-class settings.
- It includes formula/explanation UX for CQF.
- It includes clear validation and error states.
- It is practical to implement as a web app.
</acceptance_criteria>

Think carefully before responding. Only design what is directly requested. Do not add unrelated features.
```

## Notes For The Next AI

- The source of truth is `reference-brief.md`.
- Keep the project focused: Portfolio Backtesting only.
- The design should support CQF explanation and coursework submission.
- If implementation is requested later, first convert the UI design into a build plan before writing code.
