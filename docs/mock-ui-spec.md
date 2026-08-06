# Mock UI Spec — Portfolio / Assumptions / Results (Phase 4 input)

Status: **spec for Phase 4 mock build**, no code yet.

**Revision history:** an earlier draft proposed a 4th "Universe" step, corrected below.
A later revision cited PortfolioVisualizer fields via web-search summaries only
(Medium confidence, since static fetch of portfoliovisualizer.com returns HTTP 403);
this revision replaces every one of those with fields confirmed by loading the live
tool pages in an actual browser session (High confidence) — static bot fetch is
blocked, but an interactive browser session is not. Several fields turned out to be
named or to work differently than the web-search summaries suggested (flagged inline
below), most importantly: target volatility does NOT shift to cash (it constrains the
risky mix), and rolling optimization uses a fixed lookback-window + frequency, not an
expanding/rolling train-test fold split.

An earlier draft of this doc proposed a 4th "Universe" step. That
was wrong — checked the existing `frontend/src/components/PortfolioStep.tsx` directly
and it *already* has AMC/policy_desc filters, search, and NAV-coverage display; it's
the shortlist UI, not a weight-entry form that needs replacing wholesale. Reverted to
the parent app's existing **3-step shell** (`Portfolio → Assumptions → Results`, see
`frontend/src/components/Stepper.tsx`), matching both the parent's own convention and
PortfolioVisualizer's pattern (its `optimize-portfolio` page is a single scrollable
form covering assets + objective + constraints together, not a multi-page wizard).

Every field below is sourced against `docs/optimization-assumptions.md`, a directly-read
file (riskfolio-lib docs, the fund universe CSV columns, `AssetManagementToolkit`
source), the primary Black-Litterman confidence-method paper (Idzorek 2004, fetched and
saved at `docs/assets/idzorek-2004-black-litterman-guide.pdf`), or — as of this
revision — **direct browser fetches of the live PortfolioVisualizer tool pages**
(`optimize-portfolio`, `efficient-frontier`, `rolling-optimization`,
`black-litterman-model`), all High confidence. Static `WebFetch` on these URLs still
returns HTTP 403; loading them in an actual browser session works and rendered the real
form fields and (for `optimize-portfolio`/`efficient-frontier`, which carried the
user-supplied query params) real computed results. Every "Medium confidence,
web-search-derived" field from the prior revision is now replaced with the verified
real field name/options below.

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

**Verified directly against the live `optimize-portfolio` and `efficient-frontier`
tools this session** (browser-fetched, real form rendered — not summarized):

| Field | Options | Source |
|---|---|---|
| Optimization goal | PV's real list, confirmed by direct fetch: **Mean Variance** – Maximize Sharpe / Minimize Volatility subject to... / Maximize Return subject to... / Minimize Variance; **CVaR** – Minimize CVaR / Minimize CVaR subject to... / Maximize Return subject to...; **Risk Parity**; **Tracking Error** – Minimize / Maximize Information Ratio / Maximize Excess Return subject to...; **Maximize Kelly Criterion**; **Minimize Maximum Drawdown subject to...**; **Maximize Omega Ratio subject to...**; **Maximize Sortino Ratio subject to...** | live-fetched `optimize-portfolio` page, this session (High confidence) |
| **First-tier subset for this project's mock** (not all 15 — matches riskfolio-lib's model coverage and this project's decided scope) | Max Sharpe · Min Volatility · Max Return subject to target volatility · Minimize Variance (=GMV) · Risk Parity · Black-Litterman · Hierarchical Risk Parity (HRP, riskfolio-lib native, not in PV's list) | scoped down from PV's full 15-goal list to what riskfolio-lib supports and this project's audience needs (README §2: retail/student, not a hedge-fund-grade tool) — CVaR/tracking-error/Kelly/Sortino/Omega goals noted as later-tier additions |
| Risk measure (for mean-risk objectives) | Std deviation (default) · CVaR · CDaR · Semi-variance | riskfolio-lib supports 26+; shortlist to 4 for legibility |
| **Targeted Annual Volatility** | numeric %, optional | **Confirmed exact field name and behavior from the live fetch**: used with the "Maximize Return subject to..." goal — the optimizer finds max-return weights subject to a volatility ceiling (verified with the user's own query: 10% target on an 8-ETF universe returned a real 4-fund allocation: VTI 46.42% / TLT 19.43% / LQD 4.60% / GLD 29.55%, expected return 9.63%, Std Dev 9.99% — i.e. it does NOT shift to cash, it just constrains the risky-asset mix to hit the vol ceiling; the earlier "shifts to cash" description was wrong, corrected here) |
| **Robust Optimization** | Yes / No toggle | **New field, confirmed from the live `efficient-frontier` fetch** — PV's own description: "Monte Carlo method... resamples the optimization inputs in order to mitigate the impact of input estimation errors and improve diversification." **This is a direct, literal implementation of Michaud's resampling fix** cited in the research — exactly the "robustness indicator" gap flagged earlier, now with a confirmed real UI pattern (a toggle, not a chart overlay) to copy |
| Use Historical Returns | Yes / No | confirmed field from live fetch — No presumably opens forward-looking capital-market-assumption inputs; out of scope to spec further without deeper look, note as later-tier |
| **Expected-return estimation method** | Historical mean (default) · CAPM-implied · Black-Litterman posterior (enabled only if Objective = Black-Litterman) | Michaud's estimation-error critique — this field must exist explicitly (PV handles this via "Use Historical Returns" toggle + the separate BL tool, rather than a single dropdown — adopt PV's toggle pattern instead of a dropdown) |
| **Covariance estimation method** | Sample (default, warning badge below a fund-count/history threshold) · Shrinkage (blend toward constant-correlation target) · EWMA | `AssetManagementToolkit`'s `estimation/covariance.py` has all three; reuse permitted (owner confirmed). PV's own analog is the **Covariance Period** field (Full History / Last Five Years) on its BL tool — simpler than exposing an estimator choice; consider that simpler pattern for the first mock, with shrinkage/EWMA as an advanced toggle |

