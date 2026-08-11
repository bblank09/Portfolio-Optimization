# Manual Verification — 2026-08-11

**Test case:** K-SET50 (M0209_2548) + M-S50 (M0155_2547), 2024-02-29 to
2024-05-31, monthly frequency, Max Sharpe / Std Dev / historical mean /
sample covariance, long-only, no constraints, no comparison. Raw request/
result/NAV: `docs/manual-verification-2026-08-11/`. Excel workbook:
`docs/manual-verification-2026-08-11.xlsx`.

**How the workbook was read.** A live-formula `.xlsx` carries no cached
results, so the workbook was recalculated headlessly with LibreOffice
(`soffice --headless --convert-to xlsx`) into a scratch copy, then every
sheet was dumped with `openpyxl.load_workbook(..., data_only=True)` — the
values below are LibreOffice's evaluation of the formula chains, not the
formula strings. Zero error cells (`#REF!`/`#VALUE!`/`#DIV/0!`) in any
sheet. Every diff column on every sheet was read, not a sample.

## Per-sheet results

### NAV / Returns — PASS

`NAV` is the raw `nav.csv` panel (2,715 daily observations per fund),
loaded verbatim; nothing to verify. `Returns` derives daily simple returns
from it and, in the side block, pulls the four month-end anchors out by
live `INDEX`/`MATCH`.

