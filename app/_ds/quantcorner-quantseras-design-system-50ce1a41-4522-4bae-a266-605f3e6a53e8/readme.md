# QuantCorner / QuantSeras Design System

Shared visual system for two sibling brands under one owner (Nuthdanai Wangpratham):

- **QuantCorner** — editorial, media, community, top-of-funnel discovery. Curious, approachable, evidence-led.
- **QuantSeras** — education, product, labs, dashboards, research depth. Structured, rigorous, product-led.

Both share one foundation (color, type, icon semantics, spacing, motion, accessibility, data-viz rules) and diverge only in composition: QuantCorner reads as editorial rows, QuantSeras reads as an answer-first dashboard.

## Source of truth

This project is built from a portable handoff package the owner exported for AI/design tooling, mounted at `QuantSeras-Design-System-Handoff-2026-07-24/` during this build (not present in this project's own filesystem):

- `02-guidelines/CANONICAL-DESIGN-SYSTEM.md` — the full visual spec (this readme's primary source)
- `02-guidelines/COMPONENTS-AND-PATTERNS.md`, `DATA-VISUALIZATION.md`, `RELEASE-CHECKLIST.md`
- `01-foundations/tokens.json`, `04-starter-code/quantseras.css`, `tailwind-theme.ts`
- `03-assets/brand/` (QuantCorner logo package), `03-assets/icons/quantseras-reference-library/` (606 reference PNGs + catalog)
- `06-governance/asset-sources.json`, `asset-governance.md`, `THIRD-PARTY-NOTICES.md`
- `05-ai-handoff/AGENTS.md`, `PROMPT.md`

**Important:** the package is a governance/spec handoff — it contains no bundled product code, Figma file, or screenshots of a shipped app. `React Bits`, `Astryx`, and `Unlumen UI` are referenced-but-not-bundled (install-on-demand, license-gated). Several referenced local workspace paths (`/Users/nuthdanai/...`) were reported by the source's own README as removed by the owner on 2026-07-20 and were not accessible to this build. The UI kits and slides in this project are original compositions built strictly from the spec's written rules (answer-first hierarchy, editorial row grammar, six slide archetypes) — not a recreation of a specific screenshot, since none was provided.

## Components

`components/core/` — **Surface**, **Button**
`components/forms/` — **Input**, **Select**, **Checkbox**, **Radio**, **Switch**
`components/feedback/` — **Status**, **Dialog**, **Tooltip**
`components/data/` — **Metric**, **DataTable**

This is the exact "required core primitives" list from `COMPONENTS-AND-PATTERNS.md` (Surface, Button, Status, Metric, form controls, data table, dialog/tooltip), expanded into one file per control. **Intentional addition:** `Switch` — the spec names "form controls" generically and separately governs an Unlumen `Switch` pattern; it's the natural on/off complement to Checkbox/Radio.

## UI kits

- `ui_kits/dashboard/` — QuantSeras Analysis dashboard (interactive: Analysis / Watchlist tabs, theme switch). Answer-first: interpretation → answer → drivers → diagnostics → method/limitations.
- `ui_kits/editorial/` — QuantCorner research feed. Numbered, asymmetric rows — deliberately not a card grid.
- `slides/` — the six one-message research-slide archetypes from the canonical spec: Assertion, Evidence, Comparison, Process, Decision, Methodology.

## Assets

- `assets/brand/` — the owner-approved **QuantCorner** logo package (mark, wordmark, app icon, favicons). QuantSeras has no separate approved wordmark of its own — do not relabel this mark as QuantSeras branding.
- `assets/icons/quantseras-reference/` — a curated ~24-icon sample plus the full catalog JSON from the 606-icon QuantSeras reference library (course/education/search use; not blanket-approved for product UI — see Iconography).

## Tokens

`tokens/colors.css`, `typography.css`, `spacing.css`, `motion.css`, `base.css`, imported by root `styles.css`. Dark is the primary theme (`:root`/`[data-theme="dark"]`); light is supporting (`[data-theme="light"]`).

---

## Content fundamentals

No product copywriting samples (marketing pages, app strings, onboarding text) were included in the handoff — it is a governance/spec document, not a content corpus. The fundamentals below are extracted directly from the spec's own stated voice and rules, not invented:

- **Voice:** "a credible quant research house that communicates its reasoning, evidence, and limitations clearly without overstating precision." Confident but hedged — claims are always scoped to a sample, window, and method.
- **Structure over adjectives:** copy leads with the interpretation/answer, then context, then a stated limitation — never a headline number alone.
- **No forecast certainty:** never imply a model "can forecast prices or returns with certainty"; every simulated or historical figure is labeled illustrative, sample, or backtested — never presented as live or predictive without saying so.
- **Precision in units:** every metric states its unit, period, and comparator ("Sharpe 1.42, trailing 12mo, +0.18 vs. benchmark") — bare numbers don't appear.
- **No emoji, no hype adjectives.** Tone is closer to a research note than a product marketing page.
- **Em/en dashes are avoided** in the spec's own verification criteria ("no em dashes, en dashes... in the HTML") — use plain hyphens or restructure the sentence.
- **Thai-language content** is a first-class, not translated-afterthought, register — Noto Sans Thai pairs at the same semantic weight as Roboto, not smaller or lighter.

## Visual foundations

- **Color:** exact Material Design 2 baseline. Dark primary (`#121212` background, `#BB86FC` primary / purple, `#03DAC6` secondary / teal, `#CF6679` error). Light supporting (`#FFFFFF`, `#6200EE` primary, same secondary/error family, `#B00020` error). Purple = interactive emphasis; teal = comparison/benchmark/secondary action. Both are reserved for small emphasis points — controls, active indicators, links, status — never large decorative fills or full-width strips. `#69F0AE` (green) is a **retired** token: it survives only, unaltered, as the small "evidence point" dot inside the approved QuantCorner logo, which must not be redrawn — do not reuse that green anywhere else.
- **Type:** Roboto for Latin UI/prose, Noto Sans Thai for Thai content at the same semantic role, Roboto Mono strictly for aligned numbers/code/tickers/IDs (never prose). A bounded `clamp()` scale from a rare hero metric (40–64px) down to 12–14px labels. Hierarchy comes from size/weight/whitespace before color.
- **Spacing:** a vocabulary (4/8/12/16/24/32/48/64/96), not a forced grid — sections, evidence, and actions may use different rhythms; compositions are intentionally asymmetric, not a repeating equal-card matrix.
- **Backgrounds:** flat neutral surfaces. No gradients, no glow, no mesh backgrounds behind data, forms, or status text (mesh gradients are reference-only, reserved for bounded covers/openers if ever adopted). No photography or full-bleed imagery was provided by the source.
- **Animation:** motion only communicates a state change, sequence, progress, or causality (120/200/320ms, one standard ease `cubic-bezier(0.4,0,0.2,1)`) — never idle/ambient effects, and always honoring `prefers-reduced-motion`.
- **Hover / press:** hover uses a lightened fill (primary/secondary blended toward white) or a low-opacity tonal wash for outlined/text buttons; press moves a primary button to the darker `primary-variant` and drops its elevation — never opacity alone as the only signal.
- **Borders & shadows:** dark theme expresses elevation as *lighter surface overlays* (0–24dp), never a shadow-on-black; light theme uses real shadows since white-on-white can't show a tonal shift. Outlined surfaces use a flat 1px border (`rgb(255 255 255 / 12%)` on dark) to group content without adding weight.
- **Corner radii:** small and consistent — 4px controls, 8px cards/dialogs, pill (999px) for status chips and switches. No large "friendly" rounding.
- **Transparency / blur:** none by default; the only sanctioned blur (`Unlumen ProgressiveBlur`) is an edge treatment for a bounded feed and is not implemented here (registry-only source, not bundled).
- **Hit targets:** every interactive control keeps a 48px accessible hit area even when its visible shape is smaller (e.g. a 20px checkbox).

## Iconography

- **Primary/production icons — Tabler Icons** (MIT, CDN-linked here via `@tabler/icons-webfont`): 24px grid, 2px outline stroke, recolored through `currentColor`.
- **Domain/section anchors — Game Icons**: 32–72px, one per section, named-author attribution required; never used as a clickable control. Not bundled locally (fetch the specific SVGs on demand at the pinned commit in `asset-sources.json` if adopting).
- **Expressive anchors — Microsoft Fluent Emoji**: at most one per view, for narrative/demo/onboarding moments only — never a status, metric, or command.
- **Avatars — DiceBear Bottts**: avatars only, never controls.
- **Fallback — Lucide** only when Tabler has no equivalent glyph; never mixed with Tabler in the same view. **OpenMoji** is stored but disabled by default (CC BY-SA attribution burden).
- **The 606-icon QuantSeras reference PNG library** (`assets/icons/quantseras-reference/`) is a search/course/concept-exploration library, not pre-approved for product UI — promote an icon to production only after confirming role, license, and owner approval, per the source package.
- No emoji are used as literal UI glyphs; Fluent Emoji is the one sanctioned "emoji-like" expressive layer, and only in the restrained role above.

## Intentional additions

- `Switch` component (see Components, above).
- The six slide archetypes and the two UI kits are original layouts composed strictly from the spec's written grammar — no visual source (screenshot, Figma, code) defined their exact composition, since none was provided.

## Font substitution note

Roboto, Roboto Mono, and Noto Sans Thai are loaded from Google Fonts CDN (`tokens/typography.css`) — these are exact matches to the spec (no substitution needed), but the source package calls for **Fontsource-bundled, offline-hostable** font files ("must not depend on external font requests"). No font binaries were included in the handoff package. **Ask:** if strict offline/production compliance matters, please supply the Fontsource `5.2.8` `.woff2` files (or approve CDN loading) and this project will be updated to self-host them.

## Index

```
styles.css                    → root stylesheet (imports tokens/*)
tokens/                        colors, typography, spacing, motion, base
components/core/               Surface, Button
components/forms/               Input, Select, Checkbox, Radio, Switch
components/feedback/            Status, Dialog, Tooltip
components/data/                Metric, DataTable
guidelines/colors/              5 specimen cards (elevation, brand/semantic, light theme, text emphasis, retired token)
guidelines/type/                3 specimen cards (scale, mono data role, Thai pairing)
guidelines/spacing/              3 specimen cards (scale, hit target, grouping)
guidelines/motion/               1 specimen card (duration/easing)
guidelines/brand/                2 specimen cards (logo, app icon)
guidelines/icons/                2 specimen cards (governance matrix, reference library sample)
ui_kits/dashboard/              QuantSeras Analysis dashboard (interactive)
ui_kits/editorial/               QuantCorner research feed
slides/                         6 research-slide archetypes
assets/brand/, assets/icons/    logo package, curated icon sample + full catalog
SKILL.md                        portable skill for Claude Code / other agent tooling
```
