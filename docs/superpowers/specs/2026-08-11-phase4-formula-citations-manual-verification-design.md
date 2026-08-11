# Phase 4: Formula Citations + Manual Verification — Design

Status: **approved, not yet implemented.**

## Why this exists

The user's Phase 4 checklist (4.1–4.5) originally referenced tabs (Summary,
Growth, Drawdown, Returns, Metrics, Cashflows, Rebalancing) that belong to
the sibling **Backtest Portfolio** project's 8-9-tab result view, not this
project's real 6-tab result view (Summary, Frontier, Weights, Performance,
Rolling, Report). Confirmed with the user: this Phase 4 targets **this**
project (Portfolio Optimization), adapted to its real tabs and its real
formulas (riskfolio-lib solvers, not backtest cashflow/rebalancing math).

Two gaps exist today:

1. `docs/formula-reference.md` (458 lines, rigorously cited) covers only the
   *backtest engine*'s formulas (TWRR, cashflow/cost accounting, rebalance
   turnover) — none of which the optimizer itself uses. `docs/
   optimization-assumptions.md` (145 lines) is a design/decision doc with a
   loose source list, not a per-formula academic citation table.
2. No hand-verification of the optimizer's real output against an
   independently-computed source of truth has ever been done — every prior
   sub-project's testing was code-level (pytest), not a human tracing every
   number back to a formula by hand.

## Scope

**In scope:** a new `docs/optimizer-formula-reference.md` covering every
formula the optimizer actually uses, cited against academic/primary sources;
a code-vs-doc verification table; one real `POST /api/optimize` run against
the live backend and cache; an Excel workbook hand-computing every metric
across the real 6 tabs from raw NAV data and comparing to 6 decimals; one
additional full-solve replication (closed-form 2-asset Max Sharpe tangency
portfolio) as a genuine solver-correctness check; a written verification
report; a TDD fix loop for any real mismatch found.

**Out of scope:** full hand-replication of CVaR/CDaR/Black-Litterman/HRP's
actual solves (LP/hierarchical-clustering/matrix-algebra machinery — treated
as validated by riskfolio-lib's own upstream test suite, not re-derived by
hand); any change to `docs/formula-reference.md` itself (already correct for
its own scope, the backtest engine, which the optimizer's Performance/
Rolling tabs reuse as-is — this doc cross-links to it rather than
duplicating).

## 1. `docs/optimizer-formula-reference.md`

Same structure and rigor as `docs/formula-reference.md`: one `##` section
per formula, each with the formula itself, an academic/primary citation, and
the exact `file:line` in `backend/app/optimizer/` implementing it.

| Section | Formula | Primary citation | Code location |
| --- | --- | --- | --- |
| Mean-Variance / Sharpe | max (w'μ − r_f) / √(w'Σw) | Markowitz (1952); Sharpe (1966/1994) | `solvers.py::solve_mean_variance` |
| Semi-Variance | downside-only variance below target | Markowitz (1959), Ch. 9 | riskfolio-lib `rm="MSV"` call site in `solvers.py` |
| CVaR | Rockafellar–Uryasev formulation | Rockafellar & Uryasev (2000) | `rm="CVaR"` call site in `solvers.py` |
| CDaR | conditional drawdown at risk | Chekhlov, Uryasev & Zabarankin (2005) | `rm="CDaR"` call site in `solvers.py` |
| Black-Litterman posterior | Bayesian blend of equilibrium Π + views | Black & Litterman (1992); He & Litterman (1999); Idzorek (2004) for view-confidence-to-Ω | `black_litterman.py` |
| HRP | recursive bisection over quasi-diagonalized correlation dendrogram | López de Prado (2016) | `solvers.py::solve_hrp` |
| Risk Parity | equal risk contribution | Maillard, Roncalli & Teïletche (2010) | `solvers.py::solve_risk_parity` |
| Risk contribution % | wᵢ·(Σw)ᵢ / w'Σw | same as above | `solvers.py::risk_contribution_pct` |
| Robust optimization (Monte Carlo resampling) | bootstrap-resample rows, average weights across successful resolves | Michaud (1989); Michaud & Michaud (2008) | `robust.py::resample_and_solve` |
| Rolling/performance metrics | CAGR, volatility, Sharpe, Sortino, max drawdown, tracking error | **already cited in `docs/formula-reference.md`** — cross-linked, not duplicated | `engine/metrics.py` (reused as-is) |

