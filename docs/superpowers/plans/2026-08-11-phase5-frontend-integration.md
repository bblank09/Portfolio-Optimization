# Phase 5 sub-project 6 (final): Frontend Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `frontend/src/lib/mockOptimize.ts`'s fabricated optimize
computation with real `POST /api/optimize` calls, closing every remaining
frontend/backend field-parity gap, and finishing Phase 5.

**Architecture:** Add a `runOptimize` client function mirroring the
existing `runBacktest` pattern in `api/client.ts`; fix three missing
`OptimizeResult` fields and one missing `OptimizeConstraints` field in
`types/optimize.ts`; extract the one legitimate non-mock helper
(`estimateEquilibriumReturns`) out of `mockOptimize.ts` into its own file;
delete `mockOptimize.ts`; switch `OptimizeWorkspace.tsx`'s two call sites to
the real endpoint; add a `rollingWindowMode` UI control.

**Tech Stack:** React + TypeScript (Vite), no new dependencies. Backend is
already complete (FastAPI `POST /api/optimize`, `backend/app/api/optimize.py`).

## Global Constraints

- No backend changes in this plan — every backend gap is already closed
  (sub-projects 1-5 are implemented in the current codebase; repository merge
  state is tracked separately).
- `npm run build` (`tsc -b && vite build`) is this frontend's only
  type-check — it must pass with zero errors after every task that touches
  a `.ts`/`.tsx` file.
- No frontend unit tests or e2e specs currently reference `mockOptimize`,
  `runMockOptimize`, or `estimateEquilibriumReturns` (confirmed via repo
  search) — no test-file updates are required by this plan; each task's
  manual verification step is the acceptance gate.
- Field names on the wire are camelCase (frontend `OptimizeRequest`/
  `OptimizeResult` types already match this); do not introduce snake_case
  anywhere in `frontend/src`.
- `estimateEquilibriumReturns` is preserved as-is (a live client-side BL
  preview, not part of the mock optimizer) — moved, not rewritten.

---

### Task 1: Field-parity fixes in `types/optimize.ts`

**Files:**
- Modify: `frontend/src/types/optimize.ts:55-74` (`OptimizeConstraints`),
  `frontend/src/types/optimize.ts:227-262` (`OptimizeResult`)

**Interfaces:**
- Consumes: nothing new.
- Produces: `OptimizeConstraints.rollingWindowMode: "expanding" | "trailing"`,
  `OptimizeResult.compareNote: string | null`,
  `OptimizeResult.constraintNote: string | null`,
  `OptimizeResult.robustOptimizationNote: string | null` — all four consumed
  by later tasks (Task 4's `initialRequest`, Task 6's new UI control, and
  any component that reads `OptimizeResult`).

- [ ] **Step 1: Add `rollingWindowMode` to `OptimizeConstraints`**

In `frontend/src/types/optimize.ts`, inside the `OptimizeConstraints`
interface (currently lines 55-74), add a new field. The interface currently
ends with:

```ts
  // Only meaningful when a benchmark is set (see OptimizeRequest.benchmarkProjId)
  // -- caps how far the optimized weights can drift from the benchmark's
  // own risk, distinct from targeting the benchmark's return. null = unconstrained.
  maxTrackingErrorPct: number | null;
}
```

Change it to:

```ts
  // Only meaningful when a benchmark is set (see OptimizeRequest.benchmarkProjId)
  // -- caps how far the optimized weights can drift from the benchmark's
  // own risk, distinct from targeting the benchmark's return. null = unconstrained.
  maxTrackingErrorPct: number | null;
  // "expanding" (default): each rolling-validation fold's training window
  // always starts at the earliest available observation and grows.
  // "trailing": each fold's training window is a fixed-length window of
  // lookbackPeriodMonths immediately preceding that fold's test period,
  // sliding forward each fold. Backend: rolling.build_fold_schedule.
  rollingWindowMode: "expanding" | "trailing";
}
```

- [ ] **Step 2: Add the three missing note fields to `OptimizeResult`, fix `robustNote`'s comment**

In the same file, the `OptimizeResult` interface currently reads (lines
227-230):

```ts
export interface OptimizeResult {
  feasibility: FeasibilityStatus;
  feasibilityMessage: string | null;
  robustNote: string | null; // set when request.robustOptimization is true
  optimalWeights: Record<string, number>; // proj_id -> weight pct
```

