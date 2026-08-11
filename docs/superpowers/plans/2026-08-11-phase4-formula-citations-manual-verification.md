# Phase 4: Formula Citations + Manual Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an academically-cited formula reference for the optimizer's own math (mean-variance, CVaR/CDaR, Black-Litterman, HRP, robust optimization), then hand-verify one real optimization run's every output field, across all 6 real result tabs, against independently-computed Excel formulas to 6 decimal places.

**Architecture:** Two independent deliverables. (1) `docs/optimizer-formula-reference.md` — a citation/formula doc, same rigor as the existing `docs/formula-reference.md` (which covers only the backtest engine). (2) A fixed real test case (2 real funds, a clean 4-month window) run once against the live backend, captured to disk, then hand-verified in a generated `.xlsx` workbook whose formulas are computed live from raw NAV data — never copied from the API response — plus one closed-form full-solve replication as a genuine solver-correctness check.

**Tech Stack:** FastAPI backend (already running, no changes needed to run it), Python `openpyxl` for building the Excel workbook with live formulas (not pasted values), the project's existing venv.

## Global Constraints

- Fixed test case (do not substitute different funds/dates without re-validating against `GET /api/funds/testable-range` first): funds `M0209_2548` (K-SET50) + `M0155_2547` (M-S50), period `2024-02-29` to `2024-05-31`, monthly frequency — confirmed live via `GET /api/funds/testable-range?proj_ids=M0209_2548,M0155_2547` to return `{"start":"2015-01-31","end":"2024-06-30"}`, so this window has no NAV gaps.
- Backend runs on port `8001` (`source /private/tmp/sec_open_data_portfolio_backtester_venv/bin/activate && uvicorn backend.app.main:app --port 8001`), matching the frontend's dev proxy default — no code change needed, just start it before Task 1.
- Every Excel formula must be computed live from `nav.csv` (raw data) — never a pasted/typed-in value copied from `result.json`. The whole point of this phase is an independent check; a formula that just references the JSON is not a check.
- `docs/optimizer-formula-reference.md` covers only formulas the *optimizer* (`backend/app/optimizer/`) uses. Formulas already covered by `docs/formula-reference.md` (CAGR, volatility, Sharpe, Sortino, max drawdown, tracking error — reused as-is by the optimizer's Performance/Rolling tabs) are cross-linked, not duplicated.
- Any real mismatch found (beyond 6-decimal floating-point noise) gets a failing `backend/tests/` test written first, then a fix in whichever of `backend/app/engine/` or `backend/app/optimizer/` owns the wrong formula — TDD, not fix-then-test.
- Output files: `docs/optimizer-formula-reference.md`, `docs/manual-verification-2026-08-11/request.json`, `docs/manual-verification-2026-08-11/result.json`, `docs/manual-verification-2026-08-11/nav.csv`, `docs/manual-verification-2026-08-11.xlsx`, `docs/manual-verification-2026-08-11.md`.

---

### Task 1: Capture the real test case

**Files:**
- Create: `docs/manual-verification-2026-08-11/request.json`
- Create: `docs/manual-verification-2026-08-11/result.json`
- Create: `docs/manual-verification-2026-08-11/nav.csv`

**Interfaces:**
- Consumes: the live `POST /api/optimize` endpoint (already implemented, no changes needed) and `backend.app.sec.cache.load_nav_panel(proj_ids)` (already implemented — call with `["M0209_2548", "M0155_2547"]`).
- Produces: `result.json` (the real `OptimizeResult`, camelCase field names) — every later task reads THIS file, never re-runs the request. `nav.csv` (columns: `nav_date`, `M0209_2548`, `M0155_2547` — raw NAV, not returns) — every later task's Excel formulas compute FROM this file.

- [ ] **Step 1: Start the backend**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
source /private/tmp/sec_open_data_portfolio_backtester_venv/bin/activate
nohup uvicorn backend.app.main:app --port 8001 > /tmp/phase4-backend.log 2>&1 &
sleep 4
curl -s http://127.0.0.1:8001/api/data-status
```
Expected: a JSON object with `"data_source":"sec_open_data"` — confirms the backend is up and the cache is loaded.

- [ ] **Step 2: Re-confirm the fixed test case's date range is still clean**

```bash
curl -s "http://127.0.0.1:8001/api/funds/testable-range?proj_ids=M0209_2548,M0155_2547"
```
Expected: `{"start":"2015-01-31","end":"2024-06-30"}` (or a range that still comfortably contains `2024-02-29`–`2024-05-31`). If the range no longer contains this window, STOP and report back — do not silently pick a different window without updating this plan's Global Constraints first.

- [ ] **Step 3: Write the request body**

Create `docs/manual-verification-2026-08-11/request.json` with exactly this content:

```json
{
  "funds": [
    {"projId": "M0209_2548", "displayName": "K-SET50"},
    {"projId": "M0155_2547", "displayName": "M-S50"}
  ],
  "fundBounds": {},
  "currentWeightPct": {},
  "fundGroups": {},
  "assetGroups": {},
  "timePeriod": {"startDate": "2024-02-29", "endDate": "2024-05-31"},
  "dataFrequency": "monthly",
  "goal": "max_sharpe",
  "riskMeasure": "std_dev",
  "tailConfidence": 95,
  "targetAnnualVolatilityPct": null,
  "targetAnnualReturnPct": null,
  "robustOptimization": false,
  "useHistoricalReturns": true,
  "useHistoricalVolatility": true,
  "useHistoricalCorrelations": true,
  "expectedReturnOverrides": {},
  "volatilityOverrides": {},
  "correlationOverrides": {},
  "returnMethod": "historical_mean",
  "covarianceMethod": "sample",
  "blackLitterman": null,
  "benchmarkProjId": null,
  "constraints": {
    "longOnly": true,
    "minWeightPct": 0,
    "maxWeightPct": 100,
    "groupConstraintsEnabled": false,
    "maxHoldings": 2,
    "lookbackPeriodMonths": 12,
    "optimizationFrequency": "monthly",
    "rollingWindowMode": "expanding",
    "riskFreeRatePct": 1.5,
    "compareAgainst": "none",
    "maxTurnoverPct": null,
    "maxTrackingErrorPct": null
  }
}
```

This is a deliberately plain request: Max Sharpe, Std Dev risk measure, historical mean returns, sample covariance, long-only, no group/turnover/tracking-error constraints, no comparison portfolio — the simplest case that still exercises every real result field, chosen so Task 3's Excel formulas stay tractable.

- [ ] **Step 4: Run the request and save the result**

```bash
curl -s -X POST http://127.0.0.1:8001/api/optimize \
  -H "Content-Type: application/json" \
  -d @docs/manual-verification-2026-08-11/request.json \
  > docs/manual-verification-2026-08-11/result.json
python3 -c "import json; d = json.load(open('docs/manual-verification-2026-08-11/result.json')); print('feasibility:', d['feasibility']); print('optimalWeights:', d['optimalWeights']); print('rolling folds:', len(d['rolling']))"
```
Expected: `feasibility: ok`, two weights in `optimalWeights` summing to ~100, and a `rolling folds:` count (this may legitimately be `0` — a 4-month test window is short, and if the rolling evaluator finds no foldable history in expanding mode with a 12-month lookback, an empty `rolling` list is a REAL, correct result to document in Task 3/4, not an error to work around).

If `feasibility` is not `ok`, STOP and report back with the full `result.json` — do not proceed with a request that didn't solve.

- [ ] **Step 5: Export the raw NAV slice**

```bash
python3 -c "
from backend.app.sec.cache import load_nav_panel
df = load_nav_panel(['M0209_2548', 'M0155_2547'])
df.to_csv('docs/manual-verification-2026-08-11/nav.csv')
print(df.tail(10))
"
```
Expected: prints the tail of the full NAV panel for both funds (this exports the FULL available history for both funds, not just the 4-month window — Task 3 needs history before 2024-02-29 to compute returns for the first return date and, for the Rolling sheet, to see the rolling evaluator's own training window). Confirm the printed dates include `2024-02` through `2024-05`.

- [ ] **Step 6: Commit**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
git add docs/manual-verification-2026-08-11/request.json docs/manual-verification-2026-08-11/result.json docs/manual-verification-2026-08-11/nav.csv
git commit -m "test: capture real optimize run + raw NAV for Phase 4 manual verification

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `docs/optimizer-formula-reference.md`

**Files:**
- Create: `docs/optimizer-formula-reference.md`

**Interfaces:**
- Consumes: `backend/app/optimizer/solvers.py`, `backend/app/optimizer/black_litterman.py`, `backend/app/optimizer/robust.py` (read-only — this task documents, does not modify, these files).
- Produces: the citation table Task 4 references when writing the narrative report's "does the code match its cited formula" section.

- [ ] **Step 1: Read the real code for each formula before citing it**

For each of these, open the file and read the actual riskfolio-lib call / computation, not just the function name:
- `backend/app/optimizer/solvers.py::solve_mean_variance` — the objective and risk-measure code passed to riskfolio-lib's `optimization()` call.
- `backend/app/optimizer/solvers.py`'s CVaR/CDaR risk-measure code paths (`RM_CODES` mapping — find where `"CVaR"` and `"CDaR"` map to riskfolio-lib's own `rm` codes).
- `backend/app/optimizer/solvers.py::solve_risk_parity`.
- `backend/app/optimizer/solvers.py::solve_hrp`.
- `backend/app/optimizer/solvers.py::risk_contribution_pct`.
- `backend/app/optimizer/black_litterman.py::compute_equilibrium_returns` and `blend_posterior`.
- `backend/app/optimizer/robust.py::resample_and_solve`.

- [ ] **Step 2: Write the document**

Create `docs/optimizer-formula-reference.md` with this structure (fill in the `<verify against code>` markers with the ACTUAL formula/parameters you read in Step 1 — do not leave them as literal placeholder text, they mark where Step 1's findings go):

```markdown
# Optimizer Formula Reference

Formulas used by `backend/app/optimizer/` (the optimization engine), with
academic/primary citations and the exact code location implementing each.
Companion to `docs/formula-reference.md`, which covers the backtest
engine's return/risk metrics (CAGR, volatility, Sharpe, Sortino, max
drawdown, tracking error) — reused as-is by this optimizer's Performance
and Rolling tabs, not duplicated here.

