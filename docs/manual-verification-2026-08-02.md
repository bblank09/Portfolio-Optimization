# Manual Excel Verification — 2026-08-02 (Phase 4.4)

**Workbook**: [`manual-verification-2026-08-02.xlsx`](manual-verification-2026-08-02.xlsx)
**Build script**: [`scripts/build_manual_verification_xlsx.py`](../scripts/build_manual_verification_xlsx.py)
**Source data**: [`docs/verification/`](verification/) (Run 2 — K-SET50 60% / M-S50 40%,
2023-01-31 to 2023-05-31, DCA 2,000/month, monthly rebalancing, 5+5 bps costs)

## What this is

Every metric the app produces, recomputed **independently in Excel** starting
only from the raw month-end NAV values — not by copying the Python engine's
intermediate output. Every calculation cell is a real formula (blue =
hardcoded input, black = formula, green = cross-sheet reference), so anyone
can open the workbook, click any cell, and see exactly how a number was
derived.

## Sheets

1. **Inputs** — run parameters and the 5 raw NAV-per-unit points per fund.
2. **Simulation** — the monthly portfolio ledger, replicating
   `backend/app/engine/backtest.py`'s per-period loop (apply return → apply
   cashflow → rebalance → deduct cost → record ending value and
   cashflow-neutral period return) as one column per period.
3. **Metrics** — TWRR, CAGR, Volatility, Sharpe, Sortino, Calmar, VaR 95/99,
   Max Drawdown, IRR (money-weighted), Beta, Alpha, Tracking Error,
   Information Ratio, correlations, per-asset CAGR/volatility, cashflow and
   cost totals — each as its own formula, matching the definitions in
   [`formula-reference.md`](formula-reference.md).
4. **Comparison** — every one of the above, plus the full equity curve and
   every rebalance event's turnover/cost, laid out side by side: the Excel
   value against the real value from `docs/verification/4.3b-result.json`
   (the actual API response), a rounded-to-6-decimals diff, and a
   MATCH/MISMATCH flag.
5. **Checks** — pass/fail rollup.

## Result

**37 of 37 comparisons MATCH to 6 decimal places.** Zero mismatches, zero
formula errors anywhere in the workbook (verified by forcing a full
recalculation with LibreOffice headless and reading every cell back).

| Check | Result |
|---|---|
| Summary metrics (TWRR, CAGR, Sharpe, Sortino, Calmar, VaR×2, Max Drawdown, IRR, benchmark excess return) | 11/11 match |
| Benchmark Risk (Beta, Alpha, Tracking Error, Information Ratio, portfolio↔benchmark Correlation) | 5/5 match |
| Diversification (K-SET50↔M-S50 correlation) | 1/1 match |
| Asset Risk and Allocation (per-asset CAGR, volatility ×2 assets) | 4/4 match |
| Cashflow accounting (contributed, withdrawn, total costs) | 3/3 match |
| Equity curve (5 period-end portfolio values) | 5/5 match |
| Rebalancing (4 turnover-ratio + 4 cost values) | 8/8 match |

## One real bug caught while building it

The first draft of the Comparison sheet's rebalance-turnover row compared
Excel's **dollar turnover** (`money_turnover`, e.g. 6.897 for the first
event) against the app's `turnover` field — which is actually the **ratio**
(fraction of portfolio value, e.g. 0.0000692). This produced 4 large,
obviously-wrong "MISMATCH" flags. Root cause: a mislabeling in the workbook
build script, not an app bug — the app's own field is correctly documented
as a ratio in `formula-reference.md`'s Rebalance Turnover section. Fixed by
comparing against the `TurnoverRatio` row instead; re-verified to MATCH.
This is exactly the kind of mistake independent manual verification is
supposed to catch — in this case it caught a bug in the *verification tool*,
not the app, which is itself a useful confirmation that the check is
sensitive enough to notice a real discrepancy when one exists.

## Known Excel-compatibility notes (not app bugs)

Two implementation details were needed to get formulas to evaluate at all in
plain (pre-2010) Excel/LibreOffice function names, both purely mechanical:

- `PRODUCT(1+range)` needs array-context (CSE) that a plain formula string
  doesn't get from openpyxl; expressed instead as
  `EXP(SUMPRODUCT(LN(1+range)))`, which is mathematically identical
  (`Σ ln(1+r_t) = ln(Π(1+r_t))`) and doesn't need array-entry.
- `STDEV.S`/`VAR.S`/`PERCENTILE.INC`/`COVARIANCE.S` are post-2007 function
  names; without an `_xlfn.` prefix (which openpyxl doesn't add
  automatically) they read as unknown names. Replaced with the identical
  pre-2010 equivalents (`STDEV`, `VAR`, `PERCENTILE`) or, for sample
  covariance (no pre-2010 equivalent exists — old `COVAR()` is *population*
  covariance), an explicit `SUMPRODUCT`-based formula for
  `Σ(x-x̄)(y-ȳ)/(n-1)`.

Neither affects the app — both are quirks of generating `.xlsx` formula
strings programmatically rather than typing them into a live Excel session.