Change it to:

```ts
export interface OptimizeResult {
  feasibility: FeasibilityStatus;
  feasibilityMessage: string | null;
  // Rolling out-of-sample validation caveats (e.g. folds dropped for
  // insufficient training history) -- NOT related to robustOptimization
  // (see robustOptimizationNote below for that).
  robustNote: string | null;
  // Set when constraints.compareAgainst produced a comparison portfolio --
  // caveats about how that comparison was computed.
  compareNote: string | null;
  // Set when a portfolio constraint (e.g. maxHoldings) could only be
  // approximately honored -- explains what was trimmed and why.
  constraintNote: string | null;
  // Set when request.robustOptimization is true -- states how many Monte
  // Carlo resamples succeeded, or explains a fallback to the single-shot
  // solve when fewer than half succeeded.
  robustOptimizationNote: string | null;
  optimalWeights: Record<string, number>; // proj_id -> weight pct
```

- [ ] **Step 3: Type-check**

Run: `npm --prefix frontend run build`
Expected: Fails, listing every file that constructs an `OptimizeResult` or
`OptimizeConstraints` object literal without the new required fields (this
is expected — Task 2 through Task 4 supply them). Confirm the failures are
only "missing property" errors on `optimize.ts`-typed object literals, not
unrelated syntax errors.

- [ ] **Step 4: Commit**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
git add frontend/src/types/optimize.ts
git commit -m "feat(optimize-types): add compareNote/constraintNote/robustOptimizationNote/rollingWindowMode

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `runOptimize` client function

**Files:**
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Consumes: `requestJson<T>` (existing, `frontend/src/api/client.ts:27-39`),
  `OptimizeRequest`/`OptimizeResult` from `../types/optimize` (Task 1's
  updated `OptimizeResult`).
- Produces: `export async function runOptimize(payload: OptimizeRequest): Promise<OptimizeResult>` — consumed by Task 5.

- [ ] **Step 1: Add the import and function**

In `frontend/src/api/client.ts`, add to the top import block (currently
line 1 imports only from `../types/backtest`):

```ts
import type { BacktestRequest, BacktestResult, DataStatus, SecFund } from "../types/backtest";
import type { OptimizeRequest, OptimizeResult } from "../types/optimize";
```

Then append at the end of the file, after the existing `runBacktest`
function:

```ts

export async function runOptimize(payload: OptimizeRequest): Promise<OptimizeResult> {
  return requestJson<OptimizeResult>("/api/optimize", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
```

- [ ] **Step 2: Type-check**

Run: `npm --prefix frontend run build`
Expected: No new errors attributable to `client.ts` itself (the pre-existing
Task-1-driven errors in other files are unaffected by this step).

- [ ] **Step 3: Commit**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
git add frontend/src/api/client.ts
git commit -m "feat(optimize-client): add runOptimize POST /api/optimize wrapper

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Extract `estimateEquilibriumReturns` into its own module

**Files:**
- Create: `frontend/src/lib/blackLittermanPreview.ts`
- Modify: `frontend/src/lib/mockOptimize.ts` (remove the function; the file
  itself is deleted in Task 5, after Task 4 removes its last consumer)

**Interfaces:**
- Consumes: `OptimizeRequest` from `../types/optimize`.
- Produces: `export function estimateEquilibriumReturns(request: OptimizeRequest): Record<string, number>` — consumed by Task 4.

- [ ] **Step 1: Create the new file**

Create `frontend/src/lib/blackLittermanPreview.ts` with this exact content
(the function and its two private helpers, moved verbatim from
`frontend/src/lib/mockOptimize.ts`, unchanged):