## Notation

- `w` — portfolio weight vector (n funds × 1)
- `μ` — expected return vector (n × 1)
- `Σ` — covariance matrix (n × n)
- `r_f` — risk-free rate
- `Π` — Black-Litterman equilibrium (implied) return vector

## Mean-Variance / Sharpe Ratio Maximization

**Formula:** maximize `(w'μ − r_f) / √(w'Σw)` subject to `Σw = 1`, `w ≥ 0` (long-only).

**Citation:** Markowitz, H. (1952). "Portfolio Selection." *Journal of
Finance*, 7(1), 77-91. Sharpe, W. F. (1966, revised 1994). "The Sharpe
Ratio." *Journal of Portfolio Management*.

**Code:** `backend/app/optimizer/solvers.py::solve_mean_variance` — <verify
against code: state the exact riskfolio-lib method/objective/rm_code used
and confirm it matches this formula>.

## Semi-Variance

**Formula:** downside-only variance, `E[min(R − target, 0)²]`, in place of
full variance in the same mean-risk objective above.

**Citation:** Markowitz, H. (1959). *Portfolio Selection: Efficient
Diversification of Investments*, Chapter 9 (semi-variance as a risk
measure more aligned with investor loss-aversion than full variance).

**Code:** `backend/app/optimizer/solvers.py`, `RM_CODES["semi_variance"]`
— <verify against code: state riskfolio-lib's exact `rm` code and confirm
target/threshold parameter matches>.

