# Frontend Cleanup And Asset List Scalability Design

Date: 2026-07-28

## Goal

Refine the backtest workspace so it feels closer to a deployable market-facing product:

- remove explanatory text that does not help the user make the next decision
- keep the current overall layout and interaction model
- make both the fund universe picker and selected portfolio list usable with 100+ assets

This design intentionally avoids changing the core workflow, business logic, or backend contracts.

## Scope

In scope:

- text reduction and hierarchy cleanup in the left rail and empty states
- fixed-height internal-scroll sections for both fund selection and selected assets
- preserving existing search behavior in the fund universe section
- keeping the existing card-based layout and weight-editing workflow

Out of scope:

- redesigning the objective system
- changing result tabs or analysis content structure
- introducing pagination, virtualized lists, or grouped taxonomy browsing
- changing API payloads or validation rules

## Recommended Approach

Use a conservative product-cleanup pass:

1. Keep the current page structure.
2. Strip non-essential helper copy.
3. Convert both asset-related sections into fixed-height list panels that show about five rows and scroll internally.

This is the smallest change that gives the workspace a more production-ready feel without retraining the user on a new interaction model.

## Text Removal Plan

The following text should be removed or significantly reduced because it is either redundant, instructional in a non-product way, or too verbose for a real deployed workflow.

### Backtest Workspace Header

Keep:

- `Portfolio Backtester`
- `SEC Open Data only`
- action buttons

Remove:

- none required beyond preserving the compact badge treatment already in place

### Objective Preset Panel

Keep:

- panel title
- objective labels
- active/selected visual state

Remove:

- `Auto-fill, editable`
- objective subtitle text on every card
- long active-objective description paragraph
- `Required:` chip list
- `Optional:` chip list
- preset summary chip cluster
- `Always shown after every run: Benchmark Risk, Drawdown Stress, Diversification Check, CQF Report.`

Replace with:

- at most one short line under the active objective name if needed, but default target is no extra paragraph copy

### SEC Fund Universe Panel

Keep:

- panel title
- total fund count
- search field
- fund display name
- secondary identifier line

Remove:

- `Cached from SEC Open Data`
- search-term badge text on each row when it is not necessary for selection

Refine:

- keep `Added` state for already-selected funds
- secondary line should stay compact and scannable

### Portfolio Panel

Keep:

- panel title
- total weight badge
- fund name
- `proj_id`
- weight input
- remove button

Remove:

- `Weights must sum to 100%`

Rationale:

- the total-weight badge and validation state already communicate this better than persistent instructional text

### Review And Run Panel

Keep:

- panel title
- readiness badge
- validation errors when present

Remove:

- `No mock values in production output`
- long ready-state paragraph summarizing start date, end date, benchmark, cashflow, and rebalancing in one sentence

Replace with:

- a single compact ready-state line such as `Ready to run`

### Empty Result State

Keep:

- clear indication that no run has been executed yet

Reduce:

- shorten `Choose an objective, confirm inputs, then run a backtest.`
- remove `Output tabs will render from cached SEC Open Data only.`

Target tone:

- short, product-like, action-oriented

## Layout Design For 100+ Assets

### SEC Fund Universe

Behavior:

- maintain the existing section location in the left rail
- keep search exactly where it is conceptually
- keep add-to-portfolio row action

Visual/layout changes:

- section body becomes a fixed-height list container sized for approximately five rows
- overflow scrolls inside the panel instead of stretching the page
- section header remains visible above the list
- search bar remains above the scrollable list

Expected result:

- the panel stays compact regardless of whether there are 20 or 200 funds
- the user can search first, then scroll within a bounded area

### Portfolio

Behavior:

- maintain the current selected-asset editing model
- keep inline weight editing and remove action

Visual/layout changes:

- selected assets render inside a fixed-height list container sized for approximately five rows
- overflow scrolls internally inside the panel
- total-weight badge remains in the header
- empty state still appears when nothing is selected

Expected result:

- selected allocations remain manageable even when the user builds a large portfolio
- the assumption and run panels do not get pushed far below the fold

## Interaction Details

### Fund Universe List

- search filters the full fund set exactly as today
- filtered results render in the bounded scroll area
- already-selected assets remain disabled
- the row should remain one-click add

### Portfolio List

- editing weights must still happen directly in the row
- removing an asset should not change the scrolling pattern
- validation remains outside the list, in the run-readiness area and/or badge states

## UX Principles

- prefer labels over explanations
- preserve fast scanning
- keep visible controls within one screenful
- remove “developer/demo” language
- make the left rail feel like a production form, not documentation

## Files Likely To Change

- `frontend/src/pages/BacktestWorkspace.tsx`
- `frontend/src/components/FundSelector.tsx`
- `frontend/src/components/PortfolioEditor.tsx`
- supporting styles in the current frontend styling surface used by these components

## Testing Plan

- confirm the workspace still renders with no result
- confirm search still filters fund results
- confirm fund add/remove still works
- confirm weight editing still works
- confirm both asset sections cap at roughly five visible rows and scroll internally
- confirm the page remains usable on smaller laptop screens and mobile widths
- run frontend production build after changes

## Risks And Mitigations

Risk:

- removing too much copy may make the objective area feel contextless

Mitigation:

- preserve objective labels and active-state emphasis; only reintroduce one compact helper line if the panel feels too bare after implementation

Risk:

- fixed-height panels may feel cramped on mobile

Mitigation:

- use responsive height tuning so mobile keeps the bounded-list behavior without making row controls too tight

Risk:

- selected portfolio rows may become hard to scan with long fund names

Mitigation:

- preserve the two-line row pattern with strong primary label and compact secondary identifier

## Implementation Shape

1. Remove the non-essential text listed above.
2. Add shared bounded-list styling for asset sections.
3. Apply that styling to `FundSelector`.
4. Apply the same bounded-list behavior to `PortfolioEditor`.
5. Tighten ready/empty-state copy.
6. Verify responsive behavior and build output.