The anchors resolve to 2024-02-29, 2024-03-29, 2024-04-30, 2024-05-31 —
March's anchor is the 29th because 2024-03-30/31 were non-trading days.
Four anchors yield **3** monthly returns, matching `result.json`'s
3-element `monthlyReturnsPct` exactly. (The design brief anticipated 4;
the real trading calendar yields 3. The engine is right; the brief's expectation was off by one.)

Monthly returns computed live: M0209_2548 `+0.01201245 / −0.00061918 /
−0.01226610`; M0155_2547 `+0.01197608 / −0.00052307 / −0.04126326`.

### Weights — PASS (all 8 diff cells zero)

| Checked value | Live from NAV | Given (`result.json`) | Diff |
| --- | --- | --- | --- |
| M0209_2548 expected return % | −0.34913103 | −0.35 | 0 |
| M0155_2547 expected return % | −11.92409855 | −11.92 | 0 |
| M0209_2548 annualized vol % | 4.20632094 | 4.21 | 0 |
| M0155_2547 annualized vol % | 9.64408538 | 9.64 | 0 |
| Portfolio expected return % | −0.63944442 | −0.64 (`optimalPoint`) | 0 |
| Correlation | 0.94904623 | 0.95 | 0 |
| Portfolio annualized vol % | 4.33105219 | 4.33 (`selectedRiskMeasure.optimizedValue`) | 0 |
| Risk contribution % | 94.66952 / 5.33048 | 94.67 / 5.33 | 0 |

Weights sum to exactly 1. The diff tolerance is 0.005 rather than 1e-6
because the API rounds its reported values to 2 dp; the computed side is
rounded to 2 dp before differencing, so an exact match shows as literal 0.
Every one did.

Live sample covariance (monthly): `s11 = 0.00014744`, `s12 = 0.00032083`,
`s22 = 0.00077507`.

### Frontier — PASS

`result.json`'s frontier holds a single point — 100% M0209_2548 — because
`maxHoldings = 2` over a 2-fund universe with a 3-observation window
collapses the efficient set to its corner. Recomputing that point's
volatility, expected return and Sharpe from the workbook's own Σ/μ:
4.20632094 % vs. given 4.21 (diff 0), −0.34913103 % vs. −0.35 (diff 0),
Sharpe −0.43960769 vs. −0.44 (diff 0). PASS.

### Performance — PASS (all 8 metric diffs zero)

Portfolio monthly returns recomputed from the weights and the fund
returns: `+1.201154 % / −0.061677 % / −1.299338 %` vs. given
`monthlyReturnsPct` `1.2 / −0.06 / −1.3` — diff 0 on all three.

| Metric (`formula-reference.md` name) | Live | Given | Diff |
| --- | --- | --- | --- |
| CAGR % (`annualized_return`) | −0.69974817 | −0.70 | 0 |
| Expected arithmetic annualized return % | −0.63944442 | −0.64 | 0 |
| Annualized volatility % | 4.33105219 | 4.33 | 0 |
| Max drawdown % | −1.36021372 | −1.36 | 0 |
| Sharpe ex-post | −0.50790156 | −0.51 | 0 |
| Sharpe ex-ante | −0.49397798 | −0.49 | 0 |
| Sortino | −0.84553605 | −0.85 | 0 |
| `bestYearPct` / `worstYearPct` | not computable | `null` | correct |

`bestYearPct`/`worstYearPct` being `null` is correct, not missing data —
they are undefined over 3 monthly observations (< 1 calendar year).

### Rolling — PASS (vacuously, and correctly so)

`result.rolling` is an empty array. The request spans 3 monthly return
observations while `constraints.lookbackPeriodMonths = 12` with
`rollingWindowMode = "expanding"`. A 12-month lookback cannot be satisfied
even once inside a ~4-month window, let alone the 2 folds the evaluator
requires. The backend says exactly this in `result.robustNote`. There is
no fold data to recompute; the verification performed is that **zero folds
is the arithmetically forced outcome of the request's own parameters** —
it is.

### Report — PASS (13/13 cross-references OK)

Every top-level scalar in `result.json` agrees with what the earlier
sheets' live formulas produce or with the request that generated it:
`feasibility = ok` (weights sum to 1, all within [0, 100]);
`selectedRiskMeasure.measure = std_dev` matches the request;
`optimizedValue`/`optimalPoint.volatilityPct` = 4.33 vs. live 4.33105219;
`optimalPoint.expectedReturnPct` = −0.64 vs. −0.63944442;
`gmvPoint.volatilityPct` and `tangencyPoint.volatilityPct` = 4.21 vs.
4.20632094; `totalTurnoverPct` = 50, i.e. `0.5 × Σ|w_target − w_current|`
with `currentWeightPct` empty (all current weights 0) giving `0.5 × 100 %`.
`feasibilityMessage`, `compareNote`, `constraintNote` and
`robustOptimizationNote` are all correctly `null` given
`compareAgainst = "none"`, `groupConstraintsEnabled = false`,
`robustOptimization = false`.

### FullSolveReplication — the one sheet that did NOT reconcile

This is the only sheet that re-derives the **weights** rather than the
reporting layer, and it is where Finding B (below) came from.

Two independent replications were run:

1. **Closed-form unconstrained tangency** (2×2 `Σ⁻¹(μ − r_f)`, cross-checked
   against `MMULT(MINVERSE(...))`): normalized weights
   **193.18 % / −93.18 %**, vs. `result.json`'s 97.49 % / 2.51 %. **This
   disagreement is EXPECTED and is not evidence of a bug** — the closed
   form is unconstrained and wants a short position the request forbids
   (`longOnly = true`), and it is additionally degenerate here because both
   assets' excess returns are negative. It is recorded as a documented
   non-comparison, not a finding.

2. **Long-only Sharpe grid search** — the meaningful check. Scoring every
   long-only mix on the identical annualized-Sharpe formula shows Sharpe
   increasing monotonically all the way to the corner: the workbook's own
   21-point grid (0.05 steps) peaks at **w(M0209_2548) = 1.00, Sharpe
   −0.43961**, while `result.json`'s `optimalWeights` (97.49 % / 2.51 %)
   score **−0.49398** on the same formula — worse by 0.0544. Re-run
   independently at 2,001 points (0.0005 steps) during this task, the
   argmax is still exactly 1.00 with the same −0.4396076898: the true
   long-only optimum genuinely is the corner, not an interior point.

That is a real internal-consistency defect: the same response's own
`frontier[0]`, `gmvPoint` and `tangencyPoint` all sit at the 100 % corner,
so the solver disagrees with its own reporting layer for the same request.
See Finding B.

## Formula citation verification

`docs/optimizer-formula-reference.md`'s Verification Table covers 9
formula families. **6 of 9 matched their citation outright** —
Mean-Variance/Sharpe, Black-Litterman posterior, HRP, Risk Parity, Risk
Contribution %, and Robust-Optimization resampling. Semi-Variance (1 of 9)
matched with two documented caveats (riskfolio-lib fixes the semi-deviation
target at the sample mean with no MAR parameter, and minimizes the
deviation rather than the semi-variance — the argmin is unchanged by the
monotone square root). That leaves 2 of 9 — CVaR and CDaR — which had a
real bug at the time of the audit, now fixed (6 clean + 1 caveated + 2
bug-then-fixed = 9).

The two that did **not** match outright were **CVaR and CDaR**: both LP
*formulations* are literally Rockafellar–Uryasev and
Chekhlov–Uryasev–Zabarankin as cited, but the tail level `alpha` was never
wired into the solve. That is Finding A, and it is now fixed; the
Verification Table has been updated to record the fix.

Three items were explicitly out of reach of a citation-level audit and are
recorded as such in that document: riskfolio-lib's CLARABEL interior-point
numerics and internal `k`-rescaling, `HCPortfolio`'s recursive-bisection
body, and — added by this pass — the degenerate-Sharpe branch discussed in
Finding B, which is precisely a defect in that unaudited `k`-rescaling
path.

## Mismatches found and fixed

### Finding A — CVaR/CDaR `tailConfidence` never reached the solver (FIXED)

**What was wrong.** `_build_portfolio` in
`backend/app/optimizer/solvers.py` built the `rp.Portfolio`, set `mu`,
`cov`, `ainequality`/`binequality`, the goal targets and `rf` — but never
set `port.alpha`. `rp.Portfolio.optimization()` takes no `alpha` argument;
it reads `self.alpha`, whose constructor default is `0.05`. So **every**
CVaR and CDaR solve ran at a 95 % tail regardless of
`request.tailConfidence`, which the UI offers at 95 / 97.5 / 99.

Only the POST-solve reporting honored the request: `realized_risk` and
`risk_contribution_pct` both pass `_tail_alpha(request)` explicitly. A 99 %
CVaR request therefore got 99 %-labelled, 99 %-measured reporting computed
on top of a 95 %-solved portfolio. The bug is completely invisible at
`tailConfidence = 95` (which coincides with the accidental default) and
silently wrong at 97.5 % and 99 %.

This defect was flagged during Task 2's citation audit (which was
documentation-only and did not fix it); this pass confirmed it
independently by direct solve.