## CVaR (Conditional Value at Risk)

**Formula:** the Rockafellar–Uryasev linear-programming formulation of
CVaR at confidence level `α` — minimizes the expected loss in the worst
`(1-α)` tail, expressed as a convex (LP) problem rather than the naive
non-convex historical-quantile definition.

**Citation:** Rockafellar, R. T. & Uryasev, S. (2000). "Optimization of
Conditional Value-at-Risk." *Journal of Risk*, 2(3), 21-41.

**Code:** `backend/app/optimizer/solvers.py`, `RM_CODES["cvar"]` — <verify
against code: confirm `alpha`/`tail_confidence` wiring matches the
request's `tailConfidence` field>.

## CDaR (Conditional Drawdown at Risk)

**Formula:** the drawdown analogue of CVaR — expected drawdown in the
worst `(1-α)` tail of the drawdown distribution, also a convex (LP)
formulation.

**Citation:** Chekhlov, A., Uryasev, S. & Zabarankin, M. (2005).
"Drawdown Measure in Portfolio Optimization." *International Journal of
Theoretical and Applied Finance*, 8(1), 13-58.

**Code:** `backend/app/optimizer/solvers.py`, `RM_CODES["cdar"]` —
<verify against code>.

## Black-Litterman Posterior Returns

**Formula:** equilibrium (implied) returns `Π = δΣw_mkt` (reverse
optimization from market-cap weights and risk aversion `δ`), then blended
with investor views via the standard BL posterior:
`E[R] = [(τΣ)⁻¹ + P'ΩP]⁻¹ [(τΣ)⁻¹Π + P'Ω⁻¹Q]`.

