# Objective Workflows

The app uses Objective Presets to reduce setup friction while keeping all quant assumptions editable.

## Rule

Objective selection does three things:

1. Auto-fills default settings.
2. Explains which inputs are required vs optional.
3. Adds an objective-specific Summary tab after the run.

It does not remove the full analysis. These always appear after every run:

- Benchmark Risk
- Drawdown Stress
- Diversification Check
- CQF Report

## Objectives

### Past Performance

Use when the user asks: "If I held this portfolio in the past, what happened?"

Auto-fill:

- Cashflow: off
- Rebalancing: annual
- Benchmark: selected SEC fund `proj_id`
- Initial capital: 10,000
- Transaction cost: 0 bps
- Slippage: 0 bps

Required:

- SEC fund `proj_id` values and weights
- Start date
- End date
- Initial capital
- Benchmark

Summary focuses on ending value, TWRR CAGR, volatility, Sharpe, max drawdown, and excess return vs benchmark.

### Monthly DCA

Use when the user asks: "What if I invested every month?"

Auto-fill:

- Cashflow: contribution
- Amount: 500/month
- Timing: period-end
- Rebalancing: annual
- Benchmark: selected SEC fund `proj_id`

Required:

- SEC fund `proj_id` values and weights
- Monthly contribution amount
- Start date
- End date
- Initial capital

Summary focuses on total contributed, ending value, net profit, MWRR/IRR, TWRR CAGR, and benchmark excess return.

### Monthly Withdrawal

Use when the user asks: "What if I withdrew money every month?"

Auto-fill:

- Cashflow: withdrawal
- Amount: 1,000/month
- Timing: period-end
- Initial capital: 100,000
- Rebalancing: annual
- Benchmark: selected SEC fund `proj_id`

Required:

- SEC fund `proj_id` values and weights
- Withdrawal amount
- Start date
- End date
- Starting capital

Summary focuses on total withdrawn, ending value, portfolio survived/depleted status, max drawdown, MWRR/IRR, and Ulcer Index.

### Rebalancing Impact

Use when the user asks: "Did rebalancing help after turnover and costs?"

Auto-fill:

- Cashflow: off
- Rebalancing: annual
- Transaction cost: 5 bps
- Slippage: 0 bps
- Benchmark: selected SEC fund `proj_id`

Required:

- SEC fund `proj_id` values and weights
- Start date
- End date
- Rebalancing mode

Summary focuses on rebalance count, average turnover, cost drag, ending value, max drawdown, and Sharpe ratio.

## Future Objective Candidates

Not implemented yet:

- Lump Sum vs DCA
- Goal Target Check
- Cost & Fee Impact

These should be added only after the core objective workflow is stable.