```ts
// Live client-side preview of Black-Litterman's market-equilibrium implied
// returns (Pi) -- shown in the Assumptions step's BL card WHILE the user
// adjusts risk aversion/tau, before running the optimization. BL views are
// meaningless without first seeing what the model already implies ("I
// think fund X will beat what the market/equilibrium implies"), so the UI
// needs this preview ahead of a full run, not only inside the eventual
// Results tab. This is a deterministic client-side estimate for display
// only -- the real equilibrium-return computation used by the optimizer
// itself lives server-side in backend/app/optimizer/black_litterman.py.
import type { OptimizeRequest } from "../types/optimize";

// Small deterministic PRNG (mulberry32) seeded from a string -- avoids a
// dependency, and guarantees the same fund selection + assumptions always
// render the same preview numbers.
function seededRandom(seed: string): () => number {
  let h = 1779033703 ^ seed.length;
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  let a = h >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function requestSeed(request: OptimizeRequest): string {
  return [
    request.funds.map((f) => f.proj_id).sort().join(","),
    request.goal,
    request.riskMeasure,
    request.targetAnnualVolatilityPct ?? "",
    request.targetAnnualReturnPct ?? "",
    request.robustOptimization,
    request.covarianceMethod,
    request.benchmarkProjId ?? "",
    request.tailConfidence,
    request.dataFrequency
  ].join("|");
}

export function estimateEquilibriumReturns(request: OptimizeRequest): Record<string, number> {
  const rand = seededRandom(requestSeed(request));
  const result: Record<string, number> = {};
  for (const fund of request.funds) {
    const equityish = /ตราสารทุน|ผสม/.test(fund.policy_desc);
    const baseReturn = equityish ? 8 + rand() * 6 : 2 + rand() * 3;
    const expectedReturnPct = !request.useHistoricalReturns && request.expectedReturnOverrides[fund.proj_id] !== undefined
      ? request.expectedReturnOverrides[fund.proj_id]
      : baseReturn;
    result[fund.proj_id] = Number((expectedReturnPct * 0.8).toFixed(2));
  }
  return result;
}
```

- [ ] **Step 2: Remove the moved code from `mockOptimize.ts`**

In `frontend/src/lib/mockOptimize.ts`, delete the `seededRandom` function,
the `requestSeed` function, and the `estimateEquilibriumReturns` function
(the comment block immediately above `estimateEquilibriumReturns` — "Lets
the Assumptions step show Black-Litterman's equilibrium returns..." — is
deleted along with it, since it now lives verbatim in the new file). Leave
everything else in `mockOptimize.ts` untouched for now (`runMockOptimize`
and its remaining helpers are still referenced by `OptimizeWorkspace.tsx`
until Task 4).

- [ ] **Step 3: Restore private copies of `seededRandom`/`requestSeed` inside `mockOptimize.ts`**