**Citation:** Black, F. & Litterman, R. (1992). "Global Portfolio
Optimization." *Financial Analysts Journal*, 48(5), 28-43. He, G. &
Litterman, R. (1999). "The Intuition Behind Black-Litterman Model
Portfolios." Idzorek, T. (2004). "A Step-by-Step Guide to the
Black-Litterman Model" (view-confidence-to-Ω back-solving, already saved
locally at `docs/assets/idzorek-2004-black-litterman-guide.pdf`).

**Code:** `backend/app/optimizer/black_litterman.py::compute_equilibrium_returns`
and `blend_posterior` — <verify against code: confirm the equilibrium
formula's `risk_aversion` default and `blend_posterior`'s τ/Ω wiring match
this posterior formula>.

## HRP (Hierarchical Risk Parity)

**Formula:** three-stage algorithm — (1) hierarchical clustering of assets
by correlation distance, (2) quasi-diagonalization of the correlation
matrix by the clustering order, (3) recursive bisection allocating
inverse-variance weight down the resulting tree — avoiding matrix
inversion entirely (unlike mean-variance), which is HRP's stated
robustness advantage in-sample.

**Citation:** López de Prado, M. (2016). "Building Diversified Portfolios
that Outperform Out-of-Sample." *Journal of Portfolio Management*, 42(4),
59-69.

**Code:** `backend/app/optimizer/solvers.py::solve_hrp` — <verify against
code: confirm it calls riskfolio-lib's `HCPortfolio` with the stated
linkage method>.

## Risk Parity

**Formula:** weights such that each asset's marginal risk contribution is
equal: `wᵢ·(Σw)ᵢ = wⱼ·(Σw)ⱼ` for all i, j.

**Citation:** Maillard, S., Roncalli, T. & Teïletche, J. (2010). "The
Properties of Equally Weighted Risk Contribution Portfolios." *Journal of
Portfolio Management*, 36(4), 60-70.

**Code:** `backend/app/optimizer/solvers.py::solve_risk_parity` — <verify
against code>.

## Risk Contribution %

**Formula:** `RCᵢ = wᵢ·(Σw)ᵢ / w'Σw`, the fraction of total portfolio
variance attributable to asset i. Sums to 100% across all holdings.

**Citation:** same as Risk Parity above (this is the underlying quantity
risk parity equalizes).

**Code:** `backend/app/optimizer/solvers.py::risk_contribution_pct` —
<verify against code>.

## Robust Optimization (Monte Carlo Resampling)

**Formula:** Michaud resampling — bootstrap-resample the return panel's
rows (with replacement) N times, re-solve the SAME objective on each
resample, average the resulting WEIGHTS across every resample that solved
successfully (not the mu/sigma inputs). Confirmed via live research
against PortfolioVisualizer's own "Robust Optimization: Yes/No" toggle
(see `docs/optimization-assumptions.md`) as the real-world technique this
matches — distinct from riskfolio-lib's own separate Worst-Case
mean-variance model, which this project does not use.

**Citation:** Michaud, R. O. (1989). "The Markowitz Optimization Enigma:
Is 'Optimized' Optimal?" *Financial Analysts Journal*, 45(1), 31-42.
Michaud, R. O. & Michaud, R. O. (2008). *Efficient Asset Management: A
Practical Guide to Stock Portfolio Optimization and Asset Allocation*
(2nd ed.), Oxford University Press — the full resampled-efficiency method.

**Code:** `backend/app/optimizer/robust.py::resample_and_solve` — <verify
against code: confirm the resample count (500), the >=50% success
threshold before falling back to single-shot, and that weights (not
mu/sigma) are what gets averaged>.

## Verification Table

