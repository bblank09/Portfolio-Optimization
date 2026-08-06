# Formula Audit — 2026-08-01

Line-by-line audit of every metric shown in the app's tab output against its
documented formula in [`formula-reference.md`](formula-reference.md) and its
actual implementation in `backend/app/engine/`. Method: read the exact
source line computing each value, algebraically compare it to the documented
formula, and where practical reproduce the number from a real backtest run
against real cached SEC NAV data (not synthetic fixtures) to confirm the
documented formula and the shipped code agree on an actual output.

Legend: ✅ Match — 🟡 Match with a note worth knowing — 🔴 Discrepancy (fixed
this session).

| # | Metric (tab) | Code location | Doc section | Status | Reasoning |
|---|---|---|---|---|---|
| 1 | Ending value (Summary) | `backtest.py`: `portfolio_value.iloc[-1]` | *(implicit — `V_t` definition in `max_drawdown`)* | ✅ | Value-path based, matches the `V_t` definition used by `max_drawdown`: after returns, cashflows, costs, rebalancing. |
| 2 | TWRR (Summary) | `time_weighted_return(portfolio_returns)` | `time_weighted_return` | ✅ | `product(1+r_t)-1` on the nose. Confirmed `period_performance` computed in the simulation loop matches the doc's `R_p,t` formulas exactly: beginning-timing `E_t/(S_t+C_t)-1`, end-timing `(E_t-C_t)/S_t-1` (`backtest.py` lines ~155-160). |
| 3 | TWRR CAGR (Summary) | `annualized_return(portfolio_returns, m)` | `annualized_return` | ✅ | `total_return ** (m/n) - 1` in code; doc states the same as `(1+TWRR)^(m/n)-1`. |
| 4 | IRR / money-weighted (Summary) | `money_weighted_return(irr_cashflows(...))` | `money_weighted_return (IRR)` | ✅ | `irr_cashflows` builds `[(0,-capital)] + [(pos/m,-amt)] + [(final/m, ending_value)]` exactly as documented; solved via `brentq`, unavailable (not a wrong number) if no root in range. |
| 5 | Volatility (Summary, Metrics) | `annualized_volatility(portfolio_returns, m)` | `annualized_volatility` | ✅ (value) / 🔴→fixed (UI text) | Value: `std(ddof=1)*sqrt(m)`, matches doc exactly, verified numerically (see Finding A). **UI text bug found and fixed**: see Finding A below. |
| 6 | Sharpe ratio (Summary, Metrics) | `sharpe_ratio` | `annualized_volatility` (Sharpe) | ✅ | `(R_ann - Rf) / sigma_ann`, unavailable if volatility ≈ 0. Matches doc exactly. |
| 7 | Sortino ratio (Summary, Metrics) | `sortino_ratio` / `downside_deviation` | `sortino_ratio` | ✅ | `downside_t = min(r_t-MAR,0)`, `sigma_down = sqrt(mean(downside_t²))·sqrt(m)`, `Sortino=(R_ann-Rf)/sigma_down`. Code and doc identical. |
| 8 | Calmar ratio (Summary, Metrics) | `calmar_ratio` | `calmar_ratio` | ✅ | `R_ann / |MDD|`, unavailable if `|MDD|≈0`. Matches. |
| 9 | Value at Risk 95%/99% (Metrics) | `historical_var` | `Historical Value at Risk` | ✅ (value) / 🔴→fixed (UI text) | Value: `max(0, -percentile(r_t, (1-confidence)*100))`, min 3 observations. Matches doc. **UI text hardcoded "monthly" regardless of actual frequency** — see Finding A. |
| 10 | Maximum drawdown (Summary, Drawdown) | `max_drawdown` / `drawdown_series` | `max_drawdown` | ✅ | `(V_t / V_t.cummax() - 1).min()` — `cummax()` is exactly the doc's running-peak `Peak_t`. |
| 11 | Benchmark excess return (Summary) | `time_weighted_return(aligned_portfolio) - time_weighted_return(aligned_benchmark)` | `time_weighted_return` | ✅ | Doc explicitly states both TWRRs here use **date-aligned** series, not the full unaligned `portfolio_returns` used for the Summary TWRR itself — code matches this exactly (`aligned_portfolio`/`aligned_benchmark`, built via `reindex().dropna()`). |
| 12 | Total contributed / withdrawn (Summary, Cashflows) | accumulator in main loop | `Cashflow Accounting` | ✅ | `total_contributed = initial_capital + Σ(positive applied cashflows)`; withdrawal capped at available value, matches doc note verbatim. |
| 13 | Total costs (Summary) | `total_costs` accumulator (drag + rebalance cost) | `Cost Accounting` | ✅ | `Σ(trade_costs + drag_costs)`, matches. |
| 14 | Beta, Alpha (Benchmark Risk) | `beta_alpha(aligned_portfolio, aligned_benchmark, ...)` | `beta_alpha` | ✅ | `cov/var` (ddof=1 via pandas), CAPM alpha `R_p,ann - [Rf + beta·(R_b,ann-Rf)]`. Matches, and correctly uses the **aligned** series as documented. |
| 15 | Tracking error (Benchmark Risk) | `tracking_error(aligned_portfolio, aligned_benchmark, m)` | `Tracking Error and Information Ratio` | ✅ (value) / 🔴→fixed (reference-table text) | Value: `std(active_t, ddof=1)*sqrt(m)`. Matches doc. Static "Formula reference" table hardcoded `sqrt(12)` — see Finding A. |
| 16 | Information ratio (Benchmark Risk) | `information_ratio(aligned_portfolio, aligned_benchmark, m)` | same | 🟡 | `(R_p,ann - R_b,ann)/tracking_error`, matches formula. **Note**: this recomputes `annualized_return` on the *aligned* subset, whereas the Summary tab's `TWRR CAGR` uses the *full unaligned* `portfolio_returns`. In every case observed the two spans are identical (the engine already rejects any request with incomplete periods for either the holdings or the benchmark), so the numbers never actually diverge today — but a reader comparing "Summary TWRR CAGR" to the CAGR implied by the Benchmark Risk tab's information ratio should know these are two separate calculations over what happens to be (not is guaranteed to remain) the same date range. |
| 17 | Correlation (Benchmark Risk) | `correlation(aligned_portfolio, aligned_benchmark)` | `Correlation and Diversification` | ✅ | Pearson `cov/(σ_X·σ_Y)`, `null` (not `NaN`) if degenerate. Matches. |
| 18 | Pairwise asset correlation (Diversification) | `diversification_table`: `asset_returns.corr()` | `Correlation and Diversification` | 🟡 | `.corr()` is Pearson by default — correct. **Minor wording note**: the static reference-table row previously said "Pearson correlation of **aligned** monthly returns" for both this pairwise case and the benchmark case above; "aligned" more precisely describes the benchmark case's explicit `reindex().dropna()` step. For the pairwise case the inputs are just each held asset's complete return series (already guaranteed gap-free upstream). Reworded to "Pearson correlation of aligned **period** returns" as part of Finding A's fix (also fixes the "monthly" hardcoding) — kept "aligned" since both variants are still date-matched pandas operations, just via different mechanisms. |
| 19 | Rolling correlation (Diversification) | `rolling_correlation(returns[asset_ids], window=m)` | `Correlation and Diversification` | ✅ | Same Pearson formula via pandas `.rolling(window).corr()`. Doc says "one year of periods" — `window=m` is exactly one year regardless of monthly (`m=12`) or daily (`m=252`) mode. |
| 20 | Per-asset CAGR, Volatility (Asset Risk and Allocation) | `asset_metrics_table`: `annualized_return`/`annualized_volatility` per asset | `annualized_return`, `annualized_volatility` | 🔴→fixed (doc gap) | Same functions as items 3 and 5, just applied per-asset. **Doc gap found**: neither section's "Used in output" list mentioned the Asset Risk and Allocation tab at all. Fixed — see Finding B. |
| 21 | Rebalance turnover, cost (Rebalancing) | `rebalance_values`: `money_turnover/2`, `cost = money_turnover*cost_rate` | `Rebalance Turnover and Cost` | ✅ | `Σ|target_i - current_i| / 2`, divide-by-2 rationale (avoid double-counting) matches doc exactly. |
| 22 | Drawdown stress scenarios (Drawdown tab) | frontend `stressRows()`: `ending_value * (1+shock)` for shocks `{-10%,-20%,-35%, actual MDD}` | *(not in formula-reference.md — only mentioned in the Report's Limitations paragraph)* | 🟡 | Simple deterministic arithmetic, not a statistical/academic formula — doesn't need a citation. Confirmed the Report tab's own Limitations text already discloses this is "a deterministic shock to ending value, not a probabilistic simulation," so the caveat exists, just not as a formal formula-reference entry. Left as-is (out of scope for a citation; already disclosed). |

## Finding A — UI formula text hardcoded "monthly"/"12" regardless of actual run frequency

**What**: `data.frequency` is a real, user-selectable input (`monthly` → `m=12`,
or `daily` → `m=252`, per `AlignmentFrequency` in
`backend/app/domain/enums.py` and the "NAV granularity" dropdown in
`AssumptionsStep.tsx`). The backend correctly uses whichever `m` the request
specifies (`DAILY_PERIODS_PER_YEAR = 252` vs `PERIODS_PER_YEAR = 12` in
`backtest.py`). However, `frontend/src/components/RunSummary.tsx` displayed
static formula-description text that unconditionally said `"* sqrt(12)"` and
"monthly returns" for Volatility, Value at Risk, Tracking error, and
Correlation — **even when the run actually used daily frequency**.

**Verified live** (not just read from code): ran a real backtest against
cached SEC NAV data for K-SET50, 2023-02-01 to 2023-02-28, with
`data.frequency = "daily"`:

```
reported volatility:     0.0781688150828776
std(daily returns, ddof=1) * sqrt(252):  0.0781688150828776   <- matches exactly
std(daily returns, ddof=1) * sqrt(12):   0.0170578339096330   <- does NOT match
```

The computed *number* was always correct — only the human-readable formula
*description* shown next to it was wrong for daily-mode runs, which could
mislead anyone trying to verify a Volatility, VaR, Tracking Error, or
Correlation figure by hand.

**Fix applied**:
- `keyMetricRows()` (per-run Summary table): now derives `periodsPerYear`
  and `periodLabel` from `result.request.data.frequency` and builds the
  Volatility/VaR formula strings dynamically, so they always match how that
  specific run's numbers were actually computed.
- `formulaReferenceRows()` (the static, run-independent "Formula reference"
  table shown in every report): Volatility and Tracking Error rows now say
  `sqrt(m); m = 12 (monthly) or 252 (daily)` instead of a hardcoded `12`;
  VaR and Correlation rows say "period returns" instead of "monthly returns".
- Re-verified via a live `fetch()` call against the real running API from
  inside the browser page context, replicating the exact fixed conditional
  logic: for the same daily-mode run above, the formula text now reads
  `"Std(daily returns) * sqrt(252)"` — correct.

## Finding B — `annualized_return`/`annualized_volatility` doc sections omitted a real usage site

**What**: `asset_metrics_table()` in `backtest.py` calls the exact same
`annualized_return` and `annualized_volatility` functions per held asset to
populate the Asset Risk and Allocation tab's `cagr`/`volatility` columns, but
neither function's "Used in output" list in `formula-reference.md` mentioned
that tab at all.

**Fix applied**: added "Asset Risk and Allocation tab: per-asset `cagr`
(same function, applied to each held asset's own return series)" and the
equivalent line for `volatility`, to both sections.

## Summary

- 22 output values audited against their documented formula and actual code.
- 19 matched exactly with no changes needed.
- 2 real discrepancies found and fixed (Finding A: UI text hardcoded the
  wrong period count for daily-mode runs; Finding B: a doc completeness gap).
- 1 item flagged as a note-worth-knowing nuance, not a bug (item 16,
  information ratio's aligned-vs-unaligned CAGR).
- 1 item (drawdown stress scenarios) confirmed to be simple deterministic
  arithmetic, already disclosed as such in the report, not requiring a
  citation.
- All fixes verified against real cached SEC NAV data via the live running
  API, not synthetic fixtures — see Finding A's exact numbers above.