**Failing test written first.**
`backend/tests/test_optimizer_tail_alpha_regression.py` (new file, 3 tests).
The fixture builds two assets whose tail ranking deliberately *flips*
between the 5 % and the 1 % tail: identical bodies, but asset A gets two
catastrophic months (inside the worst 1 % of 240 observations) while asset
B gets twelve moderately bad months (inside the worst 5 %, never inside the
worst 1 %). A solver honoring `alpha` must return substantially different
portfolios at 95 % vs. 99 %; one ignoring it returns identical weights.

- `test_cvar_solve_honors_tail_confidence` (line 82)
- `test_cdar_solve_honors_tail_confidence` (line 101)
- `test_default_tail_confidence_is_unchanged_by_the_alpha_wiring` (line 110)
  — the regression guard, pinning the pre-fix 95 % solution as literal
  numbers captured from the unfixed code.

Run against the unfixed `solvers.py` (verified by forcing `port.alpha =
0.05` regardless of `request.tailConfidence`, reproducing the pre-fix
behavior against the exact fixture in
`backend/tests/test_optimizer_tail_alpha_regression.py`): the first two
**FAIL** with weights byte-identical across confidences — CVaR
`{A: 79.2952, B: 20.7048}` at both 95 % and 99 %; CDaR
`{A: 16.2363, B: 83.7637}` at both — and the guard passes. That is the
bug's observable symptom. Note the pre-fix CDaR number is identical to the
post-fix CDaR-95 % number below (both solved with `alpha = 0.05`, since
95 % coincidentally maps to the same value the unfixed code always used);
only the pre-fix-99 % number differs from post-fix, since pre-fix the 99 %
request never actually reached `alpha = 0.01`.

**The fix.** `backend/app/optimizer/solvers.py:179-187` — in
`_build_portfolio`, after `port.rf`, add `port.alpha = _tail_alpha(request)`,
reusing the existing helper (not a duplicate of its logic) so the solve and
the reporting can never disagree. It is a no-op for MV/MSV, which ignore
`alpha`.

**Result.** All 3 tests pass. Post-fix the tail confidence visibly drives
the allocation: CVaR 95 % → `{A: 79.30, B: 20.70}` but 99 % →
`{A: 20.80, B: 79.20}`; CDaR 95 % → `{A: 16.24, B: 83.76}` vs. 99 % →
`{A: 21.86, B: 78.14}`. The 95 % default is unchanged to within 1e-6, as
required. Full backend suite re-run green.

Note this finding does **not** affect the verified test case's numbers:
that request uses `riskMeasure = "std_dev"` at `tailConfidence = 95`, where
`alpha` is both ignored by the risk measure and coincidentally correct.

### Finding B — Max Sharpe returns a dominated interior point when all excess returns are negative (ROOT CAUSE IDENTIFIED, FIX DEFERRED)

**What is wrong.** For this test case the solver's own `optimalWeights`
(97.49 % / 2.51 %, annualized Sharpe −0.49398) are dominated on both axes
by the same response's `frontier[0]` / `gmvPoint` / `tangencyPoint`
(100 % M0209_2548, Sharpe −0.43961). A 2,001-point long-only grid search
confirms the corner is the true long-only maximum. The solver disagrees with its own reporting layer.

**Root cause — located, and it is in riskfolio-lib, not in this project.**
`solve_mean_variance` calls `port.optimization(model="Classic", rm="MV",
obj="Sharpe", rf=port.rf, l=0, hist=True)`. riskfolio-lib solves the Sharpe
objective by the Charnes–Cooper homogenization (variables `y = k·w`), and
at `src/Portfolio.py:3450-3461` it branches:

```python
elif kelly is None:
    if (mu < 0).all():
        constraints += [risk <= 1]
        objective = cp.Maximize(ret - rf0 * k - penalty_factor)
    else:
        constraints += [ret - rf0 * k == 1]
        objective = cp.Minimize(risk * 1000 + penalty_factor * 1000)
```

The normal branch (`ret − rf·k == 1`, minimize risk) is infeasible when no
long-only portfolio has positive excess return, so the library falls back
to the `(mu < 0).all()` branch. **That fallback is degenerate.** Along any
fixed direction `w₀` with Sharpe `s < 0`, scaling `y = t·w₀` gives
objective `t·(ret(w₀) − r_f) < 0` under `t·risk(w₀) ≤ 1`; since the
numerator is negative, the objective is maximized by driving `t → 0`, not
by binding the risk constraint. The supremum is 0 and is approached at
`y = 0, k = 0` for *every* direction, so the program has no interior
maximizer and the returned weights are whatever the interior-point solver's
numerical drift lands on, normalized by `sum(w)`. Hence 97.49 % / 2.51 %.

**Evidence.** Three checks, all on the real test case:

1. The same request with every other objective lands cleanly on the corner:
   `obj="MinRisk"` → `{M0209_2548: 1.0}`, `obj="MaxRet"` → `{1.0}`,
   `obj="Utility"` → `{1.0}`. Only `obj="Sharpe"` returns the interior
   point. That isolates the defect to the Sharpe reformulation, exactly as
   hypothesized.
2. Shifting μ upward so the all-negative branch is not taken
   (`μ + 5`, `μ + 20`) makes `obj="Sharpe"` return `{M0209_2548: 1.0,
   M0155_2547: 0.0}` — the corner. The geometry is fine; the branch is not.
3. A *small* upward shift (`μ + 0.35`, enough to make one μ positive but
   not the excess return) makes riskfolio raise `"The problem doesn't have
   a solution with actual input parameters"` — the `ret − rf·k == 1`
   branch going infeasible, which is what motivates the degenerate fallback
   in the first place.

**`rf` periodicity was checked and is correct** — it was the first
hypothesis and it is not the cause. `port.mu` and `port.cov` are both
annualized (`inputs.build_mu_sigma` annualizes, `_build_portfolio` divides
out the percent scaling), and `port.rf = risk_free_rate_pct / 100 = 0.015`
is likewise annual. For `rm="MV"` with `hist=True` the objective reads
`port.cov`, not the monthly `returns` panel, so all three inputs are on the
same annual footing. No mismatch.

**Why no fix was applied.** Maximizing a Sharpe ratio that is negative
everywhere on the feasible set is not a convex or quasi-concave problem —
the ratio `(μ'w − r_f)/σ(w)` with a negative numerator is quasi-*convex*,
so it has no drop-in convex reformulation. There is no wrong sign, no
periodization error, and no solver parameter to set. Fixing it means a
deliberate design decision — for example, detecting an all-negative excess
regime and switching the objective (to minimum variance, or to maximizing
return per unit risk under a fixed risk budget), and deciding what the API
should then report and how the UI should label it. Per this task's scope
rule, that decision is escalated rather than patched ad hoc, so no
special-case code was written.

**Practical severity.** The wrong answer is bounded and the regime is
narrow: it requires *every* asset's excess return over the window to be
negative, and here it costs 0.054 of annualized Sharpe (−0.494 vs. −0.440).
But it is silent — the response looks internally coherent unless you
compare `optimalWeights` against `tangencyPoint`, which is exactly what
this pass did. Recommended options, in order: (a) detect the all-negative
excess regime and return the frontier/tangency corner as `optimalWeights`
with an explanatory `feasibilityMessage`; (b) detect it and fall back to
`obj="MinRisk"` with a note; (c) leave the behavior and add a warning note
only. All three are product decisions.

## Known limitations of this verification pass

- CVaR/CDaR/Black-Litterman/HRP's actual convex-optimization solves were
  NOT independently replicated in Excel (LP/hierarchical-clustering/
  matrix-algebra machinery, out of scope per the design spec) — only the
  Max Sharpe case got a full-solve replication (FullSolveReplication
  sheet). Those three objectives' REPORTING (given their own solved
  weights) was still fully verified in the Weights/Frontier/Performance
  sheets if a request with those objectives is tested in a future pass —
  this pass only ran Max Sharpe.
- Finding A's fix is verified by targeted regression tests against a
  synthetic tail-asymmetric fixture, not by an Excel replication of the
  CVaR LP — replicating Rockafellar–Uryasev in a spreadsheet is the same
  out-of-scope LP machinery noted above.
- Finding B is diagnosed but not fixed; see its section for the reasoning
  and the options.
