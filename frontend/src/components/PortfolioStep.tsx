import { useEffect, useMemo, useRef, useState } from "react";
import type { FocusEvent, KeyboardEvent } from "react";
import { ChevronDown, Search, SlidersHorizontal, X } from "lucide-react";
import type { SecFund, SecFundAllocation } from "../types/backtest";

interface Row {
  key: string;
  projId: string;
  weight: number;
  query: string;
}

interface Facet {
  value: string;
  count: number;
}

// SEC's policy_desc is a Thai-language category label from the API. This
// map covers every value observed in the full 800-fund universe (checklist
// 8.8) -- verified against data/sec/mvp_fund_universe.csv, not just the
// handful of categories the original 12-fund universe happened to have.
const CATEGORY_LABELS_EN: Record<string, string> = {
  "ตราสารทุน": "Equity",
  "ตราสารหนี้": "Fixed Income",
  "ผสม": "Mixed",
  "ทรัพย์สินทางเลือก": "Alternative Assets",
  "อื่น ๆ": "Other",
  "ไม่ระบุ เนื่องจากเป็นกองทุนรวมอีทีเอฟแบบ leveraged management หรือ inverse management": "Unspecified (Leveraged/Inverse ETF)"
};

function categoryLabel(value: string) {
  return CATEGORY_LABELS_EN[value] ?? value;
}

// Concrete, checkable coverage text instead of an abstract percentage --
// names the actual gap (matches scripts/sec_annotate_universe_coverage.py's
// nav_gap_count/nav_largest_gap_start/nav_largest_gap_end) so a user can
// tell at a glance whether it overlaps their intended backtest window.
function formatCoverage(fund: SecFund): string | null {
  if (!fund.nav_start || !fund.nav_end) return null;
  const range = `${fund.nav_start.slice(0, 7)} to ${fund.nav_end.slice(0, 7)}`;
  const gapCount = fund.nav_gap_count ?? 0;
  if (gapCount === 0) return range;
  if (gapCount === 1 && fund.nav_largest_gap_start && fund.nav_largest_gap_end) {
    return `${range} · gap ${fund.nav_largest_gap_start} to ${fund.nav_largest_gap_end}`;
  }
  const months = fund.nav_months ?? 0;
  const span = fund.nav_span_months ?? 0;
  return `${range} · data only ${months}/${span} months (reports infrequently)`;
}

function buildFacets(funds: SecFund[], field: "amc_name_en" | "policy_desc", otherFilter: Set<string>, otherField: "amc_name_en" | "policy_desc") {
  const counts = new Map<string, number>();
  for (const fund of funds) {
    const key = fund[field];
    if (!key) continue;
    if (otherFilter.size && !otherFilter.has(fund[otherField])) continue;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => a.value.localeCompare(b.value));
}

interface Props {
  funds: SecFund[];
  active: boolean;
  onAssetsChange: (assets: SecFundAllocation[]) => void;
  onContinue: () => void;
}

const PALETTE = ["#5b21d6", "#34383e", "#92620a", "#9aa1ac", "#7c4ded"];

let rowSeq = 0;
function nextKey() {
  rowSeq += 1;
  return `row-${rowSeq}`;
}