### 2b. Black-Litterman view panel (shown only if Objective = Black-Litterman)

**Structural note from the live fetch:** PV does not inline its BL tool into the main
optimize form — it's a **separate 3-step wizard** ("Step 1/3: Benchmark Portfolio" →
presumably views → results, confirmed by direct fetch this session; steps 2-3 not
explored further, out of scope). Step 1 fields, confirmed live: **Portfolio Type**
(Asset Classes/Tickers), **Covariance Period** (Full History / Last Five Years),
**Expected Return** (%, for the benchmark), **Portfolio Assets** (the market-weight
allocation table). This validates the "Market weights" field below as a real,
necessary first input — keep BL as an in-line panel within this project's single
Assumptions step (simpler than a 3-step sub-wizard) but keep PV's ordering: benchmark
weights first, then views, then confidence.

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

| Field | Options | Why / source |
|---|---|---|
| Per-fund weight bounds (min/max %) | numeric per fund | confirmed live on both `optimize-portfolio` ("Asset Constraints: Yes/No") and `efficient-frontier` (explicit Min./Max. Weight column per asset) |
| Long-only toggle | on/off | default on — matches typical retail-fund reality (no short access on Thai mutual funds) |
| **Group Constraints** | Yes / No | **exact field name confirmed live** on both `optimize-portfolio` and `efficient-frontier` — caps exposure per group (map to `policy_desc` groupings here) |
| **Excess Return Frontier** | Yes / No | new field, confirmed live on `efficient-frontier` only — plots the frontier in excess-of-risk-free-rate space; note as an advanced/later-tier toggle, not required for the first mock |
| Max number of holdings (cardinality) | numeric | riskfolio-lib native support; not present in PV's UI (PV doesn't expose cardinality) — this project adds it because the shortlist can still be 20-30 funds |
| **Rolling-window validation params** — corrected this revision | **Lookback Period**: 12 / 24 / 36 / 48 / 60 months (fixed dropdown, not free numeric) · **Optimization Frequency**: Monthly / Quarterly / Annually | **Corrected from the prior revision's guess.** Confirmed live on the `rolling-optimization` tool: PV does NOT use an expanding/rolling train-test fold split (that was an incorrect inference from `AssetManagementToolkit`'s simulation-calibration walk-forward code, which solves a different problem, flagged in the earlier code review). PV's actual pattern is simpler — re-optimize at a fixed **frequency** using a fixed-length trailing **lookback window**, repeated forward through the whole period. Adopt PV's real, simpler pattern instead |
| **Constrain Weights** | Yes / No | confirmed live on `rolling-optimization` — same as "Asset Constraints" above, just this tool's own name for it |
| Risk-free rate | numeric % | reuse the parent backtester's existing field as-is |
| **Compare against** | None · Equal Weighted · Max Sharpe Ratio Weights · Inverse Volatility Weighted · Risk Parity Weighted (rolling tool: None/Equal Weighted/Inverse Volatility only) | **exact field name "Compared Allocation" and its real option list confirmed live** on both `optimize-portfolio` and `rolling-optimization` — carry this exact option set into the mock rather than the earlier generic "equal-weight or current portfolio" guess |
| Benchmark | None · Specify Ticker · Import Benchmark · a few presets | confirmed live on both `optimize-portfolio` and `rolling-optimization` — separate from "Compared Allocation" (a benchmark is for relative-performance stats like tracking error/beta, not a second allocation shown side-by-side); this project's benchmark options should pull from the SEC fund/index universe instead of PV's US-ETF presets |

---

## Step 3 — Results