Each row's formula is verified directly against the cited source and the
actual code at the stated location — not assumed. A **verification table**
(same doc, final section) records per formula: matches / deviates (with
reason) / could not verify (with what's blocking it), which serves as 4.2's
deliverable — a byproduct of writing 4.1 carefully, not a separate pass.

## 2. Real run + Excel verification

**Fixed test case** (confirmed against the live cache, no data gaps):
funds = K-SET50 (`proj_id=M0209_2548`) + M-S50 (`proj_id=M0155_2547`),
period **2024-02-29 to 2024-05-31** (4 months, monthly frequency — inside
the pair's real testable range, `2015-01-31` to `2024-06-30`, confirmed live
via `GET /api/funds/testable-range?proj_ids=M0209_2548,M0155_2547`), goal =
Max Sharpe, long-only, no other constraints.

**4.3:** `POST /api/optimize` against the real running backend with this
request. Save the request JSON, response JSON, and the raw NAV slice pulled
directly from the parquet cache for these two funds/dates to
`docs/manual-verification-2026-08-11/` (request.json, result.json, nav.csv)
— the Excel's ground truth, so every downstream number traces back to a
file in the repo, not a value typed from memory.

**4.4:** `docs/manual-verification-2026-08-11.xlsx`, one sheet per real tab,
each following: **raw NAV → returns → weights (given from result.json) →
the tab's metrics**, computed with live Excel formulas (not pasted Python
output), diffed against `result.json` to 6 decimal places:

- **Summary** — objective value, selected risk measure value, feasibility.
- **Weights** — optimal weights (given) + hand-computed risk contribution %
  per fund (`wᵢ·(Σw)ᵢ / w'Σw`, Σ built via `COVARIANCE.S`/array formula over
  the raw monthly returns).
- **Frontier** — for each returned frontier point, recompute (volatility,
  expected return, Sharpe) *given that point's own weights* — verifying
  self-consistency, not re-deriving the frontier's construction.
- **Performance** — CAGR, annualized volatility, Sharpe, Sortino, max
  drawdown from the portfolio's own realized monthly return series
  (weights × fund returns), matching `docs/formula-reference.md`'s
  already-cited formulas exactly.
- **Rolling** — per-fold realized return/volatility/Sharpe, recomputed from
  each fold's stated train/test boundaries and the raw NAV.
- **Report** — cross-checks that the Report tab's numbers match the other
  tabs (internal-consistency check, not a new computation).

**Full-solve replication (one case):** a separate sheet solving the
unconstrained 2-asset Max Sharpe tangency portfolio by its closed-form
solution, `w* = Σ⁻¹(μ − r_f·1) / 1'Σ⁻¹(μ − r_f·1)` (then normalized to sum
to 1), computed independently from the same raw NAV, compared against what
the solver actually returned for the same request. This is the one place
the *solve itself* is checked, not just the reporting layer built on top of
a given set of weights.

**4.5:** `docs/manual-verification-2026-08-11.xlsx` (workbook) +
`docs/manual-verification-2026-08-11.md` (narrative: what was tested,
pass/fail per row, root cause for any mismatch). Any real mismatch (beyond
6-decimal floating-point noise) gets a failing test written first in
`backend/tests/` reproducing it, then the fix lands in `backend/app/engine/`
or `backend/app/optimizer/` — whichever owns the wrong formula — TDD-style.

## Error Handling

- If the fixed test case's request fails (e.g. the cache changed and the
  date range is no longer clean), the request is re-validated against
  `GET /api/funds/testable-range` before re-running — no silent substitution
  of a different range without noting why in the verification `.md`.
- A verification-table row that "could not verify" (e.g. a formula whose
  exact riskfolio-lib internals aren't inspectable without reading its
  source) is recorded as such, not silently marked as matching.
- Any Excel formula that would need to reference a value not independently
  derivable from `nav.csv` (i.e. would just be copying `result.json`) is
  flagged in the sheet rather than written as if it were an independent
  check — the whole point of 4.4 is that nothing is copied from the code
  under test.

## Testing

- The TDD fix loop (4.5) is this phase's own test coverage requirement: any
  discovered mismatch is not fixed without a failing `backend/tests/` case
  first reproducing it against the real fixed test case's numbers.
- No new automated test suite is added purely for "does the citation doc
  match the code" — that check is manual (by construction, since it's a
  literature-vs-implementation comparison, not a runtime behavior), captured
  in the verification table itself.