| Formula | Cited source matches code? | Notes |
| --- | --- | --- |
| Mean-Variance / Sharpe | <yes/no + reason> | |
| Semi-Variance | <yes/no + reason> | |
| CVaR | <yes/no + reason> | |
| CDaR | <yes/no + reason> | |
| Black-Litterman posterior | <yes/no + reason> | |
| HRP | <yes/no + reason> | |
| Risk Parity | <yes/no + reason> | |
| Risk Contribution % | <yes/no + reason> | |
| Robust Optimization resampling | <yes/no + reason> | |
```

Every `<verify against code: ...>` and `<yes/no + reason>` marker must be
replaced with the real finding from Step 1 before this file is committed —
none may be left as literal bracketed text. If a formula genuinely cannot
be fully confirmed from the code alone (e.g. riskfolio-lib's internal
numerical formulation isn't visible without reading riskfolio-lib's own
source), write that explicitly as the finding ("could not fully verify
riskfolio-lib's internal CVaR implementation without reading its source;
confirmed the `rm` code and `alpha` parameter are correctly wired") rather
than silently marking it as a match.

- [ ] **Step 3: Commit**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
git add docs/optimizer-formula-reference.md
git commit -m "docs: add optimizer-formula-reference.md with citations + code verification table

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Excel verification workbook

**Files:**
- Create: `docs/manual-verification-2026-08-11.xlsx`
- Create (temporary, may be deleted after use or kept for reproducibility — implementer's choice, note the choice in the Task 4 report): a Python script that builds the workbook via `openpyxl`, e.g. `docs/manual-verification-2026-08-11/build_workbook.py`

**Interfaces:**
- Consumes: `docs/manual-verification-2026-08-11/nav.csv` and `docs/manual-verification-2026-08-11/result.json` (both from Task 1 — read-only, do not regenerate).
- Produces: `docs/manual-verification-2026-08-11.xlsx`, consumed by Task 4 for the diff-and-report step.

- [ ] **Step 1: Confirm `openpyxl` is available**

```bash
source /private/tmp/sec_open_data_portfolio_backtester_venv/bin/activate
python3 -c "import openpyxl; print(openpyxl.__version__)"
```
Expected: a version string. If `ModuleNotFoundError`, install it in the venv: `python3 -m pip install openpyxl` (it's a dev-time verification tool, not a runtime dependency — do not add it to `pyproject.toml`).

- [ ] **Step 2: Build a `NAV` sheet — raw data, no formulas**

Load `nav.csv` and write it verbatim into a sheet named `NAV`: column A = date, column B = K-SET50 NAV, column C = M-S50 NAV, one row per date, header row 1. This is the single source every other sheet's formulas reference — no other sheet re-types a NAV value.

- [ ] **Step 3: Build a `Returns` sheet — live formulas from `NAV`**

Column A = date (from row 2 onward, one row shorter than NAV since return needs a prior period), column B = K-SET50 monthly return (Excel formula `=NAV.B3/NAV.B2-1` for row 2, referencing consecutive NAV rows — not a pasted number), column C = M-S50 monthly return, same pattern. Restrict to the 4 return observations inside `2024-02-29` to `2024-05-31` in a separate labeled range (or a second small table on the same sheet) so later sheets can reference "the test-window returns" specifically, since `NAV`/`Returns` cover the fund's full history.

- [ ] **Step 4: Build a `Weights` sheet**

Row 1: fund names. Row 2: `optimalWeights` from `result.json`, entered as a plain value (this is the one place a JSON value is entered directly — it's the GIVEN input for this sheet's checks, not something being independently verified; Task 3's later "full-solve replication" sheet is where the weights themselves get checked). Below that, live formulas computing:
- Portfolio expected return: `=SUMPRODUCT(weights_range, mean_return_range)` where `mean_return_range` is `=AVERAGE()` over each fund's test-window returns from the `Returns` sheet.
- Covariance matrix Σ (2×2): `=COVARIANCE.S(K-SET50 test-window returns, M-S50 test-window returns)` for the off-diagonal, `=VAR.S(...)` for each diagonal entry.
- Portfolio variance: `=MMULT(MMULT(TRANSPOSE(weights), covariance_matrix), weights)` (array formula) or the expanded scalar form `w1²σ1² + w2²σ2² + 2w1w2σ12` — either is acceptable as long as it's a live formula, not a typed number.
- Portfolio volatility: `=SQRT(portfolio_variance)`.
- Risk contribution % per fund: `=(weight_i * (covariance_matrix row i · weights)) / portfolio_variance`, expressed as a live formula referencing the cells above.
- A comparison column: `result.json`'s `riskContributionPct` value pasted alongside, with a `=ABS(computed - given) < 0.000001` check column.

- [ ] **Step 5: Build a `Frontier` sheet**

For each point in `result.json`'s `frontier` array: paste that point's own `weights` (given, same reasoning as Step 4), then live-formula-recompute `volatilityPct`, `expectedReturnPct`, and `sharpe` from those weights using the SAME covariance/mean-return approach as Step 4, compared against the point's own stated values in a diff column.

- [ ] **Step 6: Build a `Performance` sheet**

Using the portfolio's realized monthly return series (weights × each month's fund returns, live formula, for the 4-month test window), compute — matching `docs/formula-reference.md`'s already-cited formulas exactly (open that file and use its exact formulas, do not improvise different ones):
- CAGR (`docs/formula-reference.md`'s `annualized_return` formula)
- Annualized volatility (`annualized_volatility` formula)
- Sharpe (ex-post, from the realized series)
- Sortino (`sortino_ratio` formula — note `result.json`'s `sortino`/`sharpeExPost`/`bestYearPct`/`worstYearPct`/`maxDrawdownPct` may be `null`; if so, record "correctly null — undefined for this short a window" in the diff column rather than treating a null as a mismatch)
- Max drawdown (`max_drawdown` formula) over the 4-month realized series
Compare each computed value against `result.json`'s `performanceSummary` array (there should be one entry, since `compareAgainst: "none"` in the request means no second column).

- [ ] **Step 7: Build a `Rolling` sheet**

If `result.json`'s `rolling` array is non-empty: for each fold, recompute the fold's realized return/volatility/Sharpe from `NAV`/`Returns` sheet data over that fold's stated period, compared against the fold's given values. If `result.json`'s `rolling` array is empty (a real, valid outcome for this short a test window — see Task 1 Step 4's note): write a single row stating "0 folds returned — expected given a 4-month window with a 12-month expanding lookback; not a defect" rather than leaving the sheet blank with no explanation.

- [ ] **Step 8: Build a `Report` sheet**

A simple cross-reference table: for each of `result.json`'s top-level scalar fields shown in the app's Report tab (feasibility, selectedRiskMeasure, totalTurnoverPct, generatedAt, and any non-null note fields), confirm the value matches what's shown on the corresponding sheet above (e.g. `selectedRiskMeasure.optimizedValue` should equal the `Weights` sheet's computed portfolio volatility, since `riskMeasure: "std_dev"` in the request). This is an internal-consistency check across sheets, not a new computation.

- [ ] **Step 9: Build a `FullSolveReplication` sheet**

Independently solve the unconstrained 2-asset Max Sharpe tangency portfolio by its closed-form solution, using ONLY `Returns` sheet data (not `result.json`):
- `μ` = each fund's mean test-window return (already computed in Step 3/4).
- `Σ` = the 2×2 covariance matrix (already computed in Step 4).
- Excess return vector: `μ_excess = μ - r_f` where `r_f` = the request's `riskFreeRatePct` (1.5%, converted to the same periodicity as the returns — monthly, so divide by 12).
- Unnormalized tangency weights: `Σ⁻¹ · μ_excess`, computed via Excel's `MINVERSE` and `MMULT` array functions on the 2×2 `Σ`.
- Normalize to sum to 1: divide each unnormalized weight by their sum.
- Compare this independently-derived weight vector against `result.json`'s `optimalWeights`, to 6 decimal places, in a diff column. This is the ONE place the actual solve is checked, not just the reporting layer.

- [ ] **Step 10: Run the build script and confirm the file exists**

```bash
python3 docs/manual-verification-2026-08-11/build_workbook.py
ls -la docs/manual-verification-2026-08-11.xlsx
```
Expected: the file exists and is non-trivial in size (openpyxl-written `.xlsx` with formulas, typically several KB minimum).

- [ ] **Step 11: Commit**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
git add docs/manual-verification-2026-08-11.xlsx docs/manual-verification-2026-08-11/build_workbook.py
git commit -m "test: build Excel verification workbook for Phase 4 manual verification

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Diff, narrative report, and TDD fix loop

**Files:**
- Create: `docs/manual-verification-2026-08-11.md`
- Conditionally create: `backend/tests/test_<area>_regression.py` (only if a real mismatch is found)
- Conditionally modify: `backend/app/engine/<file>.py` or `backend/app/optimizer/<file>.py` (only if a real mismatch is found, whichever file owns the wrong formula)

**Interfaces:**
- Consumes: `docs/manual-verification-2026-08-11.xlsx` (Task 3), `docs/optimizer-formula-reference.md` (Task 2), `docs/manual-verification-2026-08-11/result.json` (Task 1).
- Produces: the final written record of this phase's findings — nothing downstream in this plan consumes this task's output, it is the deliverable.

- [ ] **Step 1: Open the workbook and read every diff column**

Since a live-formula `.xlsx` can't be evaluated by grep, open it with a tool that computes formula results (e.g. `libreoffice --headless --convert-to csv` per sheet, or a Python `xlcalculator`/`formulas` library if available, or manually via a spreadsheet application) — confirm the computed values, not just that formulas exist syntactically. For each sheet built in Task 3, read every diff/comparison column's result.

- [ ] **Step 2: Write the narrative report**

Create `docs/manual-verification-2026-08-11.md`:

```markdown
# Manual Verification — 2026-08-11

