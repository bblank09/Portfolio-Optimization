# Mock UI Spec — Assumptions & Results (Phase 4 input)

Status: **spec for Phase 4 mock build**, no code yet. Field-by-field expansion of the
two Phase-3 headline bullets, closing the gaps flagged in review (missing
expected-return method, covariance method, BL view input, rolling-window params,
robustness indicator, benchmark comparison, feasibility reporting, data-quality
handling). Every field below is justified against `docs/optimization-assumptions.md`
or a directly-read source (riskfolio-lib docs, the fund universe CSV columns, or the
`AssetManagementToolkit` code read this session).

The parent backtester's 3-step flow (`Portfolio → Assumptions → Results`, see
`frontend/src/components/Stepper.tsx`) is reused as the shell. **A new 4th step is
required, inserted before Assumptions:** the universe is ~2,000 funds
(`data/sec/mvp_fund_universe.csv`), and optimizing over all of them at once is not
standard practice — a shortlist step must exist before "Assumptions" can mean anything
objective-wise. Renamed flow: **Universe → Objective → Constraints → Results.**
("Objective" replaces "Portfolio" as step 1 content; "Constraints" replaces
"Assumptions.")

---

## Step 1 — Universe (new step, doesn't exist in the parent app)

Fund shortlist/pre-selection, using columns that already exist in
`data/sec/mvp_fund_universe.csv` (verified by direct read this session):

| Field | Source column | Purpose |
|---|---|---|
| Search / filter by name | `display_name`, `search_term` | find funds, same UX as parent's fund picker |
| Filter by AMC (asset management company) | `amc_name_th` / `amc_name_en` | narrow by manager |
| Filter by fund policy/category | `policy_desc` | e.g. equity / mixed / fixed income — needed because mixing wildly different asset classes into one MVO run without a category lens produces unstable results |
| Minimum history length | `nav_span_months` | optimizer needs enough observations per asset; expose as a slider (e.g. "require ≥ 36 months") |
| Data completeness threshold | `nav_completeness`, `nav_gap_count` | exclude funds with unreliable NAV history — same "gap is a hard error" philosophy as the parent engine (`INSUFFICIENT_NAV_HISTORY`), reused here at shortlist time instead of at run time |
| Max funds selectable | UI-enforced cap, e.g. 20-30 | keeps the optimization problem well-posed (N assets << number of return observations); exact cap is a Phase 5 design call, flagged as an open question below |
| Selected shortlist (running list) | user picks | feeds Step 2/3 as the asset universe |

**Open question (flag, not yet decided):** what's the actual max-N cap and does the
backend enforce it or just the UI? Resolve in Phase 5 backend design, not blocking for
the mock.

---

## Step 2 — Objective

| Field | Options | Why (source) |
|---|---|---|
| Optimization objective | Max Sharpe ratio · Min volatility · Risk parity (ERC) · Hierarchical Risk Parity (HRP) · Black-Litterman | riskfolio-lib's supported model list (verified via docs this session) |
| Risk measure (for mean-risk objectives) | Std deviation (default) · CVaR · CDaR · Semi-variance | riskfolio-lib supports 26+ measures; exposing all 26 is not usable UX — shortlist the 4 most legible to a retail/student user, matching the "risk-adjusted-return" framing in the source project's own audience (README §2: "retail investors and quant-finance students") |
| **Expected-return estimation method** *(new — was entirely missing)* | Historical mean (default) · CAPM-implied · Black-Litterman posterior (only enabled if Objective = Black-Litterman) | Michaud's critique (cited in research) is specifically about garbage-in-garbage-out on expected returns — the field must exist or every non-BL objective silently uses an unstated method |
| **Covariance estimation method** *(new — was entirely missing)* | Sample (default, with a warning badge below a fund-count threshold) · Shrinkage (Ledoit-Wolf-style, blend toward constant-correlation target) · EWMA | Directly maps to the decision doc's stance: default away from naive sample covariance where the universe is thin; `AssetManagementToolkit`'s `estimation/covariance.py` (read this session) has exactly these three, permitted for reuse now that license permission was confirmed |

### Black-Litterman view input (new sub-panel, only shown if Objective = Black-Litterman)

Directly maps to the mechanics read from `AssetManagementToolkit`'s
`black_litterman.py` and verified against Wikipedia this session:

| Field | Maps to | Notes |
|---|---|---|
| Market weights | `market_weights` (prior) | default: proportional to AUM/NAV size if available, else equal-weight within the shortlist — needs a data-availability check in Phase 5 |
| Risk aversion (δ) | `risk_aversion` | numeric input, default 2.5 (the library's own default) |
| Tau (τ) | `tau` | numeric input, default 0.05 — expose with a tooltip explaining it scales prior uncertainty, since the exact formula wasn't fully sourced (flagged gap: pull He & Litterman 1999 before finalizing the tooltip copy) |
| View builder | pick matrix `P` + view vector `Q` | UI pattern: "Fund A will return [X]% more than Fund B" (relative view) or "Fund A will return [X]%" (absolute view) — one row per view, add/remove rows |
| View confidence | `Ω` (Omega) | per-view slider (low/medium/high confidence) mapped to the proportional He-Litterman uncertainty formula by default; advanced users can override with a raw uncertainty value |

---

## Step 3 — Constraints

| Field | Why |
|---|---|
| Per-fund weight bounds (min/max %) | standard MVO constraint; riskfolio-lib supports directly |
| Long-only toggle | default on — matches `AssetManagementToolkit`'s "long-only" scope, matches typical retail use case (no short-selling access on Thai mutual funds) |
| Max number of holdings (cardinality) | riskfolio-lib supports cardinality constraints; useful since shortlist can still be large |
| Sector/category exposure caps | optional, using `policy_desc` groupings from Step 1 |
| **Rolling-window validation params** *(new — was entirely missing)* | train window length, test window length, rolling vs. expanding — directly required by the decision doc's "pair every optimal-weights result with an out-of-sample rolling backtest" requirement; UI pattern borrowed from `AssetManagementToolkit`'s `walk_forward.py` fold-splitting logic (expanding/rolling, non-overlapping test folds) |
| Risk-free rate | needed for Sharpe-ratio objective and reporting | reuse the parent backtester's existing `riskFreeRate` field/UX as-is |

---

## Step 4 — Results

| Section | Content | Why (closes a previously-flagged gap) |
|---|---|---|
| Efficient frontier chart | interactive frontier plot, selected portfolio marked | standard output, matches PortfolioVisualizer's efficient-frontier page |
| Optimal weights table | per-fund weight, with a **comparison column against equal-weight and (if provided) the user's current portfolio** | *new* — closes "no benchmark/current-portfolio comparison" gap; professional tools always show optimal vs. status quo |
| Risk contribution breakdown | per-fund % of total portfolio risk | riskfolio-lib native output |
| **Robustness indicator** *(new — was entirely missing)* | resampled/perturbed frontier band (shaded region) instead of a single line, OR a simpler "estimation sensitivity" badge (e.g. "high sensitivity to input assumptions" flag when the universe is small/short-history) | directly answers Michaud's "error maximizer" critique from the research — an "optimal" weighting shown as a single confident line, with no caveat, is the single biggest professional-standard gap identified in the prior review |
| Rolling out-of-sample performance chart | realized return/vol/Sharpe of the optimized weights, evaluated fold-by-fold per the Step-3 rolling params | the decision doc's core requirement — mirrors PortfolioVisualizer's rolling-optimization tool |
| **Feasibility / constraint-violation report** *(new — was entirely missing)* | explicit error state distinguishing "solver did not converge" vs. "constraints are mutually infeasible" vs. "insufficient data for the selected window," each with an actionable message | professional tools never fail silently or with a generic error; matches the parent project's own `ErrorCode` pattern (`backend/app/domain/enums.py`) — reuse that enum pattern, add optimizer-specific codes |
| Report tab | methodology recap: objective, risk measure, return/covariance estimation method, constraints, rolling-window setup, as a plain-language audit trail | mirrors the parent's existing "Report" tab (formula reference + assumptions), same "every number traces back to a stated formula" philosophy from the source README |

---

## Explicitly out of scope for this spec

- Actual computation/wiring (Phase 5).
- The exact max-N shortlist cap (flagged above as an open Phase-5 question).
- BL tau/Omega exact formula sourcing beyond what Wikipedia + `AssetManagementToolkit`'s
  code already confirm — pull He & Litterman (1999) before writing the real tooltip
  copy or backend validation ranges.
- Data-quality handling for gaps *within* a shortlisted fund's history during the
  optimization window itself (only handled at shortlist-filter time above) — needs the
  same server-side "is this range usable" logic the parent project already has in
  `backend/app/data/quality.py`; reuse that module rather than re-deriving it.
