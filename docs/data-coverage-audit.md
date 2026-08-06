# NAV data coverage audit

Investigation into "Backtest cannot calculate with incomplete NAV periods"
errors reported after the full-universe pull (checklist 8.8), following
`superpowers:systematic-debugging`.

## The error is correct, expected behavior

`backend/app/engine/backtest.py` rejects a backtest whose selected assets or
benchmark are missing any monthly (or daily) NAV observation inside the
requested date range, rather than silently interpolating over a gap. This
is intentional — verified in [docs/4.3-report.md](verification/4.3-report.md)
and the project's standing "never fabricate data" rule. **The check itself
is not the bug.** The question this audit answers is *why* real funds hit
it, and whether users can find out beforehand instead of after filling in
the whole form.

## Root causes found (all real, none are ingestion bugs)

Evidence gathered by comparing the cache against SEC's live API directly,
per Phase 1 of systematic-debugging — not guessed.

1. **Different fund inception dates.** Start dates across the 800-fund
   universe range from 2015-01-05 to 2026-07-27. A fund registered in 2026
   simply has no 2015 data — expected, not a defect.

2. **Real quarterly/semi-annual NAV reporting.** Many funds report NAV
   daily only during an initial launch window, then switch to quarterly
   (or less frequent) reporting for the rest of their life. Confirmed by
   inspecting exact date sequences, e.g. `M0420_2565`:
   `2022-10-05 .. 2022-10-25` (daily, 3 weeks) then
   `2022-12-30, 2023-03-31, 2023-06-30, ...` (quarter-end only) through
   2026-06-30. This is a real characteristic of the fund, not missing data
   from our download.

3. **The known SEC-wide gap, 2024-06-26 to ~2024-11-18** (documented
   separately in README §13) — affects the month-completeness check for
   any date range spanning it, for virtually every fund.

4. **A rare (2 of 800 funds) share-class ambiguity.** For `M0006_2539`
   (SCBRFFUND) and `M0061_2567`, the class chosen by
   `scripts/sec_build_mvp_universe.py` has only a few days/weeks of its own
   separately-tagged history, while a `main`-labeled bucket for the same
   proj_id has years of history. Queried SEC's live API directly: the
   `main` records long-predate the specific class label appearing at all,
   suggesting SEC only started tagging this proj_id's classes separately
   at some point — but whether `main` and the specific class are truly the
   same underlying series, or genuinely different classes that happen to
   share a proj_id, could not be determined with confidence from the API
   alone. **Left as-is rather than guessed at**: silently substituting
   `main` risks splicing together two different investments' NAV under one
   label, which would be a worse and *silent* error compared to today's
   loud one. These 2 funds simply have very little usable history right
   now under their designated class.

## What was fixed

Nothing about the underlying data was changed (per the rules above,
guessing at scenario 4 would risk fabricating a wrong series). The fix is
**making the real, already-true coverage information visible before a
user hits the wall**, instead of after filling in the whole form:

- `backend/app/data/quality.py::compute_month_coverage()` (unit tested) —
  given a fund's NAV dates, reports `nav_start`, `nav_end`, `nav_months`
  (calendar months actually observed), `nav_span_months` (calendar months
  from first to last observation), and `nav_completeness` = the ratio of
  the two. This is what distinguishes case 2 (real quarterly reporter,
  `nav_span_months` far exceeds `nav_months`) from a merely-young fund
  (`nav_span_months` == `nav_months`, both small).
- `scripts/sec_annotate_universe_coverage.py` — computes this for every
  fund from the real cached `daily_nav.parquet` and writes it into
  `data/sec/mvp_fund_universe.csv` as five new columns. `GET /api/funds`
  already returns the full CSV verbatim, so this data is queryable
  immediately with no other backend change. Re-run this after any NAV
  refresh (`sec_download_mvp.py`, `sec_repair_failed_requests.py`,
  `sec_dedupe_fund_classes.py`) to keep it in sync.
- `SecFund` (frontend type) now includes the five new fields, so a future
  UI change (e.g. showing a fund's real usable range inline while building
  a portfolio) doesn't need a backend change to build on.

## Current findings (2026-08-03 snapshot)

Run `python -m scripts.sec_annotate_universe_coverage` to refresh these
numbers after any data change.

- 800 / 800 funds have at least some NAV data (none are entirely empty).
- 87 / 800 funds (~11%) have `nav_completeness < 90%` — i.e. a real,
  non-trivial reporting gap somewhere in their own active span, not just a
  short history. Most are quarterly/semi-annual reporters (cause 2 above);
  2 are the share-class ambiguity (cause 4).
- The two original "preferred" funds most commonly used in examples
  (K-SET50 `M0209_2548`, M-S50 `M0155_2547`) both show `nav_completeness`
  around 97% — the ~3% gap is entirely the known 2024 SEC-wide incident,
  not a fund-specific issue.

## Not implemented (optional follow-up)

Surfacing this in the Portfolio-building UI itself (e.g. a small "usable
range: 2015-01 to 2026-07 (98% complete)" note per selected fund, or
clamping the Assumptions date pickers to the *intersection* of selected
funds' ranges rather than the whole cache's range) was not built — the
scope here was the audit and making the data queryable, not a new UI
feature. Worth doing as a follow-up if the wall-of-months error keeps
coming up in practice.
