# Formula Reference

This project computes production outputs from cached SEC Open Data NAV observations. The NAV alignment frequency is a user-selectable input (`data.frequency`): month-end (`m = 12`, the default) or daily business days (`m = 252`). Every formula below that references `m` uses whichever value the run was actually configured with — the walkthroughs use `m = 12` for readability, but substitute `m = 252` for a daily-mode run.

## Notation

| Symbol | Meaning |
| --- | --- |
| `NAV_t` | SEC NAV per unit at period `t` |
| `r_t` | Single-period return |
| `R_p,t` | Portfolio return at period `t` |
| `R_b,t` | Benchmark return at period `t` |
| `S_t` | Portfolio value at the start of period `t` |
| `E_t` | Portfolio value at the end of period `t` |
| `C_t` | Actual external cashflow applied in period `t` (positive contribution, negative withdrawal) |
| `V_t` | Portfolio value at period `t` |
| `n` | Number of observed return periods |
| `m` | Periods per year, currently `12` |
| `R_f` | Annual risk-free rate input |

## `simple_returns`

Purpose: convert SEC NAV observations into period returns for each selected fund and the benchmark.

```text
r_t = NAV_t / NAV_{t-1} - 1
```

Equivalent form:

```text
r_t = (NAV_t - NAV_{t-1}) / NAV_{t-1}
```

Implementation detail: the function uses pandas `pct_change(fill_method=None)` and drops rows with missing observations according to the configured `drop` rule. It never forward-fills a missing NAV into a fabricated return. In production backtesting, selected-asset periods must be complete; benchmark metrics use only periods with real matched returns.

Used in output:

- Monthly Returns.
- Equity Curve return path.
- Benchmark Risk calculations.
- Annual Returns aggregation.

Source: standard period-return arithmetic; not attributable to a specific paper.

## `time_weighted_return`

Purpose: measure compounded investment performance independent of cashflow size.

```text
TWRR = product_{t=1..n}(1 + R_p,t) - 1
```

Where:

- `R_p,t` is the cashflow-neutral portfolio return for period `t`. For beginning-of-period cashflows, `R_p,t = E_t / (S_t + C_t) - 1`; for end-of-period cashflows, `R_p,t = (E_t - C_t) / S_t - 1`.
- `C_t` is the amount actually applied. A withdrawal is capped at available portfolio value, so it can be smaller in magnitude than the requested withdrawal.
- `n` is the number of valid aligned periods.

Interpretation: TWRR answers "what did the strategy return over the selected period?" without treating a larger DCA deposit or withdrawal as skill. Market returns, modeled costs, and rebalancing effects remain in the performance return.

Used in output:

- Summary: `TWRR`.
- Benchmark excess return:

```text
benchmark_excess_return = TWRR_portfolio - TWRR_benchmark
```

For this metric, both TWRRs are calculated from the date-aligned portfolio and benchmark return observations.