**Test case:** K-SET50 (M0209_2548) + M-S50 (M0155_2547), 2024-02-29 to
2024-05-31, monthly frequency, Max Sharpe / Std Dev / historical mean /
sample covariance, long-only, no constraints, no comparison. Raw request/
result/NAV: `docs/manual-verification-2026-08-11/`. Excel workbook:
`docs/manual-verification-2026-08-11.xlsx`.

## Per-sheet results

<one subsection per Task 3 sheet: Weights, Frontier, Performance, Rolling,
Report, FullSolveReplication — for each, state PASS/FAIL per row/metric,
with the actual computed-vs-given numbers for anything that didn't match
exactly, and the root cause if it's a real mismatch vs. expected floating-
point noise>

## Formula citation verification

<summarize docs/optimizer-formula-reference.md's Verification Table result
here — how many formulas matched their citation, any that didn't>

## Mismatches found and fixed

<for each real mismatch: what was wrong, the failing test written first
(file:line), the fix (file:line), confirmation the test now passes. If
zero real mismatches were found, state that explicitly: "No mismatches
found beyond floating-point noise under 1e-6 — every checked value in
every sheet matched its independently-computed counterpart.">

## Known limitations of this verification pass

- CVaR/CDaR/Black-Litterman/HRP's actual convex-optimization solves were
  NOT independently replicated in Excel (LP/hierarchical-clustering/
  matrix-algebra machinery, out of scope per the design spec) — only the
  Max Sharpe case got a full-solve replication (FullSolveReplication
  sheet). Those three objectives' REPORTING (given their own solved
  weights) was still fully verified in the Weights/Frontier/Performance
  sheets if a request with those objectives is tested in a future pass —
  this pass only ran Max Sharpe.