Confirmed: `runMockOptimize` itself also calls `seededRandom(requestSeed(request))`
directly (separately from the deleted `estimateEquilibriumReturns`), so
Step 2 broke it. Re-add both functions as private (non-exported) helpers
near the top of `frontend/src/lib/mockOptimize.ts`, in the same place they
used to live, with identical bodies to the ones now in
`blackLittermanPreview.ts` (see Step 1's code block). Do not import them
from `blackLittermanPreview.ts` — that module and `mockOptimize.ts` are
both deleted in Task 5, so no cross-dependency should be introduced between
them for what is a few-task-lifetime duplication.

- [ ] **Step 4: Type-check**

Run: `npm --prefix frontend run build`
Expected: No errors referencing `mockOptimize.ts` or `blackLittermanPreview.ts`.

- [ ] **Step 5: Commit**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
git add frontend/src/lib/blackLittermanPreview.ts frontend/src/lib/mockOptimize.ts
git commit -m "refactor(optimize): extract estimateEquilibriumReturns out of mockOptimize

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Switch `OptimizeWorkspace.tsx` to the real endpoint

**Files:**
- Modify: `frontend/src/pages/OptimizeWorkspace.tsx`

**Interfaces:**
- Consumes: `runOptimize` from `../api/client` (Task 2), Task 1's updated
  `OptimizeConstraints`/`OptimizeResult` types.
- Produces: nothing new for later tasks — this is the integration point.

- [ ] **Step 1: Swap the import**

In `frontend/src/pages/OptimizeWorkspace.tsx`, change line 2 and line 8
from:

```ts
import { fetchFunds, fetchTestableRange } from "../api/client";
```
```ts
import { runMockOptimize } from "../lib/mockOptimize";
```

to:

```ts
import { fetchFunds, fetchTestableRange, runOptimize } from "../api/client";
```

and delete the `import { runMockOptimize } from "../lib/mockOptimize";`
line entirely (line 8).

- [ ] **Step 2: Add `rollingWindowMode` to `initialRequest`**

In the `initialRequest` object (currently lines 31-68), inside the nested
`constraints` object, the last field is currently:

```ts
    maxTurnoverPct: null,
    maxTrackingErrorPct: null
  }
};
```

Change it to:

```ts
    maxTurnoverPct: null,
    maxTrackingErrorPct: null,
    rollingWindowMode: "expanding"
  }
};
```

- [ ] **Step 3: Make `submit()` call the real endpoint**

The current `submit()` function (lines 289-305) reads:

```ts
  async function submit() {
    setLoading(true);
    setError("");
    // Phase 4 mock: no backend call yet. A short artificial delay plus the
    // existing RunOverlay staged UI keeps the loading-state UX identical to
    // what Phase 5's real POST /api/optimize will need.
    await new Promise((resolve) => window.setTimeout(resolve, 900));
    try {
      const mockResult = runMockOptimize(request);
      setResult(mockResult);
      advanceTo(2);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Optimization failed");
    } finally {
      setLoading(false);
    }
  }
```

Replace it with:

```ts
  async function submit() {
    setLoading(true);
    setError("");
    try {
      const optimizeResult = await runOptimize(request);
      setResult(optimizeResult);
      advanceTo(2);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Optimization failed");
    } finally {
      setLoading(false);
    }
  }
```

(The artificial 900ms delay is removed — real network latency, covered by
the existing `RunOverlay`, replaces it.)

- [ ] **Step 4: Make the share-link restore effect async and error-surfacing**

The current restore effect (lines 117-139) reads:

```ts
  // Restore a shared link (?state=<encoded request>) once funds are loaded
  // (needed to resolve fundProjIds back into full SecFund objects), then
  // replay the same deterministic mock and jump straight to Results.
  useEffect(() => {
    if (!funds.length) return;
    const url = new URL(window.location.href);
    const raw = url.searchParams.get("state");
    if (!raw) return;
    const shared = decodeShareState(raw);
    if (!shared) return;
    const { fundProjIds, ...rest } = shared;
    const restoredFunds = fundProjIds.map((id) => funds.find((f) => f.proj_id === id)).filter((f): f is SecFund => Boolean(f));
    const restored: OptimizeRequest = { ...(rest as OptimizeRequest), funds: restoredFunds };
    setRequest(restored);
    if (restoredFunds.length >= 2) {
      try {
        setResult(runMockOptimize(restored));
        setUnlockedStep(2);
        setCurrentStep(2);
      } catch {
        // Malformed/stale shared state -- fall back to leaving the user on
        // Step 1 with the restored selections instead of a broken Results page.
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [funds.length]);
```

Replace it with:

```ts
  // Restore a shared link (?state=<encoded request>) once funds are loaded
  // (needed to resolve fundProjIds back into full SecFund objects), then
  // replay the real optimization and jump straight to Results.
  useEffect(() => {
    if (!funds.length) return;
    const url = new URL(window.location.href);
    const raw = url.searchParams.get("state");
    if (!raw) return;
    const shared = decodeShareState(raw);
    if (!shared) return;
    const { fundProjIds, ...rest } = shared;
    const restoredFunds = fundProjIds.map((id) => funds.find((f) => f.proj_id === id)).filter((f): f is SecFund => Boolean(f));
    const restored: OptimizeRequest = { ...(rest as OptimizeRequest), funds: restoredFunds };
    setRequest(restored);
    if (restoredFunds.length >= 2) {
      let cancelled = false;
      setLoading(true);
      setError("");
      runOptimize(restored)
        .then((restoredResult) => {
          if (cancelled) return;
          setResult(restoredResult);
          setUnlockedStep(2);
          setCurrentStep(2);
        })
        .catch((caught: unknown) => {
          if (cancelled) return;
          // Malformed/stale shared state (e.g. a fund the cache no longer
          // covers) -- surface why, leave the user on Step 1 with the
          // restored selections instead of a silent, unexplained stall.
          setError(caught instanceof Error ? caught.message : "Could not restore the shared optimization.");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
      return () => {
        cancelled = true;
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [funds.length]);
```

- [ ] **Step 5: Remove the "Mock UI — Phase 4" header tag**

In the JSX (currently lines 334-339):

```tsx
      <header className="topbar">
        <div className="brand">
          <img alt="Portfolio Optimization" className="mark" src="/brand/topbar-mark.png" />
          <span>Portfolio Optimization</span>
          <span className="tag">Mock UI &mdash; Phase 4, no live optimizer yet</span>
        </div>
```

Change to:

```tsx
      <header className="topbar">
        <div className="brand">
          <img alt="Portfolio Optimization" className="mark" src="/brand/topbar-mark.png" />
          <span>Portfolio Optimization</span>
        </div>
```

- [ ] **Step 6: Update the two comments that still reference the mock**

Two comment blocks in this file describe now-obsolete Phase-4-mock
behavior and must be corrected so they don't mislead the next reader:

The comment above `SharedRequest` (currently lines 70-75):

```ts
// No backend persists a run yet (Phase 4 mock -- see CLAUDE.md), so there's
// no server-issued run_id to put in a shareable URL the way the sibling
// backtester's copyShareLink does. runMockOptimize is fully deterministic
// from the request alone, though, so a shareable link here encodes the
// request itself (funds reduced to proj_ids) -- reloading it reproduces the
// identical result client-side, no backend round-trip needed.
```

becomes:

```ts
// POST /api/optimize doesn't persist a run_id (unlike POST /api/backtests),
// so there's no server-issued id to put in a shareable URL the way the
// sibling backtester's copyShareLink does. Instead, a shareable link here
// encodes the request itself (funds reduced to proj_ids) -- reloading it
// re-submits the identical request to the real optimizer.
```

The comment inside `handleAssetsChange` (currently lines 199-206) that ends
with "mockOptimize's allocateWeights" — update the last sentence from:

```ts
  // itself isn't fed anywhere yet (Phase 5: it would become the reference/
  // starting allocation); the per-fund min/max bounds ARE used, in
  // mockOptimize's allocateWeights. See docs/mock-ui-spec.md Step 1.
```

to:

```ts
  // itself feeds the trade-list/turnover computation server-side; the
  // per-fund min/max bounds are used as solver constraints. See
  // docs/mock-ui-spec.md Step 1.
```

The comment inside the `fetchTestableRange` effect (around lines 163-172)
that says "This Phase 4 mock has no backend at all -- runMockOptimize never
validates timePeriod against fund coverage" — update to:

```ts
        // The sibling backtester has this same client-side "don't re-clamp
        // an already-set date when the bound shrinks" gap, but it's caught
        // server-side (POST /api/backtests rejects an out-of-range request
        // with INSUFFICIENT_NAV_HISTORY, and POST /api/optimize does the
        // same). Re-clamp here too, the one place both bounds are known at
        // the same time, so a fund swap to a much narrower window doesn't
        // silently leave the date inputs holding a stale value below their
        // own new `min` until the request round-trips to the server.
```

- [ ] **Step 7: Type-check**

Run: `npm --prefix frontend run build`
Expected: No errors referencing `OptimizeWorkspace.tsx`. Errors may remain
in `mockOptimize.ts` (its last consumer here is now gone) and
`OptimizeAssumptionsStep.tsx` (Task 6 still imports `estimateEquilibriumReturns`
from the old path) — those are resolved in Task 5 and Task 6.

- [ ] **Step 8: Commit**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
git add frontend/src/pages/OptimizeWorkspace.tsx
git commit -m "feat(optimize): call real POST /api/optimize instead of the mock

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Delete `mockOptimize.ts`

**Files:**
- Delete: `frontend/src/lib/mockOptimize.ts`

**Interfaces:**
- Consumes: confirmation from Task 4 (its only remaining consumer) that no
  import of `runMockOptimize` or anything else from `mockOptimize.ts`
  remains anywhere in `frontend/src`.
- Produces: nothing — this is a pure deletion.

- [ ] **Step 1: Confirm no remaining references**

Run: `grep -rn "mockOptimize" "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI/frontend/src"`
Expected: No output (zero matches). If any match remains, stop and resolve
it before deleting — do not delete a file something still imports.

- [ ] **Step 2: Delete the file**

```bash
git rm "frontend/src/lib/mockOptimize.ts"
```

- [ ] **Step 3: Type-check**

Run: `npm --prefix frontend run build`
Expected: No errors referencing `mockOptimize.ts` (it no longer exists).
Errors may remain in `OptimizeAssumptionsStep.tsx` until Task 6 fixes its
import.

- [ ] **Step 4: Commit**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
git commit -m "chore(optimize): delete mockOptimize.ts, fully replaced by the real backend

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: `rollingWindowMode` UI control + fix the `estimateEquilibriumReturns` import

**Files:**
- Modify: `frontend/src/components/OptimizeAssumptionsStep.tsx:3` (import),
  `frontend/src/components/OptimizeAssumptionsStep.tsx:601-633` (rolling-window
  validation section)

**Interfaces:**
- Consumes: `estimateEquilibriumReturns` from `../lib/blackLittermanPreview`
  (Task 3), `OptimizeConstraints.rollingWindowMode` (Task 1).
- Produces: nothing new for later tasks — this is the final UI piece.

- [ ] **Step 1: Fix the import**

In `frontend/src/components/OptimizeAssumptionsStep.tsx`, line 3 currently
reads:

```ts
import { estimateEquilibriumReturns } from "../lib/mockOptimize";
```

Change to:

```ts
import { estimateEquilibriumReturns } from "../lib/blackLittermanPreview";
```

- [ ] **Step 2: Add the `rollingWindowMode` select**

The rolling-window validation section (currently lines 601-633) reads:

```tsx
        <div className={advancedOpen ? "advanced-body open" : "advanced-body"}>
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="lookback">Lookback period</label>
              <select className="field" id="lookback" onChange={(event) => patchConstraints({ lookbackPeriodMonths: Number(event.target.value) as OptimizeRequest["constraints"]["lookbackPeriodMonths"] })} value={request.constraints.lookbackPeriodMonths}>
                <option value={12}>12 months</option>
                <option value={24}>24 months</option>
                <option value={36}>36 months</option>
                <option value={48}>48 months</option>
                <option value={60}>60 months</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="frequency">Optimization frequency</label>
              <select className="field" id="frequency" onChange={(event) => patchConstraints({ optimizationFrequency: event.target.value as OptimizeRequest["constraints"]["optimizationFrequency"] })} value={request.constraints.optimizationFrequency}>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
                <option value="annually">Annually</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="compareAgainst">Compared Allocation</label>
              <select className="field" id="compareAgainst" onChange={(event) => patchConstraints({ compareAgainst: event.target.value as CompareAgainst })} value={request.constraints.compareAgainst}>
                <option value="none">None</option>
                <option value="current">Your Current Portfolio</option>
                <option value="equal_weighted">Equal Weighted</option>
                <option value="max_sharpe">Max Sharpe Ratio Weights</option>
                <option value="inverse_volatility">Inverse Volatility Weighted</option>
                <option value="risk_parity">Risk Parity Weighted</option>
              </select>
            </div>
          </div>
        </div>
```

Change the `lookback` form-field to add a new `rollingWindowMode` field
immediately after it:

```tsx
        <div className={advancedOpen ? "advanced-body open" : "advanced-body"}>
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="lookback">Lookback period</label>
              <select className="field" id="lookback" onChange={(event) => patchConstraints({ lookbackPeriodMonths: Number(event.target.value) as OptimizeRequest["constraints"]["lookbackPeriodMonths"] })} value={request.constraints.lookbackPeriodMonths}>
                <option value={12}>12 months</option>
                <option value={24}>24 months</option>
                <option value={36}>36 months</option>
                <option value={48}>48 months</option>
                <option value={60}>60 months</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="rollingWindowMode">Rolling window mode</label>
              <select className="field" id="rollingWindowMode" onChange={(event) => patchConstraints({ rollingWindowMode: event.target.value as OptimizeRequest["constraints"]["rollingWindowMode"] })} value={request.constraints.rollingWindowMode}>
                <option value="expanding">Expanding (grows from the start date)</option>
                <option value="trailing">Trailing (fixed-length, slides forward)</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="frequency">Optimization frequency</label>
              <select className="field" id="frequency" onChange={(event) => patchConstraints({ optimizationFrequency: event.target.value as OptimizeRequest["constraints"]["optimizationFrequency"] })} value={request.constraints.optimizationFrequency}>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
                <option value="annually">Annually</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="compareAgainst">Compared Allocation</label>
              <select className="field" id="compareAgainst" onChange={(event) => patchConstraints({ compareAgainst: event.target.value as CompareAgainst })} value={request.constraints.compareAgainst}>
                <option value="none">None</option>
                <option value="current">Your Current Portfolio</option>
                <option value="equal_weighted">Equal Weighted</option>
                <option value="max_sharpe">Max Sharpe Ratio Weights</option>
                <option value="inverse_volatility">Inverse Volatility Weighted</option>
                <option value="risk_parity">Risk Parity Weighted</option>
              </select>
            </div>
          </div>
        </div>
```

- [ ] **Step 3: Type-check**

Run: `npm --prefix frontend run build`
Expected: PASS with zero errors — this is the last file with an outstanding
reference from Task 1's type additions.

- [ ] **Step 4: Manual verification**

Run: `npm --prefix frontend run dev` (in one terminal) and, in another,
start the backend: `uvicorn backend.app.main:app --reload --port 8000` (per
the frontend's Vite proxy default `VITE_API_PROXY_TARGET=http://127.0.0.1:8001` —
check `frontend/vite.config.ts` for the actual configured port and match
it, or set `VITE_API_PROXY_TARGET` to wherever the backend is actually
listening). Then in a browser:
1. Select at least 2 funds, go to Assumptions, expand "Rolling-window
   validation & comparison", confirm the new "Rolling window mode" select
   appears between "Lookback period" and "Optimization frequency" with both
   options selectable.
2. Set goal to Black-Litterman, confirm the equilibrium-returns preview
   table still renders (proves `blackLittermanPreview.ts`'s extraction
   didn't break the BL card).
3. Click "Run optimization" on a non-Black-Litterman, non-robust request;
   confirm a real result renders (not a fabricated one — cross-check one
   number, e.g. total weight sums to ~100%, against what the backend
   actually returns via the Network tab).
4. Set `robustOptimization` to true and run again; confirm the request
   takes noticeably longer (real Monte Carlo resampling, several seconds)
   and `robustOptimizationNote` renders somewhere in Results (check
   `OptimizeResults.tsx`'s existing rendering of note fields — if it
   doesn't yet render `robustOptimizationNote`/`compareNote`/`constraintNote`
   anywhere, that is a pre-existing gap in `OptimizeResults.tsx` outside
   this plan's file list; note it in the report but do not fix it in this
   task).
5. Copy a shareable link, open it in a fresh tab/incognito window, confirm
   it re-runs against the real backend and lands on Results (or shows a
   clear error if the funds are no longer servable) instead of stalling
   silently.

- [ ] **Step 5: Commit**

```bash
cd "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI"
git add frontend/src/components/OptimizeAssumptionsStep.tsx
git commit -m "feat(optimize): add rollingWindowMode UI control, fix BL preview import

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Whole-branch verification

**Files:** none (verification only).

**Interfaces:** none.

- [ ] **Step 1: Full frontend build**

Run: `npm --prefix frontend run build`
Expected: PASS, zero errors.

- [ ] **Step 2: Confirm zero remaining references to deleted/renamed symbols**

Run:
```bash
grep -rn "mockOptimize\|runMockOptimize" "/Users/doc/Downloads/Quant_Training_PNUTH/Project/Portfolio Optimization Webull:SEC OPENAI/frontend/src"
```
Expected: No output.

- [ ] **Step 3: Confirm the backend test suite is still green (no backend files touched, but this is the standard pre-merge gate for this project)**

Run: `pytest` (from the repo root, with the project venv active per
`CLAUDE.md`'s Commands section)
Expected: PASS, same pass count as before this plan (this plan makes no
backend changes, so this is a regression guard, not a new-coverage check).

- [ ] **Step 4: Playwright e2e**

Run: `npm --prefix frontend run test:e2e`
Expected: PASS. If `e2e/happy-path.spec.ts` (the only existing e2e spec)
exercises the Optimize workspace at all, confirm it still passes against
the real backend; if it only covers the Backtest workspace, this step is a
no-op regression guard.

- [ ] **Step 5: Report**

No commit for this task — it is a verification gate. If every step passes,
the plan is complete and ready for `superpowers:finishing-a-development-branch`.
