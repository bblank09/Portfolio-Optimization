# Frontend Cleanup And Asset Scalability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the backtest workspace feel like a deployable market-facing product by stripping non-essential copy and converting both asset-related panels into fixed-height, internally scrollable sections that stay usable with 100+ funds.

**Architecture:** Keep the current page structure and interaction model intact. Apply targeted copy reduction in `BacktestWorkspace`, `FundSelector`, and `PortfolioEditor`, then add bounded-list styling in `styles.css` so the fund-universe list and selected-portfolio list each show roughly five rows and scroll internally without changing API contracts or business logic.

**Tech Stack:** React, TypeScript, Vite, CSS, existing frontend component structure in `frontend/src/`

## Global Constraints

- Keep the current overall layout and interaction model.
- Remove explanatory text that does not help the user make the next decision.
- Preserve existing search behavior in the fund universe section.
- Keep the existing card-based layout and weight-editing workflow.
- Do not redesign the objective system.
- Do not change result tabs or analysis content structure.
- Do not introduce pagination, virtualized lists, or grouped taxonomy browsing.
- Do not change API payloads or validation rules.
- `SEC Fund Universe` and `Portfolio` must each become fixed-height list panels sized for approximately five visible rows with internal scrolling.
- Preserve the current two-line row pattern with strong primary label and compact secondary identifier.
- Frontend verification must include search, add/remove, weight editing, bounded scrolling, responsive behavior, and production build success.

---

### Task 1: Clean Product Copy In Workspace Panels

**Files:**
- Modify: `frontend/src/pages/BacktestWorkspace.tsx`
- Modify: `frontend/src/components/FundSelector.tsx`
- Modify: `frontend/src/components/PortfolioEditor.tsx`
- Test: `frontend/src/pages/BacktestWorkspace.tsx`

**Interfaces:**
- Consumes: existing `BacktestRequest`, `Objective`, `SecFund`, and current component props without signature changes
- Produces: slimmer UI copy only; no prop or type contract changes

- [ ] **Step 1: Remove the non-essential copy from the objective panel in `BacktestWorkspace.tsx`**

```tsx
<div className="panelHeader">
  <h2>Objective preset</h2>
</div>
...
<button ...>
  <strong>{objective.label}</strong>
</button>
...
<div className="objectiveNote">
  <strong>{activeObjective.label}</strong>
</div>
```

Required removals from the current file:
- remove `Auto-fill, editable`
- remove `objective.subtitle`
- remove the long `activeObjective.description`
- remove the `presetChips` block
- remove the `Always shown after every run...` helper text

- [ ] **Step 2: Remove the non-essential copy from the fund selector and portfolio panels**

```tsx
// FundSelector
<div className="panelHeader">
  <h2>SEC Fund Universe</h2>
  <span className="badge">{funds.length} funds</span>
</div>

// PortfolioEditor
<div className="panelHeader">
  <h2>Portfolio</h2>
  <span className={valid ? "badge success" : "badge warn"}>{totalWeight.toFixed(1)}%</span>
</div>
```

Required removals from the current files:
- remove `Cached from SEC Open Data`
- remove the per-row `fund.search_term` display for selectable rows
- remove `Weights must sum to 100%`

- [ ] **Step 3: Reduce the review/run and empty-result copy to product-style language**

```tsx
// BacktestWorkspace ready state
<p className="hintText">Ready to run</p>

// RunSummary empty state
<h2>Run a backtest to see results.</h2>
```

Required changes:
- remove `No mock values in production output`
- replace the long ready-state sentence with a compact ready-state line
- shorten the empty-result headline
- remove `Output tabs will render from cached SEC Open Data only.`

- [ ] **Step 4: Run frontend build to verify the copy-only cleanup compiles cleanly**

Run: `npm run build`

Expected: Vite production build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit the copy-cleanup task**

```bash
git add frontend/src/pages/BacktestWorkspace.tsx frontend/src/components/FundSelector.tsx frontend/src/components/PortfolioEditor.tsx
git commit -m "feat: simplify workspace copy"
```

### Task 2: Add Bounded Asset List Layout For 100+ Funds

**Files:**
- Modify: `frontend/src/components/FundSelector.tsx`
- Modify: `frontend/src/components/PortfolioEditor.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/components/FundSelector.tsx`
- Test: `frontend/src/components/PortfolioEditor.tsx`