```

- [ ] **Step 3: If Step 1 found a real mismatch — write the failing test first**

For each real mismatch (not floating-point noise), identify the exact
function in `backend/app/engine/` or `backend/app/optimizer/` computing
the wrong value (cross-reference against `docs/optimizer-formula-reference.md`'s
code-location column or `docs/formula-reference.md`'s existing Source
Mapping section). Write a new test in `backend/tests/` reproducing the
exact mismatch using this plan's fixed test case's real numbers (from
`docs/manual-verification-2026-08-11/result.json` and the Excel workbook's
independently-computed value), run it, confirm it FAILS for the stated
reason before touching any implementation code.

- [ ] **Step 4: If a mismatch was found — fix it**

Fix the identified function. Re-run the new test, confirm it PASSES. Run
the full backend suite (`pytest`) to confirm nothing else broke. Update
`docs/manual-verification-2026-08-11.md`'s "Mismatches found and fixed"
section with the resolution.

- [ ] **Step 5: Commit**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
git add docs/manual-verification-2026-08-11.md
# If Step 3/4 produced a fix, also:
# git add backend/tests/test_<area>_regression.py backend/app/<engine-or-optimizer>/<file>.py
git commit -m "docs: record Phase 4 manual verification findings

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Stop the backend**

```bash
pkill -f "uvicorn backend.app.main:app --port 8001"
```
