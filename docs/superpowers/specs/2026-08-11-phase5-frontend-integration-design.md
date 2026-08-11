# Phase 5 sub-project 6 (final): Frontend Integration — Design

Status: **approved, not yet implemented.** Sixth and final sub-project of the
expanded Phase 5 backend-gap-closing roadmap. Sub-projects 1 (backend
optimizer core), 2 (rolling out-of-sample evaluator), 3 (comparison
features), 4 (portfolio constraint completion), and 5 (return-method
completion + rolling lookback + robust optimization) are complete and merged
to `main`. Every backend gap identified during the audit chain is now closed.
This sub-project replaces the frontend's fabricated mock computation with
real `POST /api/optimize` calls — the last piece of Phase 5.

## Why this sub-project exists

`frontend/src/lib/mockOptimize.ts` (795 lines) has stood in for a real
backend since Phase 4. `backend/app/api/optimize.py`'s `POST /api/optimize`
route is now fully real and feature-complete. A fresh field-parity audit
(this session) found the frontend UI itself is in better shape than an
earlier session's notes assumed — `compareAgainst`, the `robustOptimization`
checkbox, and `returnMethod` (including `capm_implied`) are already wired to
real request fields with no leftover "disabled" logic from Phase 4. The
actual gaps are narrower:

1. `frontend/src/types/optimize.ts`'s `OptimizeResult` is missing
   `compareNote`, `constraintNote`, and `robustOptimizationNote` entirely,
   and its `robustNote` field carries a stale comment describing a meaning
   that field no longer has (sub-project 2 repurposed it for rolling-
   validation caveats).
2. `OptimizeConstraints` has no `rollingWindowMode` field, and the UI has no
   control for it at all — every request implicitly uses `"expanding"`.
3. The whole app still calls `runMockOptimize` instead of the real endpoint.

## Scope

**In scope:** field-parity fixes to `types/optimize.ts`; a new `runOptimize`
API client function; switching `OptimizeWorkspace.tsx`'s two call sites
(`submit()` and the share-link restore effect) to the real endpoint; adding
a `rollingWindowMode` UI control; extracting `estimateEquilibriumReturns`
out of `mockOptimize.ts` into its own module; deleting `mockOptimize.ts`;
removing the "Mock UI — Phase 4" header tag; updating tests that assumed
mock output.

**Out of scope:** any backend change (all backend gaps are closed);
redesigning the Results tabs or Assumptions step layout beyond the one new
control; changing `OptimizeAssumptionsStep.tsx`'s existing compareAgainst/
robustOptimization controls (already correct).

## Architecture

The swap is mechanical, not structural. `OptimizeWorkspace.tsx` already
owns a `loading`/`error`/`result` state triple built around an async-shaped
call (`submit()` already `await`s an artificial delay before invoking the
mock). Both call sites of `runMockOptimize(request)` — a synchronous,
deterministic function — become `await runOptimize(request)`, a new
`api/client.ts` function following the established `runBacktest` pattern
exactly:

```ts
export async function runOptimize(payload: OptimizeRequest): Promise<OptimizeResult> {
  return requestJson<OptimizeResult>("/api/optimize", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
```

`requestJson` already handles the `assertSecOnly` check, JSON parsing, and
throwing `Error(extractErrorMessage(text))` on any non-2xx response — no new
error-handling design is needed. `extractErrorMessage` already parses
`AppHTTPException.detail` in both its string and validation-array shapes,
covering every `ErrorCode` the real `/api/optimize` route raises
(`NAV_CACHE_MISSING` 503, `VALIDATION_ERROR`/`INFEASIBLE_CONSTRAINTS`/
`SOLVER_NON_CONVERGENCE`/etc. 422, `RATE_LIMITED` 429, `INTERNAL_ERROR` 500).
`OptimizeResults.tsx` already renders `result.feasibility !== "ok"` as an
inline banner using `feasibilityMessage` — the soft-failure path (non-
convergence, insufficient rolling history) is already fully wired to real
backend semantics and needs no new UI.

## File-by-File Changes