export function PortfolioStep({ funds, active, onAssetsChange, onContinue }: Props) {
  const [rows, setRows] = useState<Row[]>([{ key: nextKey(), projId: "", weight: 0, query: "" }]);
  const [amcFilter, setAmcFilter] = useState<Set<string>>(new Set());
  const [categoryFilter, setCategoryFilter] = useState<Set<string>>(new Set());
  const seededRef = useRef(false);

  const fundsById = useMemo(() => new Map(funds.map((fund) => [fund.proj_id, fund])), [funds]);

  const amcFacets = useMemo(
    () => buildFacets(funds, "amc_name_en", categoryFilter, "policy_desc"),
    [funds, categoryFilter]
  );
  const categoryFacets = useMemo(
    () => buildFacets(funds, "policy_desc", amcFilter, "amc_name_en"),
    [funds, amcFilter]
  );

  const filteredFunds = useMemo(
    () =>
      funds.filter((fund) => {
        if (amcFilter.size && !amcFilter.has(fund.amc_name_en)) return false;
        if (categoryFilter.size && !categoryFilter.has(fund.policy_desc)) return false;
        return true;
      }),
    [funds, amcFilter, categoryFilter]
  );

  function toggleFilter(setter: (updater: (current: Set<string>) => Set<string>) => void, value: string) {
    setter((current) => {
      const next = new Set(current);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function clearAllFilters() {
    setAmcFilter(new Set());
    setCategoryFilter(new Set());
  }

  useEffect(() => {
    if (seededRef.current || funds.length < 2) return;
    seededRef.current = true;
    seedRows(funds.slice(0, 2).map((fund, index) => ({ fund, weight: index === 0 ? 60 : 40 })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [funds]);

  function commit(nextRows: Row[]) {
    setRows(nextRows);
    const assets: SecFundAllocation[] = nextRows
      .filter((row) => row.projId)
      .map((row) => ({
        proj_id: row.projId,
        display_name: fundsById.get(row.projId)?.display_name ?? row.query,
        weight: row.weight
      }));
    onAssetsChange(assets);
  }

  function seedRows(picks: { fund: SecFund; weight: number }[]) {
    commit(picks.map(({ fund, weight }) => ({ key: nextKey(), projId: fund.proj_id, weight, query: fund.display_name })));
  }

  function addRow() {
    commit([...rows, { key: nextKey(), projId: "", weight: 0, query: "" }]);
  }

  function removeRow(key: string) {
    if (rows.length <= 1) return;
    commit(rows.filter((row) => row.key !== key));
  }

  function selectFund(key: string, fund: SecFund) {
    commit(rows.map((row) => (row.key === key ? { ...row, projId: fund.proj_id, query: fund.display_name } : row)));
  }

  function setQuery(key: string, query: string) {
    commit(rows.map((row) => (row.key === key ? { ...row, projId: "", query } : row)));
  }

  function setWeight(key: string, weight: number) {
    commit(rows.map((row) => (row.key === key ? { ...row, weight } : row)));
  }

  function setWeights(updates: Map<string, number>) {
    commit(rows.map((row) => (updates.has(row.key) ? { ...row, weight: updates.get(row.key)! } : row)));
  }

  // Equal weight / normalize / clear are the standard bulk-allocation actions
  // in professional portfolio backtesters (Portfolio Visualizer, testfol.io)
  // -- without them, summing to exactly 100% is manual arithmetic on every edit.
  function equalWeightAll() {
    if (!rows.length) return;
    const share = Math.round((100 / rows.length) * 10) / 10;
    const remainder = Math.round((100 - share * (rows.length - 1)) * 10) / 10;
    commit(rows.map((row, index) => ({ ...row, weight: index === rows.length - 1 ? remainder : share })));
  }

  function normalizeWeights() {
    const currentTotal = rows.reduce((sum, row) => sum + (row.weight || 0), 0);
    if (currentTotal <= 0) {
      equalWeightAll();
      return;
    }
    const scaled = rows.map((row) => (row.weight || 0) * (100 / currentTotal));
    // Round to 1dp but correct the last row so the sum is exactly 100 -- naive
    // per-row rounding alone can drift to 99.9%/100.1% and fail the "ready" check.
    const rounded = scaled.map((weight) => Math.round(weight * 10) / 10);
    const roundedTotal = rounded.reduce((sum, weight) => sum + weight, 0);
    const drift = Math.round((100 - roundedTotal) * 10) / 10;
    if (rounded.length) rounded[rounded.length - 1] = Math.round((rounded[rounded.length - 1] + drift) * 10) / 10;
    commit(rows.map((row, index) => ({ ...row, weight: rounded[index] })));
  }

  function clearWeights() {
    commit(rows.map((row) => ({ ...row, weight: 0 })));
  }

  function loadExample() {
    if (funds.length < 2) return;
    seedRows(funds.slice(0, 2).map((fund, index) => ({ fund, weight: index === 0 ? 60 : 40 })));
  }

  const committedRows = rows.filter((row) => row.projId);
  const total = rows.reduce((sum, row) => sum + (row.weight || 0), 0);
  const allNamed = rows.every((row) => row.projId || row.query.trim() !== "");
  const complete = allNamed && Math.abs(total - 100) < 0.05 && committedRows.length > 0;
  const selectedIds = new Set(rows.map((row) => row.projId));

  function handlePageKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Enter" || event.defaultPrevented || !complete) return;
    // A row's own combobox already handled Enter (calling preventDefault) if
    // it was selecting a highlighted suggestion -- only reaching here means
    // no combobox intercepted it, so it's safe to treat as "submit".
    onContinue();
  }

  return (
    <div className={active ? "page active" : "page"} onKeyDown={handlePageKeyDown}>
      <div className="page-head">
        <h1>Build your portfolio</h1>
        <p>Search SEC-registered mutual funds by name or class, set target weights, and confirm they sum to 100% before setting your assumptions.</p>
      </div>

      <div className="card">
        <div className="example-row">
          <span className="footnote" style={{ margin: 0 }}>First time here?</span>
          <button className="link-btn" onClick={loadExample} type="button">Load an example portfolio</button>
        </div>

        <div className="holdings-table">
          <div className="holdings-head">
            <div>SEC Fund</div>
            <div>Weight %</div>
            <div />
          </div>
          {rows.map((row) => (
            <HoldingsRow
              key={row.key}
              row={row}
              funds={filteredFunds}
              allFunds={funds}
              selectedIds={selectedIds}
              canRemove={rows.length > 1}
              amcFacets={amcFacets}
              categoryFacets={categoryFacets}
              amcFilter={amcFilter}
              categoryFilter={categoryFilter}
              onToggleAmc={(value) => toggleFilter(setAmcFilter, value)}
              onToggleCategory={(value) => toggleFilter(setCategoryFilter, value)}
              onClearFilters={clearAllFilters}
              onSelect={(fund) => selectFund(row.key, fund)}
              onQueryChange={(query) => setQuery(row.key, query)}
              onWeightChange={(weight) => setWeight(row.key, weight)}
              onRemove={() => removeRow(row.key)}
            />
          ))}
        </div>

        <div className="holdings-foot">
          <div className="holdings-foot-left">
            <button className="add-asset" onClick={addRow} type="button">+ Add fund</button>
            <div className="weight-actions">
              <button className="link-btn" onClick={equalWeightAll} type="button">Equal weight</button>
              <span aria-hidden="true">&middot;</span>
              <button className="link-btn" onClick={normalizeWeights} type="button">Normalize to 100%</button>
              <span aria-hidden="true">&middot;</span>
              <button className="link-btn" onClick={clearWeights} type="button">Clear</button>
            </div>
          </div>
          <div className="weight-total">
            Total <span>{formatPct(total)}</span>
            <span className={complete ? "pill ok" : "pill warn"}>{complete ? "ready" : "incomplete"}</span>
          </div>
        </div>

        {complete ? <AllocationDonut fundsById={fundsById} onWeightsChange={setWeights} rows={committedRows} /> : null}
      </div>

      <div className="actions">
        <span className="footnote">Step 1 of 3 &mdash; portfolio weights must sum to 100%.</span>
        <button className="btn btn-primary" disabled={!complete} onClick={onContinue} type="button">Continue to Assumptions &rarr;</button>
      </div>
    </div>
  );
}

function HoldingsRow({
  row,
  funds,
  allFunds,
  selectedIds,
  canRemove,
  amcFacets,
  categoryFacets,
  amcFilter,
  categoryFilter,
  onToggleAmc,
  onToggleCategory,
  onClearFilters,
  onSelect,
  onQueryChange,
  onWeightChange,
  onRemove
}: {
  row: Row;
  funds: SecFund[];
  allFunds: SecFund[];
  selectedIds: Set<string>;
  canRemove: boolean;
  amcFacets: Facet[];
  categoryFacets: Facet[];
  amcFilter: Set<string>;
  categoryFilter: Set<string>;
  onToggleAmc: (value: string) => void;
  onToggleCategory: (value: string) => void;
  onClearFilters: () => void;
  onSelect: (fund: SecFund) => void;
  onQueryChange: (query: string) => void;
  onWeightChange: (weight: number) => void;
  onRemove: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const activeFilterCount = amcFilter.size + categoryFilter.size;
  const inputRef = useRef<HTMLInputElement | null>(null);
  const fieldRef = useRef<HTMLDivElement | null>(null);
  const fund = allFunds.find((item) => item.proj_id === row.projId);
  const displayValue = fund ? fund.display_name : row.query;

  const query = row.projId ? "" : row.query.trim().toLowerCase();
  const options = funds.filter((item) => {
    if (selectedIds.has(item.proj_id) && item.proj_id !== row.projId) return false;
    if (!query) return true;
    const haystack = `${item.proj_id} ${item.display_name} ${item.fund_class_name} ${item.search_term} ${item.amc_name_en} ${item.policy_desc}`.toLowerCase();
    return haystack.includes(query);
  });
  // Show every match, not just the first few -- the dropdown already has a
  // fixed max-height with overflow-y: auto (see .fund-suggest in styles.css),
  // so with 800+ funds in the universe a hard cap here would silently hide
  // matches the user has no way to scroll to.
  const visibleOptions = options;
  const listboxId = `${row.key}-listbox`;
  const optionId = (index: number) => `${row.key}-option-${index}`;

  useEffect(() => {
    if (!open) return;
    document.getElementById(optionId(highlight))?.scrollIntoView({ block: "nearest" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlight, open]);

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!open) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((current) => Math.min(visibleOptions.length - 1, current + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((current) => Math.max(0, current - 1));
    } else if (event.key === "Enter" && visibleOptions[highlight]) {
      event.preventDefault();
      onSelect(visibleOptions[highlight]);
      setOpen(false);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  function handleBlur(event: FocusEvent<HTMLDivElement>) {
    const next = event.relatedTarget as Node | null;
    if (next && fieldRef.current?.contains(next)) return;
    setOpen(false);
  }

  return (
    <div className="holdings-row">
      <div className="fund-field" onBlur={handleBlur} ref={fieldRef}>
        <input
          aria-activedescendant={open && visibleOptions[highlight] ? optionId(highlight) : undefined}
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-expanded={open}
          aria-label="Search SEC fund by name, class, or proj_id"
          className="field fund-input"
          ref={inputRef}
          role="combobox"
          value={displayValue}
          placeholder="Search fund name, class, or proj_id..."
          onFocus={() => { setOpen(true); setHighlight(0); }}
          onChange={(event) => { onQueryChange(event.target.value); setOpen(true); setHighlight(0); }}
          onKeyDown={handleKeyDown}
          autoComplete="off"
        />
        {fund && formatCoverage(fund) ? <p className="fund-coverage-hint">{formatCoverage(fund)}</p> : null}
        <div className={open ? "fund-suggest open" : "fund-suggest"}>
          {amcFacets.length || categoryFacets.length ? (
            <div className="fund-suggest-filters">
              <button
                className="fund-suggest-filter-toggle"
                onClick={() => setFiltersOpen((current) => !current)}
                onMouseDown={(event) => event.preventDefault()}
                type="button"
              >
                <SlidersHorizontal size={12} />
                Filters{activeFilterCount ? ` (${activeFilterCount})` : ""}
                <ChevronDown className={filtersOpen ? "chev open" : "chev"} size={12} />
              </button>
              {filtersOpen ? (
                <div className="fund-suggest-filter-body">
                  {activeFilterCount ? (
                    <button className="filter-clear-all" onClick={onClearFilters} onMouseDown={(event) => event.preventDefault()} type="button">
                      Clear all filters
                    </button>
                  ) : null}
                  {amcFacets.length ? (
                    <FacetGroup label="AMC" facets={amcFacets} selected={amcFilter} onToggle={onToggleAmc} />
                  ) : null}
                  {categoryFacets.length ? (
                    <FacetGroup facets={categoryFacets} formatLabel={categoryLabel} label="Fund category" onToggle={onToggleCategory} selected={categoryFilter} />
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
          <div aria-label="Fund suggestions" id={listboxId} role="listbox">
            {visibleOptions.map((item, index) => (
              <button
                aria-selected={index === highlight}
                className={index === highlight ? "highlighted" : ""}
                id={optionId(index)}
                key={`${item.proj_id}-${item.fund_class_name}`}
                onMouseDown={(event) => { event.preventDefault(); onSelect(item); setOpen(false); }}
                role="option"
                type="button"
              >
                {item.display_name}
                <span className="fid">{item.proj_id} &middot; {item.fund_class_name}</span>
                {formatCoverage(item) ? <span className="coverage">{formatCoverage(item)}</span> : null}
              </button>
            ))}
            {!options.length ? <button disabled type="button">No matching funds</button> : null}
          </div>
        </div>
      </div>
      <input
        className="field num weight-input"
        type="number"
        min={0}
        max={100}
        value={row.weight}
        onChange={(event) => onWeightChange(Number(event.target.value))}
      />
      <button aria-label="Remove fund row" className="icon-btn remove-row" disabled={!canRemove} onClick={onRemove} type="button">
        <X size={15} />
      </button>
    </div>
  );
}

function FacetGroup({
  label,
  facets,
  selected,
  onToggle,
  formatLabel = (value: string) => value
}: {
  label: string;
  facets: Facet[];
  selected: Set<string>;
  onToggle: (value: string) => void;
  formatLabel?: (value: string) => string;
}) {
  const [query, setQuery] = useState("");
  const visible = query.trim()
    ? facets.filter((facet) => formatLabel(facet.value).toLowerCase().includes(query.trim().toLowerCase()))
    : facets;
  const showSearch = facets.length > 6;

  return (
    <div className="filter-mini-group">
      <div className="filter-mini-head">
        <span className="filter-mini-label">{label}</span>
        {selected.size ? <span className="filter-mini-count">{selected.size} selected</span> : null}
      </div>
      {showSearch ? (
        <div className="filter-mini-search">
          <Search size={11} />
          <input
            onChange={(event) => setQuery(event.target.value)}
            onMouseDown={(event) => event.stopPropagation()}
            placeholder={`Search ${label.toLowerCase()}...`}
            value={query}
          />
        </div>
      ) : null}
      <div className="filter-checklist">
        {visible.map((facet) => (
          <label className="filter-check-row" key={facet.value}>
            <input
              checked={selected.has(facet.value)}
              onChange={() => onToggle(facet.value)}
              onMouseDown={(event) => event.stopPropagation()}
              type="checkbox"
            />
            <span className="filter-check-label">{formatLabel(facet.value)}</span>
            <span className="filter-check-count">{facet.count}</span>
          </label>
        ))}
        {!visible.length ? <p className="filter-check-empty">No matches</p> : null}
      </div>
    </div>
  );
}

const MIN_SLICE_WEIGHT = 1;

function AllocationDonut({
  rows,
  fundsById,
  onWeightsChange
}: {
  rows: Row[];
  fundsById: Map<string, SecFund>;
  onWeightsChange: (updates: Map<string, number>) => void;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [dragBoundary, setDragBoundary] = useState<number | null>(null);
  const total = rows.reduce((sum, row) => sum + (row.weight || 0), 0) || 1;
  const cx = 60;
  const cy = 60;
  const r = 50;
  const inner = 30;
  const n = rows.length;

  let angle = -90;
  const arcs = rows.map((row, index) => {
    const share = (row.weight || 0) / total;
    const sweep = share * 360;
    const startAngle = angle;
    const x1 = cx + r * Math.cos((startAngle * Math.PI) / 180);
    const y1 = cy + r * Math.sin((startAngle * Math.PI) / 180);
    const endAngle = startAngle + sweep;
    const x2 = cx + r * Math.cos((endAngle * Math.PI) / 180);
    const y2 = cy + r * Math.sin((endAngle * Math.PI) / 180);
    const large = sweep > 180 ? 1 : 0;
    const color = PALETTE[index % PALETTE.length];
    const d = `M${cx},${cy} L${x1.toFixed(2)},${y1.toFixed(2)} A${r},${r} 0 ${large} 1 ${x2.toFixed(2)},${y2.toFixed(2)} Z`;
    angle = endAngle;
    return { d, color, startAngle, endAngle, key: row.key, label: fundsById.get(row.projId)?.display_name ?? row.projId, weight: row.weight };
  });

  // A boundary sits between arc[i] and arc[(i+1)%n] -- dragging it moves
  // weight between exactly those two slices, matching M1 Finance's Pie
  // editor (drag a slice edge, everything else stays put).
  const boundaries = arcs.map((arc, index) => {
    const next = arcs[(index + 1) % n];
    const bx = cx + r * Math.cos((arc.endAngle * Math.PI) / 180);
    const by = cy + r * Math.sin((arc.endAngle * Math.PI) / 180);
    return { angle: arc.endAngle, x: bx, y: by, leftIndex: index, rightIndex: (index + 1) % n, minAngle: arc.startAngle, maxAngle: next.endAngle };
  });

  function angleFromPointer(clientX: number, clientY: number, referenceAngle: number): number {
    const svg = svgRef.current;
    if (!svg) return referenceAngle;
    const rect = svg.getBoundingClientRect();
    // viewBox is 0 0 120 120 rendered at 120x120, so client px map 1:1 to
    // svg units once offset by the element's own on-screen position.
    const x = ((clientX - rect.left) / rect.width) * 120 - cx;
    const y = ((clientY - rect.top) / rect.height) * 120 - cy;
    let raw = (Math.atan2(y, x) * 180) / Math.PI;
    // Normalize into the same continuous [-90, 270) space the arcs use, so
    // a boundary near the top (the -90/270 wrap point) doesn't jump.
    while (raw < referenceAngle - 180) raw += 360;
    while (raw > referenceAngle + 180) raw -= 360;
    return raw;
  }

  function applyBoundaryDrag(boundaryIndex: number, clientX: number, clientY: number) {
    const boundary = boundaries[boundaryIndex];
    const left = arcs[boundary.leftIndex];
    const right = arcs[boundary.rightIndex];
    const minSweep = (MIN_SLICE_WEIGHT / total) * 360;
    const minAngle = boundary.minAngle + minSweep;
    const maxAngle = boundary.maxAngle - minSweep;
    if (minAngle >= maxAngle) return;
    const pointerAngle = angleFromPointer(clientX, clientY, boundary.angle);
    const clamped = Math.min(maxAngle, Math.max(minAngle, pointerAngle));
    const leftWeight = Math.round(((clamped - boundary.minAngle) / 360) * total * 10) / 10;
    const rightWeight = Math.round(((boundary.maxAngle - clamped) / 360) * total * 10) / 10;
    onWeightsChange(new Map([[left.key, leftWeight], [right.key, rightWeight]]));
  }

  useEffect(() => {
    if (dragBoundary === null) return;
    function handleMove(event: PointerEvent) {
      applyBoundaryDrag(dragBoundary!, event.clientX, event.clientY);
    }
    function handleUp() {
      setDragBoundary(null);
    }
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dragBoundary, rows, total]);

  const canDrag = n > 1;

  return (
    <div id="allocationBlock">
      <div className="donut-wrap">
        <svg height="120" ref={svgRef} viewBox="0 0 120 120" width="120" role="img" aria-label="Allocation donut chart. Drag a slice edge to rebalance between two funds.">
          {arcs.map((arc) => <path d={arc.d} fill={arc.color} key={arc.key} />)}
          <circle cx={cx} cy={cy} fill="var(--surface)" r={inner} />
          {canDrag
            ? boundaries.map((boundary) => (
                <circle
                  className={dragBoundary === boundary.leftIndex ? "donut-handle dragging" : "donut-handle"}
                  cx={boundary.x}
                  cy={boundary.y}
                  key={boundary.leftIndex}
                  onPointerDown={(event) => {
                    event.preventDefault();
                    (event.target as Element).setPointerCapture?.(event.pointerId);
                    setDragBoundary(boundary.leftIndex);
                  }}
                  r={5}
                  tabIndex={0}
                  role="slider"
                  aria-label={`Boundary between ${arcs[boundary.leftIndex].label} and ${arcs[boundary.rightIndex].label}`}
                  aria-valuenow={arcs[boundary.leftIndex].weight}
                  aria-valuemin={MIN_SLICE_WEIGHT}
                  aria-valuemax={100 - MIN_SLICE_WEIGHT}
                  onKeyDown={(event) => {
                    // Keyboard equivalent of the drag, for anyone who can't
                    // (or doesn't want to) use a pointer -- 1% per press.
                    const step = event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : 0;
                    if (!step) return;
                    event.preventDefault();
                    const stepAngle = (step / total) * 360;
                    const minSweep = (MIN_SLICE_WEIGHT / total) * 360;
                    const clamped = Math.min(boundary.maxAngle - minSweep, Math.max(boundary.minAngle + minSweep, boundary.angle + stepAngle));
                    const leftWeight = Math.round(((clamped - boundary.minAngle) / 360) * total * 10) / 10;
                    const rightWeight = Math.round(((boundary.maxAngle - clamped) / 360) * total * 10) / 10;
                    onWeightsChange(new Map([[arcs[boundary.leftIndex].key, leftWeight], [arcs[boundary.rightIndex].key, rightWeight]]));
                  }}
                />
              ))
            : null}
        </svg>
        <div className="legend">
          {arcs.map((arc) => (
            <div className="row" key={arc.key}>
              <span className="swatch" style={{ background: arc.color }} />
              {arc.label} &mdash; {formatPct(arc.weight)}
            </div>
          ))}
        </div>
      </div>
      {canDrag ? <p className="footnote donut-hint">Drag a dot on the chart to shift weight between two neighboring funds.</p> : null}
    </div>
  );
}

function formatPct(value: number) {
  return `${Math.round(value * 10) / 10}%`;
}
