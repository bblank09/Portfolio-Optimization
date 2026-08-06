# Purple Primary Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make purple the primary product color while reducing green to semantic success/source-status usage only.

**Architecture:** Adjust the frontend palette in the existing styling surface and chart color assignments only. Keep layout, copy, and logic unchanged while making buttons, neutral badges, and interactive highlights align to a purple-led brand system.

**Tech Stack:** React, TypeScript, Vite, CSS

## Global Constraints

- Do not change layout or interaction patterns.
- Do not change logic or API behavior.
- Make purple the primary product color.
- Reduce green to semantic success or source-status usage only.
- Keep warning and error semantics intact.
- Verify with `npm run build`.

---

### Task 1: Unify Primary UI Palette

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/components/RunSummary.tsx`

**Interfaces:**
- Consumes: existing class names, component structure, and chart series definitions
- Produces: updated color assignments only; no prop or logic changes

- [ ] **Step 1: Update primary and neutral interactive colors in `frontend/src/styles.css`**

Change the brand-driving green usages to purple-led values:
- `primaryButton`
- default `badge` / `fundTag`
- any other non-semantic interactive purple/green split that currently makes branding inconsistent

- [ ] **Step 2: Preserve semantic greens only where they communicate status**

Keep or refine green only for:
- `.badge.success`
- `.successText`
- `.sourceLine` if it remains a source-status indicator

- [ ] **Step 3: Update chart companion colors in `frontend/src/components/RunSummary.tsx`**

Replace the teal/green companion series colors with purple-compatible secondary tones while keeping the portfolio series visually dominant.

- [ ] **Step 4: Run frontend verification**

Run: `npm run build`

Expected: PASS