**Interfaces:**
- Consumes: existing component props and current DOM structure for fund rows and allocation rows
- Produces: new bounded-list class names and fixed-height scroll behavior; component prop signatures remain unchanged

- [ ] **Step 1: Add explicit bounded-list wrappers to both asset panels**

```tsx
// FundSelector
<div className="fundList boundedList">
  {filtered.map(...)}
</div>

// PortfolioEditor
<div className="allocationList boundedList">
  {assets.map(...)}
</div>
```

Requirements:
- keep the search box above the scrollable fund list
- keep the panel headers outside the scroll area
- do not change button semantics or row edit controls

- [ ] **Step 2: Cap the rendered fund rows to a product-friendly scroll section instead of a long page stretch**

```tsx
const filtered = funds.filter(...);
```

Implementation requirements:
- stop slicing to 8 rows in the selector
- render the filtered set inside the bounded scroll container
- rely on internal scrolling rather than truncating useful results too aggressively
- keep disabled state for already-added funds

- [ ] **Step 3: Add shared CSS for five-row bounded sections in `frontend/src/styles.css`**

```css
.boundedList {
  max-height: 23rem;
  overflow-y: auto;
}
```

Also add supporting styles as needed for:
- row spacing that still looks clean inside a fixed-height card
- scrollbar-safe padding
- mobile adjustments so the bounded behavior remains usable on smaller screens

Do not redesign unrelated panels while editing this stylesheet.

- [ ] **Step 4: Verify the interaction path manually by reading the updated component flow**

Check against the code after editing:
- search input still updates `query`
- filtered rows still call `onAdd(fund)`
- portfolio rows still call `onWeightChange(...)`
- remove button still calls `onRemove(...)`

Expected: no prop wiring or action callback changes were introduced.

- [ ] **Step 5: Run frontend build to verify the bounded-list layout changes**

Run: `npm run build`

Expected: Vite production build succeeds and generated assets compile cleanly.

- [ ] **Step 6: Commit the bounded-list task**

```bash
git add frontend/src/components/FundSelector.tsx frontend/src/components/PortfolioEditor.tsx frontend/src/styles.css
git commit -m "feat: bound asset lists for large fund sets"
```

### Task 3: Final UX Verification And Responsive Polish

**Files:**
- Modify: `frontend/src/pages/BacktestWorkspace.tsx`
- Modify: `frontend/src/components/FundSelector.tsx`
- Modify: `frontend/src/components/PortfolioEditor.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/main.tsx`

**Interfaces:**
- Consumes: the cleaned copy and bounded-list structure from Tasks 1-2
- Produces: final polish only; no new API or component contracts

- [ ] **Step 1: Check the left-rail hierarchy for any remaining non-product helper copy**

Review these sections in code:
- workspace header
- objective preset
- fund universe
- portfolio
- review and run

Remove any leftover line that still reads like documentation instead of product UI, but do not remove labels or required validation feedback.

- [ ] **Step 2: Tune the bounded-list height and row density for the “five visible rows” target**

```css
.fundList.boundedList { ... }
.allocationList.boundedList { ... }
```

Expected outcome:
- desktop shows roughly five rows before scrolling
- mobile still keeps a bounded section without crushing row controls

- [ ] **Step 3: Run the full frontend verification pass**

Run: `npm run build`

Expected: PASS

Manual verification checklist:
- fund search still narrows results
- already-added funds still show as unavailable
- adding a fund still appends it to portfolio
- removing a fund still updates selected assets
- weight editing still works
- fund universe panel does not grow with 100+ results
- portfolio panel does not grow beyond the bounded height when many assets are selected

- [ ] **Step 4: Record the final deliverable in a concise change summary comment inside the plan execution notes**

```text
Product copy reduced, asset panels bounded to five-row scroll sections, search/add/remove/edit flows preserved.
```

This is not a code change; it is the required execution-note output for whoever implements the plan.

- [ ] **Step 5: Commit the final polish task**

```bash
git add frontend/src/pages/BacktestWorkspace.tsx frontend/src/components/FundSelector.tsx frontend/src/components/PortfolioEditor.tsx frontend/src/styles.css
git commit -m "feat: polish scalable asset selection UX"
```