1. **`frontend/src/types/optimize.ts`** — field-parity fixes:
   - Add `compareNote: string | null` to `OptimizeResult` (sub-project 3).
   - Add `constraintNote: string | null` to `OptimizeResult` (sub-project 4).
   - Add `robustOptimizationNote: string | null` to `OptimizeResult`
     (sub-project 5).
   - Fix `robustNote`'s comment from `// set when request.robustOptimization
     is true` (its stale, pre-sub-project-2 meaning) to describe its actual
     meaning: rolling out-of-sample validation caveats.
   - Add `rollingWindowMode: "expanding" | "trailing"` to
     `OptimizeConstraints`.

2. **`frontend/src/api/client.ts`** — add `runOptimize`, mirroring
   `runBacktest`'s exact shape (see Architecture above). Import
   `OptimizeRequest`/`OptimizeResult` from `../types/optimize`.

3. **`frontend/src/lib/blackLittermanPreview.ts`** (new file) —
   `estimateEquilibriumReturns` moved here verbatim from `mockOptimize.ts`.
   This function is a live client-side preview of the Black-Litterman
   equilibrium return (Π) shown in the BL card while the user adjusts risk
   aversion/tau, before running the optimization — genuinely distinct from
   the mock optimizer output it happened to share a file with, so it is
   preserved rather than deleted.

4. **`frontend/src/lib/mockOptimize.ts`** — deleted in full, along with its
   fixture/helper exports no longer referenced anywhere.

5. **`frontend/src/pages/OptimizeWorkspace.tsx`**:
   - `submit()` becomes `async`, calls `await runOptimize(request)` instead
     of `runMockOptimize(request)`. The artificial 900ms
     `window.setTimeout` delay is removed — real network latency now
     stands in for it, and the existing `RunOverlay` staged UI already
     covers the wait with no new latency-specific messaging (including for
     `robustOptimization=true`'s ~7s real solve time, per decision).
   - The share-link restore effect (`?state=` query param) becomes async:
     on a successful decode with ≥2 restored funds, it sets `loading`,
     `await`s `runOptimize(restored)`, and on success proceeds to Results
     exactly as before. On failure (a real thrown `Error`, e.g. stale
     shared state pointing at fund IDs the current cache can't serve), it
     sets the `error` state with the caught message and leaves the user on
     Step 1 with their restored selections — replacing today's silent
     `catch {}` swallow, which stranded the user with no explanation.
   - The header's `"Mock UI — Phase 4, no live optimizer yet"` tag is
     removed.
   - Swap the `estimateEquilibriumReturns` import source in any file that
     needs it (see below) and remove the `runMockOptimize`/`mockOptimize`
     import from this file entirely.

6. **`frontend/src/components/OptimizeAssumptionsStep.tsx`**:
   - Import `estimateEquilibriumReturns` from `../lib/blackLittermanPreview`
     instead of `../lib/mockOptimize`.
   - Add a `rollingWindowMode` select control (options: `"expanding"`,
     `"trailing"`) next to the existing `lookbackPeriodMonths` and
     `optimizationFrequency` constraint controls, defaulting to
     `"expanding"`. Wire via the same `patchConstraints({ rollingWindowMode:
     event.target.value as OptimizeRequest["constraints"]["rollingWindowMode"]
     })` pattern already used for `lookback`/`optimizationFrequency`.

## Error Handling

No new mechanism. `runOptimize` throws the same `Error` shape
`runBacktest`/`fetchFunds`/`fetchTestableRange` already throw, caught by
`submit()`'s existing `try { ... } catch (caught) { setError(...) }
finally { setLoading(false) }` — unchanged except for what it now awaits.
The only new behavior is the restore effect surfacing a real error instead
of swallowing it (see File-by-File Changes above).

## Testing

- Any existing unit/component test that imports or mocks `runMockOptimize`
  directly is updated to mock `runOptimize` from `api/client.ts` instead.
- Playwright e2e (`npm run test:e2e`): update the optimize-flow spec(s) that
  currently assert on the mock's deterministic output to tolerate real
  solver output (assert on shape/invariants — weights sum to ~100%, presence
  of expected fields — not exact fabricated numbers). Add one new e2e case
  that sets `rollingWindowMode` to `"trailing"` via the new control and
  confirms the request round-trips (rolling tab renders fold data) rather
  than silently defaulting back to `"expanding"`.
- Manual smoke pass across all 7 objectives through the real UI, plus one
  `robustOptimization=true` run to confirm the ~7s real latency renders
  correctly through the existing `RunOverlay`.