Source: [GIPS Guidance Statement on Calculation Methodology](http://www.gipsstandards.org/wp-content/uploads/2021/03/calculation_methodology_gs_2006.pdf) (CFA Institute) — GIPS requires time-weighted return specifically because it removes the effect of client-driven cashflow timing, which is why this metric (not IRR) is the primary performance figure in this report. See also [CFA Institute, "Overview of the Global Investment Performance Standards"](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/overview-of-the-global-investment-performance-standards).

## `money_weighted_return` (IRR)

Purpose: measure the investor's actual dollar-weighted experience, including the size and timing of contributions and withdrawals — the figure TWRR deliberately excludes.

The investor-perspective cashflow series is built first (`irr_cashflows`):

```text
events = [(0, -initial_capital)] + [(position_i / m, -amount_i) for each applied cashflow] + [(final_position / m, ending_value)]
```

IRR solves for the rate `r` that sets the net present value of this series to zero:

```text
sum_i( CF_i / (1 + r)^t_i ) = 0
```

Where:

- `CF_i` is the signed cashflow from the investor's perspective (money going in is negative, money coming out — including the terminal ending value — is positive).
- `t_i` is nominal elapsed years (`period position / m`), the same convention every other annualized figure in this engine uses. Real NAV dates fall on month-end/business-day calendars, so using actual calendar days instead would make IRR diverge from TWRR CAGR even with zero intermediate cashflows, when the two must agree exactly in that case.
- The equation is solved numerically with Brent's method (`scipy.optimize.brentq`) over the rate range `-99.9999%` to `1000%`; if no root exists in that range, IRR is reported as unavailable rather than a wrong number.

Interpretation: IRR and TWRR agree exactly when there are no intermediate cashflows (only the initial investment and final value). They diverge whenever cashflow timing matters — e.g. a large contribution added right before a rally inflates IRR relative to TWRR, because IRR is money-weighted (a bigger cashflow gets more weight) while TWRR is not.

Used in output:

- Summary: `IRR (money-weighted)`.

Source: [GIPS Guidance Statement on Calculation Methodology](http://www.gipsstandards.org/wp-content/uploads/2021/03/calculation_methodology_gs_2006.pdf) (CFA Institute) defines money-weighted return as the appropriate alternative to TWRR when cashflow timing is relevant to the return experienced. The underlying IRR technique (net-present-value root-finding on a cashflow series) is a standard capital-budgeting method, not attributable to a single paper.

## `annualized_return`

Purpose: convert compounded period return into an annualized growth rate.

```text
R_ann = product_{t=1..n}(1 + r_t)^(m / n) - 1
```

Equivalent using total return:

```text
R_ann = (1 + TWRR)^(m / n) - 1
```

Where:

- `m = 12` for month-end returns.
- `n` is the number of observed periods.

Used in output:

- Summary: `TWRR CAGR`.
- Sharpe ratio numerator.
- CAPM-style alpha calculation.
- Information ratio numerator.
- Asset Risk and Allocation tab: per-asset `cagr` (same function, applied to each held asset's own return series).

Source: standard geometric annualization of a compounded return; not attributable to a specific paper. It is the numerator convention used throughout the GIPS-referenced return calculations above.

## `annualized_volatility`

Purpose: annualize return dispersion from period returns.

```text
sigma_ann = std(r_t, ddof=1) * sqrt(m)
```

Where:

- `std(r_t, ddof=1)` is the unbiased sample standard deviation (Bessel corrected), matching the `ddof=1` cov/var used by beta so Sharpe and beta rest on one convention.
- `m = 12` for month-end returns.

Used in output:

- Summary: `Volatility`.
- Sharpe ratio denominator.
- Asset Risk and Allocation tab: per-asset `volatility` (same function, applied to each held asset's own return series).

Related ratio:

```text
Sharpe = (R_ann - R_f) / sigma_ann
```

If volatility is zero, Sharpe is reported as unavailable instead of dividing by zero.

Source: `annualized_volatility` is standard sample-statistics dispersion; not attributable to a specific paper. The Sharpe ratio itself originates with Sharpe, W.F. (1966), "Mutual Fund Performance," *Journal of Business*, 39(1), 119-138 (as the "reward-to-variability ratio"), and was formalized under its current name and interpretation in Sharpe, W.F. (1994), ["The Sharpe Ratio"](https://web.stanford.edu/~wfsharpe/art/art1.htm), *The Journal of Portfolio Management*, 21(1), 49-58.

## `sortino_ratio`

Purpose: like Sharpe, but penalizes only downside volatility (returns below a minimum acceptable return, `MAR = 0` here) instead of total volatility — so a strategy with large *upside* swings is not penalized for them.

Downside deviation:

```text
downside_t = min(r_t - MAR, 0)
sigma_down = sqrt(mean(downside_t^2)) * sqrt(m)
```

Sortino ratio:

```text
Sortino = (R_ann - R_f) / sigma_down
```

Where:

- `MAR = 0` (minimum acceptable return) in this engine's configuration.
- `m = 12` for month-end returns.

If downside deviation is zero (no periods below the MAR), Sortino is reported as unavailable instead of dividing by zero.

Used in output:

- Summary / Metrics: `Sortino ratio`.

Source: Sortino, F.A. & Price, L.N. (1994), "Performance Measurement in a Downside Risk Framework," *The Journal of Investing*, 3(3), 59-64.

## `max_drawdown`

Purpose: measure the largest peak-to-trough loss in the simulated portfolio value path.

First calculate running peak:

```text
Peak_t = max(V_0, V_1, ..., V_t)
```

Then calculate drawdown:

```text
DD_t = V_t / Peak_t - 1
```

Maximum drawdown:

```text
MDD = min(DD_t)
```

Where:

- `V_t` is the simulated portfolio value after NAV returns, cashflows, costs, and rebalancing logic for period `t`. Drawdown is value-path based, so external cashflows can change it even though they are excluded from TWRR.
- Drawdown is negative or zero.

Used in output:

- Summary: `Maximum drawdown`.
- Drawdown Curve.
- Drawdown Stress: `Repeat max drawdown` scenario.

Source: Magdon-Ismail, M. & Atiya, A.F., ["An Analysis of the Maximum Drawdown Risk Measure"](https://www.cs.rpi.edu/~magdon/ps/journal/drawdown_RISK04.pdf) — the peak-to-trough drawdown definition used here matches the standard formulation analyzed in that paper.

## `calmar_ratio`

Purpose: measure annualized return relative to the worst peak-to-trough loss actually realized, as a "return per unit of pain endured" figure that is easier to communicate than volatility-based ratios.

```text
Calmar = R_ann / |MDD|
```

Where `MDD` is the maximum drawdown defined above. If `|MDD|` is zero (no drawdown observed), Calmar is reported as unavailable instead of dividing by zero.

Used in output:

- Summary / Metrics: `Calmar ratio`.

Source: introduced by Young, T.W. (1991) in *Futures* magazine as a modification of the Sterling ratio, calculated monthly instead of annually; the name is an acronym of Young's firm, California Managed Accounts Reports. The original 1991 trade-magazine article is not available as a digitized/linkable source — see [Wikipedia, "Calmar ratio"](https://en.wikipedia.org/wiki/Calmar_ratio) for a secondary summary and attribution.

## `beta_alpha`

Purpose: measure benchmark-relative risk and CAPM-style excess performance.

Cashflow-neutral portfolio and benchmark returns are first aligned by date:

```text
Aligned_t = (R_p,t, R_b,t)
```

Beta:

```text
beta = cov(R_p, R_b) / var(R_b)
```

Implementation detail: beta uses pandas covariance and sample variance for benchmark returns (`ddof=1` through pandas `var()`).

Annualized portfolio and benchmark returns:

```text
R_p,ann = product_{t=1..n}(1 + R_p,t)^(m / n) - 1
R_b,ann = product_{t=1..n}(1 + R_b,t)^(m / n) - 1
```

CAPM-style alpha:

```text
alpha = R_p,ann - [R_f + beta * (R_b,ann - R_f)]
```

Where:

- `R_f` is the annual risk-free rate input.
- `R_p,ann` is portfolio annualized return.
- `R_b,ann` is benchmark annualized return.

Used in output:

- Benchmark Risk: `beta`.
- Benchmark Risk: `alpha`.

Source: the CAPM that defines beta and CAPM-style alpha originates with Sharpe, W.F. (1964), "Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk," *Journal of Finance*, 19(3), 425-442, and Lintner, J. (1965), "The Valuation of Risk Assets and the Selection of Risky Investments in Stock Portfolios and Capital Budgets," *Review of Economics and Statistics*, 47(1), 13-37. For a modern treatment and evidence on the model's assumptions and limitations, see Fama, E.F. & French, K.R. (2004), ["The Capital Asset Pricing Model: Theory and Evidence"](https://mba.tuck.dartmouth.edu/bespeneckbo/default/AFA611-Eckbo%20web%20site/AFA611-S6B-FamaFrench-CAPM-JEP04.pdf), *Journal of Economic Perspectives*, 18(3), 25-46.

## Historical Value at Risk

Purpose: estimate the loss magnitude that should not be exceeded more than `(1 - confidence)` of the time, using the empirical distribution of observed returns directly (no assumed distribution shape, unlike parametric/variance-covariance VaR).

```text
VaR_confidence = max(0, -percentile(r_t, (1 - confidence) * 100))
```

Where:

- `percentile(r_t, p)` is the `p`-th percentile of the observed period-return sample (e.g. the 5th percentile for 95% VaR).
- The result is reported as a positive loss magnitude (a 95% VaR of 3% means no more than a 3% loss is expected in 95% of periods).
- Requires at least 3 clean return observations; below that, VaR is reported as unavailable rather than a statistically meaningless percentile.

Used in output:

- Metrics: `Value at Risk (95%)`, `Value at Risk (99%)`.

Source: this is the standard **historical simulation** method for VaR — using realized historical returns as the loss distribution directly, rather than assuming a parametric distribution. See Jorion, P., *Value at Risk: The New Benchmark for Managing Financial Risk* (3rd ed., McGraw-Hill), the standard reference that popularized VaR as a risk-management benchmark, and CFA Institute, ["Measuring and Managing Market Risk"](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/measuring-managing-market-risk), which documents the historical-simulation method's advantage (no distributional assumption) and its main limitation (estimates are sensitive to the choice of lookback period).

## Correlation and Diversification

Purpose: measure how closely two return series move together, which drives the diversification benefit of holding multiple assets — the entire reason a mix of assets can have lower risk than any single one of its components.

Pearson correlation coefficient:

```text
rho(X, Y) = cov(X, Y) / (sigma_X * sigma_Y)
```

Where `cov(X, Y)` is the sample covariance and `sigma_X`, `sigma_Y` are sample standard deviations. `rho` is undefined (reported as `null`, not `NaN`) when either series has zero variance, since the denominator is then zero.

Two variants are computed:

- `correlation`: a single value over the full aligned portfolio-vs-benchmark return history (Benchmark Risk tab) and over every unordered pair of held assets (`diversification_table`, Diversification tab).
- `rolling_correlation`: the same Pearson formula applied over a rolling window (one year of periods), recomputed at each date, for every pair of held assets. A static full-period correlation can hide regime changes — two funds can average a low correlation over years while having moved in lockstep during exactly the period that mattered; the rolling window surfaces that.

Used in output:

- Benchmark Risk: `correlation`.
- Diversification tab: pairwise asset correlation matrix, rolling correlation chart.

Source: the correlation coefficient's role in portfolio risk (`rho < 1` between assets means portfolio volatility is less than the weighted average of individual volatilities) is the foundational result of Markowitz, H. (1952), "Portfolio Selection," *The Journal of Finance*, 7(1), 77-91 — the origin of mean-variance portfolio theory and the formal basis for "diversification reduces risk."

## Tracking Error and Information Ratio

These are additional benchmark-risk formulas used in the report.

Active return:

```text
active_t = R_p,t - R_b,t
```

Tracking error:

```text
tracking_error = std(active_t, ddof=1) * sqrt(m)
```

Information ratio:

```text
information_ratio = (R_p,ann - R_b,ann) / tracking_error
```

If tracking error is zero, information ratio is reported as unavailable.

Source: CFA Institute — Kidd, D., CFA (2012), ["Investment Risk and Performance"](https://rpc.cfainstitute.org/sites/default/files/-/media/documents/code/gips/case-study-risk-adjusted-performance-measures.pdf), which documents tracking error (the standard deviation of active/benchmark-relative returns) and the information ratio (active return divided by tracking error) as the standard pair of measures for evaluating active management skill.

## Cashflow Accounting

Recurring contribution and withdrawal amounts are accounted separately from TWRR.

```text
total_contributed = initial_capital + sum(contribution_cashflows)
total_withdrawn = sum(withdrawal_cashflows)
net_profit = ending_value + total_withdrawn - total_contributed
```

`total_contributed` starts with initial capital and adds applied positive cashflows. `total_withdrawn` sums the absolute value of applied withdrawals, including any cap when a requested withdrawal exceeds the available portfolio value.

Used in output:

- Objective Summary for Monthly DCA.
- Objective Summary for Monthly Withdrawal.
- Cashflows tab.

Source: bookkeeping arithmetic specific to this engine's cashflow model; not attributable to a specific paper.

## Cost Accounting

Transaction cost and slippage are specified in basis points.

```text
cost_rate = (transaction_bps + slippage_bps) / 10,000
trade_cost = traded_value * cost_rate
```

Annual drag is specified as a percent input and applied as a recurring model assumption by the engine where configured.

```text
total_costs = sum(trade_costs + drag_costs)
```

Used in output:

- Summary: `Total costs`.
- Rebalancing tab cost impact.

Source: basis-point cost modeling is standard transaction-cost practice; not attributable to a specific paper.

## Rebalance Turnover and Cost

Purpose: measure how much of the portfolio was actually traded at each rebalance event, and the resulting transaction cost.

One-way turnover (as a fraction of portfolio value):

```text
money_turnover = sum(|target_value_i - current_value_i|) / 2
turnover_ratio = money_turnover / total_portfolio_value
```

Rebalance cost:

```text
cost = money_turnover * cost_rate   (cost_rate defined in Cost Accounting above)
```

Where dividing by 2 avoids double-counting: money moved out of overweight assets equals money moved into underweight assets, so summing the absolute differences across all assets counts each dollar traded twice.

Used in output:

- Rebalancing tab: per-event turnover and cost.

Source: turnover-as-fraction-of-portfolio-traded is standard portfolio-management bookkeeping; not attributable to a specific paper.

## Source Mapping

| Engine function | Report section | Primary output |
| --- | --- | --- |
| `simple_returns` | Growth, Returns, Benchmark Risk | Period returns |
| `time_weighted_return` | Summary, Objective Summary | TWRR |
| `money_weighted_return` (IRR) | Summary | IRR (money-weighted) |
| `annualized_return` | Summary, Benchmark Risk | TWRR CAGR, alpha inputs |
| `annualized_volatility` | Summary, Metrics | Volatility |
| `sortino_ratio` | Summary, Metrics | Sortino ratio |
| `max_drawdown` | Drawdown, Drawdown Stress | Maximum drawdown |
| `calmar_ratio` | Summary, Metrics | Calmar ratio |
| `historical_var` | Metrics | Value at Risk (95%, 99%) |
| `correlation` / `rolling_correlation` | Benchmark Risk, Diversification | Correlation, rolling correlation |
| `beta_alpha` | Benchmark Risk | Beta, alpha |
| `tracking_error` / `information_ratio` | Benchmark Risk | Tracking error, information ratio |
| Rebalance turnover/cost | Rebalancing | Turnover, cost |

## References

- CFA Institute, [GIPS Guidance Statement on Calculation Methodology](http://www.gipsstandards.org/wp-content/uploads/2021/03/calculation_methodology_gs_2006.pdf).
- CFA Institute, [Overview of the Global Investment Performance Standards](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/overview-of-the-global-investment-performance-standards).
- Sharpe, W.F. (1966). "Mutual Fund Performance." *Journal of Business*, 39(1), 119-138.
- Sharpe, W.F. (1994). ["The Sharpe Ratio."](https://web.stanford.edu/~wfsharpe/art/art1.htm) *The Journal of Portfolio Management*, 21(1), 49-58.
- Sortino, F.A. & Price, L.N. (1994). "Performance Measurement in a Downside Risk Framework." *The Journal of Investing*, 3(3), 59-64.
- Young, T.W. (1991). Calmar ratio, originally published in *Futures* magazine. See [Wikipedia, "Calmar ratio"](https://en.wikipedia.org/wiki/Calmar_ratio) (primary source not digitized/linkable).
- Magdon-Ismail, M. & Atiya, A.F. ["An Analysis of the Maximum Drawdown Risk Measure."](https://www.cs.rpi.edu/~magdon/ps/journal/drawdown_RISK04.pdf)
- Jorion, P. *Value at Risk: The New Benchmark for Managing Financial Risk* (3rd ed.). McGraw-Hill.
- CFA Institute, ["Measuring and Managing Market Risk."](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/measuring-managing-market-risk)
- Sharpe, W.F. (1964). "Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk." *Journal of Finance*, 19(3), 425-442.
- Lintner, J. (1965). "The Valuation of Risk Assets and the Selection of Risky Investments in Stock Portfolios and Capital Budgets." *Review of Economics and Statistics*, 47(1), 13-37.
- Fama, E.F. & French, K.R. (2004). ["The Capital Asset Pricing Model: Theory and Evidence."](https://mba.tuck.dartmouth.edu/bespeneckbo/default/AFA611-Eckbo%20web%20site/AFA611-S6B-FamaFrench-CAPM-JEP04.pdf) *Journal of Economic Perspectives*, 18(3), 25-46.
- Kidd, D., CFA (2012). ["Investment Risk and Performance."](https://rpc.cfainstitute.org/sites/default/files/-/media/documents/code/gips/case-study-risk-adjusted-performance-measures.pdf) CFA Institute.
- Markowitz, H. (1952). "Portfolio Selection." *The Journal of Finance*, 7(1), 77-91.