**Verified against the live `optimize-portfolio` and `efficient-frontier` results
pages this session** (real computed output rendered from the user's own query params
— e.g. the 8-ETF, 10%-target-volatility query returned a real 4-fund solution: VTI
46.42% / TLT 19.43% / LQD 4.60% / GLD 29.55%, CAGR 9.52%, Sharpe 0.79 vs. an
equal-weight comparison at CAGR 7.75%, Sharpe 0.54):

| Section | Content | Source / rationale |
|---|---|---|
| Efficient frontier chart | interactive frontier plot (Standard Deviation × Expected Return axes, confirmed live), selected/tangency portfolio marked | confirmed live on `efficient-frontier` |
| **Efficient Frontier Transition Map** | *(new field, confirmed live)* stacked-area chart showing how each asset's weight changes across frontier points (risk level on x-axis) | confirmed live on `efficient-frontier` — genuinely useful, not previously in this spec; shows *how* the optimal mix shifts as risk tolerance changes, not just the endpoint |
| **Efficient Frontier Points table** | *(new field, confirmed live)* full numeric table of every frontier point: per-asset weight, expected return, std dev, Sharpe ratio, one row per point (PV showed 80+ rows) | confirmed live — more granular than just plotting the curve; useful for a "download the frontier" export |
| **Per-asset summary table** | *(new field, confirmed live)* expected return / std dev / Sharpe / min-max weight, one row per selected fund, shown alongside the frontier | confirmed live on `efficient-frontier` |
| **Asset Correlations matrix** | *(new field, confirmed live)* pairwise correlation table across the shortlist | confirmed live on `efficient-frontier` — directly useful for a "why did the optimizer avoid these two funds" explanation |
| Optimal weights table | per-fund weight, **columns for the "Compared Allocation" from Step 2c** (confirmed real UI pattern: PV renders the compared allocation as a full second table + pie chart side by side with the optimal one, not just an extra column) | confirmed live on `optimize-portfolio` |
| Performance Summary table | *(new field, confirmed live)* Start/End Balance, CAGR, Expected Return, Std Dev, Best/Worst Year, Max Drawdown, Sharpe (ex-ante and ex-post), Sortino — one column per allocation (optimal vs. compared) | confirmed live on `optimize-portfolio` — this is the richest single section PV ships and was missing entirely from earlier drafts of this spec |
| Risk contribution breakdown | per-fund % of total portfolio risk | riskfolio-lib native output (not shown on PV's free tier in this fetch, kept because it's core to Risk Parity/HRP objectives this project supports) |
| **Robustness indicator → now "Robust Optimization" toggle, carried from Step 2a** | when enabled, the frontier/weights shown are Monte-Carlo-resampled per PV's own description ("resamples the optimization inputs... mitigate input estimation error") | this is the confirmed real implementation of the earlier "robustness indicator" gap — a toggle upstream in Assumptions (Step 2a) that changes how the Results are computed, not a Results-only visual add-on |
| Rolling out-of-sample performance chart | realized return/vol/Sharpe of the optimized weights, re-evaluated at each rebalance per the Step-2c Lookback Period + Optimization Frequency | mirrors PV's rolling-optimization tool, using its real (corrected) params |
| Feasibility / constraint-violation report | explicit error states: solver non-convergence vs. mutually-infeasible constraints vs. insufficient data for the selected window, each actionable | not present in PV (no UI precedent) — reuse the parent's `ErrorCode` pattern (`backend/app/domain/enums.py`), add optimizer-specific codes; PV's own note is instructive though: it displays "time period was constrained by the available data for [ticker]" as a plain banner when history is short — copy that pattern directly |
| Report tab | plain-language audit trail: objective, risk measure, return/covariance method, BL inputs if used, constraints, rolling-window setup | mirrors the parent's existing Report tab; same "every number traces to a stated formula" philosophy as the source README |

---

## Explicitly out of scope for this spec

- Actual computation/wiring (Phase 5).
- The exact shortlist cap in Step 1 (flagged as open).
- PV's BL tool steps 2-3 (views input, results) were not explored live this session —
  only Step 1/3 (Benchmark Portfolio) was fetched; confirm the views/confidence UI
  pattern against the live tool before finalizing the BL sub-panel's exact layout.
- "Use Historical Returns: No" (forward-looking capital-market assumptions) — field
  confirmed to exist live, behavior not explored; later-tier addition.
- PV's other 2-of-3 Optimization Goal categories (CVaR-subject-to, Tracking
  Error/Information-Ratio, Kelly, Max Drawdown, Omega, Sortino) — confirmed to exist
  live but out of scope for the first-tier objective list above.
- Data-quality handling for gaps *within* a shortlisted fund's history during the
  optimization window itself — reuse `backend/app/data/quality.py`'s server-side logic
  rather than re-deriving it, per the parent project's own "known landmines" note.
