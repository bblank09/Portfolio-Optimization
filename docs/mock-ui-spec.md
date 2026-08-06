# Mock UI Spec — Portfolio / Assumptions / Results (Phase 4 input)

Status: **spec for Phase 4 mock build**, no code yet.

**Revision note:** an earlier draft of this doc proposed a 4th "Universe" step. That
was wrong — checked the existing `frontend/src/components/PortfolioStep.tsx` directly
and it *already* has AMC/policy_desc filters, search, and NAV-coverage display; it's
the shortlist UI, not a weight-entry form that needs replacing wholesale. Reverted to
the parent app's existing **3-step shell** (`Portfolio → Assumptions → Results`, see
`frontend/src/components/Stepper.tsx`), matching both the parent's own convention and
PortfolioVisualizer's pattern (its `optimize-portfolio` page is a single scrollable
form covering assets + objective + constraints together, not a multi-page wizard).

Every field below is sourced against `docs/optimization-assumptions.md`, a directly-read
file (riskfolio-lib docs, the fund universe CSV columns, `AssetManagementToolkit`
source), or — for the fields in this revision — the primary Black-Litterman
confidence-method paper (Idzorek 2004, fetched and saved at
`docs/assets/idzorek-2004-black-litterman-guide.pdf`) plus web-search-derived summaries
of PortfolioVisualizer's `optimize-portfolio`, `efficient-frontier`, and
`rolling-optimization` tools (direct fetch of portfoliovisualizer.com remains
403-blocked to automation; summaries below are Medium confidence where noted).

---

## Step 1 — Portfolio (reuse existing component, minimal change)

Keep `PortfolioStep.tsx`'s search/AMC-filter/policy-filter/NAV-coverage display as-is.
**Only change:** drop the per-fund "weight" input (the optimizer computes weights, the
user doesn't set them) and add:

| Field | Source column | Purpose |
|---|---|---|
| Minimum history length filter | `nav_span_months` | optimizer needs enough observations per asset; expose as a slider (e.g. "require ≥ 36 months") |
| Data completeness filter | `nav_completeness`, `nav_gap_count` | exclude funds with unreliable NAV history — same "gap is a hard error" philosophy as the parent engine's `INSUFFICIENT_NAV_HISTORY`, applied here at selection time |
| Selection cap | soft UI cap, e.g. 20-30 funds, with an override | keeps the optimization well-posed (N assets << observations) on a ~2,000-fund universe; **open question, not yet decided:** exact cap and whether the backend also enforces it — resolve in Phase 5 |

---

## Step 2 — Assumptions (merges Objective + Constraints into one form, PV-style)

PortfolioVisualizer's `optimize-portfolio` page (per its query params and tool
summaries found this session — `mode`, `goal`, `timePeriod`, `targetAnnualVolatility`,
`constrained`, `groupConstraints`, `comparedAllocation`) puts objective selection,
target-risk input, and constraint toggles on **one page**, not separate steps. This
project's Assumptions step follows that shape:

### 2a. Objective

