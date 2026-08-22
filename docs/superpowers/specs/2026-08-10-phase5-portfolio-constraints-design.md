# Phase 5 sub-project 4: Portfolio Constraint Completion — Design

Status: **implemented (updated 2026-08-17).** This is the historical design record for the fourth of an expanded set of ordered
Phase 5 sub-projects. Sub-projects 1 (backend optimizer core), 2 (rolling
out-of-sample evaluator), and 3 (comparison features) are complete and merged
to `main`.

## Why this sub-project exists

Continuing the audit of `OptimizeRequest`/`OptimizeConstraints` fields the
real backend never reads (started in sub-project 3's brainstorm): two more
UI-selectable fields do nothing server-side today.
`groupConstraintsEnabled`/`assetGroups` (a group weight-cap selector, e.g.
"Equities ≤ 40%") and `maxHoldings` (a cardinality cap, "at most N funds")
are both fully rendered in `OptimizeAssumptionsStep.tsx` and both silently
ignored by `backend/app/optimizer/*.py`.

## Research finding that shapes this design

`maxHoldings` cannot be enforced exactly with this project's solver
constraint (CLARABEL/free solvers only, no MOSEK/GUROBI). Verified directly
against the installed riskfolio-lib 7.3.0 / CVXPY 1.9.2: `rp.Portfolio`'s
`card` parameter (its own cardinality-constraint mechanism) constructs a
boolean CVXPY variable (`cp.Variable(..., boolean=True)`,
`Portfolio.py:2878` and two duplicate sites for other optimization methods),
making the resulting problem a genuine Mixed-Integer Program the moment
`card` is set. Of this project's installed solvers, only `HIGHS`/`SCIPY`
are MI-capable at all (`cvxpy.reductions.solvers.defines.INSTALLED_MI_SOLVERS`),
and a direct test (`HIGHS` on a toy mixed boolean + SOCP-norm problem)
confirmed `SolverError: The solver HIGHS cannot solve this problem` — HiGHS
is MILP-only, and every risk measure this project exposes (std_dev,
semi-variance, CVaR, CDaR) is SOCP-based, not pure-LP. `maxHoldings` is
therefore implemented as a **greedy post-solve heuristic**, not an exact
solver-level constraint — per decision, not silently degraded without
disclosure (see Reporting below).

## Scope

**In scope:** `groupConstraintsEnabled`/`assetGroups` as a real,
solver-level linear constraint; `maxHoldings` as a greedy heuristic; a new
`OptimizeResult.constraintNote: string | null` field.

**Out of scope:** any frontend change; `returnMethod`/rolling-lookback
(sub-project 5); robust optimization (sub-project 6); any change to
`compareAgainst`/`benchmarkProjId` (sub-project 3, already shipped).

## Architecture

Two independent pieces, both landing in `backend/app/optimizer/solvers.py`
(group constraints, since they're solver-input construction, alongside the
existing `_asset_bounds`/`_build_portfolio` per-fund-bound logic) and a new
`backend/app/optimizer/holdings.py` (the max-holdings heuristic, since it's
an iterative re-solve loop, a distinct concern from single-shot constraint
construction — matches this project's established "one file per concern"
shape).

## Group Constraints

A linear inequality, added to the SAME `ainequality`/`binequality` matrix
`_build_portfolio` already constructs for per-fund bounds (sub-project 1) —
no new constraint mechanism, just more rows. For each group letter (A-F)
present in `request.asset_groups` when `request.constraints.group_constraints_enabled`
is true: one row enforcing `Σ(w_i for i where fund_groups[i] == group) <= max_weight_pct/100`,
one row for `>= min_weight_pct/100`. Funds not assigned to any group (absent
from `fund_groups`) are unconstrained by this mechanism, matching the UI's
own framing (`fundGroups` is a per-fund opt-in mapping, not a mandatory
partition). When `group_constraints_enabled` is false, zero rows are added —
identical to today's behavior.

## Max Holdings — Greedy Heuristic

`holdings.enforce_max_holdings(request, mu, sigma, returns) -> tuple[dict[str, float], str | None]`:

1. Solve once via the existing `solvers.solve_for_goal` (unchanged,
   including any group-constraint rows from above).
2. If the number of funds with weight > 0.5% is ≤ `request.constraints.max_holdings`,
   return the weights unchanged, note `None` — the common case where the cap
   was never binding costs nothing extra.
3. Otherwise, iteratively: find the smallest nonzero-weight fund, force its
   `max_weight_pct` to 0 for the next solve (via a per-request
   `fund_bounds` override, the same mechanism `FundBound` already provides —
   no new bound-pinning mechanism needed), re-solve. Repeat until the
   resulting fund count is ≤ `max_holdings` or a solve fails.
4. Capped at `original_fund_count - max_holdings` iterations by
   construction (each iteration removes exactly one fund) — this cannot
   loop indefinitely.
5. If a solve fails mid-loop (e.g. group constraints force more funds than
   `max_holdings` allows to hold nonzero weight — a genuine infeasibility,
   not a bug), return the LAST successfully-solved weights (which may still
   exceed `max_holdings`) with a `constraintNote` explaining the cap could
   not be fully honored — never fail the whole request over this (same
   non-blocking-secondary-feature principle established in sub-projects 2
   and 3).
6. On success after N>0 trimming iterations, `constraintNote` states which
   funds were dropped and why (e.g. "Trimmed 2 funds to satisfy the 3-holding
   cap: lowest-weight funds removed and the remainder re-optimized.").

`service.py` calls `holdings.enforce_max_holdings` once, after the main
solve, and uses its returned weights as the FINAL `optimalWeights` for
everything downstream (frontier markers, diagnostics, performance summary,
comparison) — the heuristic's output IS the request's answer, not a
side-channel. `constraintNote` is a new, separate `OptimizeResult` field
(never reusing `robustNote`/`compareNote`, per this project's now-established
one-meaning-per-field rule).

## Error Handling

- Group constraints: no new error path — an infeasible group bound (e.g.
  min sums exceeding 100%) surfaces as the EXISTING `INFEASIBLE_CONSTRAINTS`
  the main solve already raises when its own constraints can't be satisfied,
  no special-casing needed.
- Max holdings: never a hard error. Best-effort trim, `constraintNote`
  explains any shortfall, main solve result is always returned.

## Testing

- Unit tests for the group-constraint row construction (verify the
  `ainequality`/`binequality` matrix gets the right rows for a 2-group,
  4-fund synthetic case) and an integration test against the real NAV cache
  confirming a tight group cap actually binds the solved weights.
- Unit tests for `enforce_max_holdings`'s trimming logic against a synthetic
  case with a known expected trim sequence, plus an integration test against
  the real cache confirming a `maxHoldings=1` request on a 2-fund universe
  converges to a single holding with a real `constraintNote`.
- Extend the 112-case smoke matrix (7 goals × 4 risk measures × 4
  `compareAgainst` values) with a `maxHoldings`-constrained case verifying
  the returned `optimalWeights` never exceeds the cap for any combination —
  the "would this smoke test have caught the bug" bar every prior
  sub-project's final review has applied.