| Field | Options | Source |
|---|---|---|
| Optimization objective (`goal`-equivalent) | Max Sharpe ratio · Min volatility · Risk parity (ERC) · Hierarchical Risk Parity (HRP) · Black-Litterman | riskfolio-lib's model list (docs, fetched this session); PortfolioVisualizer's own goal list additionally includes CVaR/tracking-error/Kelly/Sortino/Omega objectives (per web-search summary, Medium confidence) — out of scope for the first mock, note as a later-tier addition |
| Risk measure (for mean-risk objectives) | Std deviation (default) · CVaR · CDaR · Semi-variance | riskfolio-lib supports 26+; shortlist to 4 for a retail/student audience (README §2) |
| **Target annual volatility** *(new this revision — direct PV pattern)* | numeric %, optional | PortfolioVisualizer's `targetAnnualVolatility` param: if the optimized portfolio's predicted volatility exceeds this target, the allocation shifts toward a risk-free/cash sleeve to bring it in line (per web-search summary, Medium confidence — exact shift mechanism not independently verified against PV's source) |
| **Expected-return estimation method** | Historical mean (default) · CAPM-implied · Black-Litterman posterior (enabled only if Objective = Black-Litterman) | Michaud's estimation-error critique — this field must exist explicitly |
| **Covariance estimation method** | Sample (default, warning badge below a fund-count/history threshold) · Shrinkage (blend toward constant-correlation target) · EWMA | `AssetManagementToolkit`'s `estimation/covariance.py` has all three; reuse permitted (owner confirmed) |

### 2b. Black-Litterman view panel (shown only if Objective = Black-Litterman)

Sourced from the Idzorek (2004) primary paper (fetched, saved locally this session)
plus `AssetManagementToolkit`'s `black_litterman.py`:

| Field | Maps to | Notes |
|---|---|---|
| Market weights | `market_weights` / `w_mkt` in Π = λΣw_mkt | default: proportional to AUM/NAV if available, else equal-weight within the shortlist |
| Risk aversion (δ) | `risk_aversion` | default 2.5 |
| Tau (τ) | `tau` | default **0.05**. Idzorek's paper (p.14, read this session) surveys practitioner values: Lee typically uses 0.01–0.05; Satchell & Scowcroft (2000) use 1; Blamont & Firoozye (2003) use 1/(number of observations). Expose as an advanced override, default 0.05 (matches riskfolio-lib's own default) |
| View builder | pick matrix `P`, view vector `Q` | "Fund A will return [X]% more than Fund B" (relative, row sums to 0) or "Fund A will return [X]%" (absolute, single 1). For multi-asset relative views, Idzorek recommends **market-cap(≈AUM)-weighted** row entries over naive equal-weighting — equal-weighting causes disproportionate tracking error on smaller funds (paper's own worked example, p.12) |
| **View confidence** | Ω, via **Idzorek's confidence method** | The paper's actual contribution: an intuitive **0–100% confidence slider per view**, back-solved into the Ω diagonal — this is the field to build, not a raw-variance input. Matches PyPortfolioOpt's `omega="idzorek"` mode (confirmed this session). Default Ω without slider interaction: Ω = τ·PΣPᵀ (matches `AssetManagementToolkit` and riskfolio-lib) |

### 2c. Constraints

| Field | Why |
|---|---|
| Per-fund weight bounds (min/max %) | standard MVO constraint |
| Long-only toggle | default on, matches PV's `constrained`/typical retail-fund reality (no short access on Thai mutual funds) |
| Group/category constraints toggle | mirrors PV's `groupConstraints` param — caps exposure per `policy_desc` group |
| Max number of holdings (cardinality) | riskfolio-lib native support; useful since the shortlist can still be 20-30 funds |
| **Rolling-window validation params** | train window length, test window length, rolling vs. expanding | PortfolioVisualizer's `rolling-optimization` tool (per web-search summary, Medium confidence): re-optimizes at the start of each period using a lookback window, non-overlapping test periods — same expanding/rolling fold-splitting pattern read in `AssetManagementToolkit`'s `walk_forward.py` this session |
| Risk-free rate | reuse the parent backtester's existing field as-is |
| **Compare against** *(new this revision — direct PV pattern)* | equal-weight · current/existing portfolio (user-entered) · none | mirrors PV's `comparedAllocation` param — a second allocation shown alongside the optimized one for direct comparison, not deferred to Results-only |

---

## Step 3 — Results

| Section | Content | Source / rationale |
|---|---|---|
| Efficient frontier chart | interactive frontier plot, selected portfolio marked, **optional minimum-variance-frontier overlay toggle** | PortfolioVisualizer's `efficient-frontier` tool (`minimumVarianceFrontier=true` param, web-search summary): the minimum-variance frontier is the lower/left boundary showing the lowest-risk combination at each return level — plot as an optional second line, not merged into the main frontier |
| Optimal weights table | per-fund weight, **columns for equal-weight and the "compare against" allocation from Step 2c** | direct implementation of the PV `comparedAllocation` pattern carried through from Assumptions |
| Risk contribution breakdown | per-fund % of total portfolio risk | riskfolio-lib native output |
| **Robustness indicator** | resampled/perturbed frontier band (shaded region) or a simpler "estimation sensitivity" badge | answers Michaud's "error maximizer" critique directly — a single confident frontier line with no caveat was the top gap flagged in review |
| Rolling out-of-sample performance chart | realized return/vol/Sharpe of the optimized weights, evaluated fold-by-fold per the Step-2c rolling params | mirrors PV's rolling-optimization output directly |
| Feasibility / constraint-violation report | explicit error states: solver non-convergence vs. mutually-infeasible constraints vs. insufficient data for the selected window, each actionable | reuse the parent's `ErrorCode` pattern (`backend/app/domain/enums.py`), add optimizer-specific codes |
| Report tab | plain-language audit trail: objective, risk measure, return/covariance method, BL inputs if used, constraints, rolling-window setup | mirrors the parent's existing Report tab; same "every number traces to a stated formula" philosophy as the source README |

---

## Explicitly out of scope for this spec

- Actual computation/wiring (Phase 5).
- The exact shortlist cap in Step 1 (flagged as open).
- PortfolioVisualizer's target-volatility cash-shift mechanism and its full goal list
  (CVaR/tracking-error/Kelly/Sortino/Omega objectives) — summarized at Medium
  confidence via web search only, since portfoliovisualizer.com remains
  403-blocked to direct fetch; verify against the live tool manually before finalizing
  the exact UI copy/behavior for "target annual volatility" and any later-tier
  objectives.
- Data-quality handling for gaps *within* a shortlisted fund's history during the
  optimization window itself — reuse `backend/app/data/quality.py`'s server-side logic
  rather than re-deriving it, per the parent project's own "known landmines" note.
