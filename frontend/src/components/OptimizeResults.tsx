import { AlertTriangle, BarChart3, Download } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { SecFund } from "../types/backtest";
import type { OptimizeRequest, OptimizeResult } from "../types/optimize";
import { OBJECTIVES } from "./OptimizeAssumptionsStep";

interface Props {
  result: OptimizeResult | null;
  funds: SecFund[]; // selected shortlist, for display-name lookups
  compareLabel: string | null;
  request?: OptimizeRequest; // for the Report tab's run_config.json export
}

type ResultTab = "Summary" | "Frontier" | "Weights" | "Performance" | "Rolling" | "Report";
const TABS: ResultTab[] = ["Summary", "Frontier", "Weights", "Performance", "Rolling", "Report"];

const pct = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
// Several backend fields are legitimately null (a realized metric that is
// undefined for this request -- no complete calendar year in the window, a
// zero-downside series). Passing null straight into pct.format() renders a
// fabricated "0%", so every nullable field goes through these instead.
const fmtPct = (value: number | null | undefined) => (value === null || value === undefined ? "N/A" : `${pct.format(value)}%`);
const fmtNum = (value: number | null | undefined) => (value === null || value === undefined ? "N/A" : String(value));
// Same palette PortfolioStep's AllocationDonut uses, so a fund reads as
// the same color across the Portfolio step and these Results charts.
const PALETTE = ["#5b21d6", "#34383e", "#92620a", "#9aa1ac", "#7c4ded"];

export function OptimizeResults({ result, funds, compareLabel, request }: Props) {
  const [activeTab, setActiveTab] = useState<ResultTab>("Summary");
  const nameOf = (projId: string) => funds.find((f) => f.proj_id === projId)?.display_name ?? projId;
  // compareLabel reflects Constraints' "Compared Allocation" *setting*, not
  // whether a comparison actually got computed -- "Your Current Portfolio"
  // resolves to null server-side when the shortlist has no current (Step 1)
  // weights entered, since there's nothing to compare against.
  // Every place that surfaces compareLabel below (Summary narrative +
  // checklist + footnote, Weights header, Report's Objective section) must
  // agree with whether result.compareWeights is actually present -- using
  // the raw setting alone previously claimed "Compared against Your
  // Current Portfolio" even when no comparison data existed anywhere on
  // the page.
  const effectiveCompareLabel = result?.compareWeights ? compareLabel : null;

  if (!result) {
    return (
      <section className="resultShell emptyResult">
        <span className="emptyResultIcon"><BarChart3 size={22} /></span>
        <h2>Run an optimization to see results.</h2>
        <p>Select funds, set an objective, then run to see the efficient frontier, optimal weights, and a rolling out-of-sample check.</p>
      </section>
    );
  }

  if (result.feasibility !== "ok") {
    return (
      <section className="resultShell emptyResult">
        <span className="emptyResultIcon"><AlertTriangle size={22} /></span>
        <h2>{feasibilityTitle(result.feasibility)}</h2>
        <p>{result.feasibilityMessage}</p>
      </section>
    );
  }

  return (
    <section className="resultShell" id="optimize-output">
      <div className="resultHeader">
        <div>
          <span className="sourceLine">Optimization result</span>
          <h2>{request ? OBJECTIVES.find((o) => o.id === request.goal)?.title ?? "Optimization" : "Optimization"} &middot; {funds.length} funds</h2>
        </div>
        <button className="secondaryButton" onClick={() => downloadText("optimization-result.json", JSON.stringify(result, null, 2), "application/json")} type="button">
          <Download size={16} /> Result JSON
        </button>
      </div>

      <nav aria-label="Optimization output tabs" className="resultTabs">
        {TABS.map((tab) => (
          <button className={activeTab === tab ? "resultTab active" : "resultTab"} key={tab} onClick={() => setActiveTab(tab)} type="button">
            {tab}
          </button>
        ))}
      </nav>

      {activeTab === "Summary" ? <SummaryTab compareLabel={effectiveCompareLabel} nameOf={nameOf} request={request} result={result} setActiveTab={setActiveTab} /> : null}
      {activeTab === "Frontier" ? <FrontierTab nameOf={nameOf} result={result} /> : null}
      {activeTab === "Weights" ? <WeightsTab compareLabel={effectiveCompareLabel} nameOf={nameOf} result={result} /> : null}
      {activeTab === "Performance" ? <PerformanceTab result={result} /> : null}
      {activeTab === "Rolling" ? <RollingTab result={result} /> : null}
      {activeTab === "Report" ? <ReportTab compareLabel={effectiveCompareLabel} nameOf={nameOf} request={request} result={result} /> : null}
    </section>
  );
}

// Every SVG chart in this file previously had axis TITLES ("Growth of
// 100", "Volatility (%)") but zero numeric tick VALUES anywhere -- a user
// could see a line move but never read what value it was at, on any
// chart in the app. Shared tick helpers fix that consistently everywhere
// instead of one-off text elements per chart.
function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) return [min];
  const ticks: number[] = [];
  for (let i = 0; i <= count; i++) ticks.push(min + ((max - min) * i) / count);
  return ticks;
}

function YAxisTicks({ min, max, padding, width, height, y, format }: {
  min: number; max: number; padding: number; width: number; height: number;
  y: (v: number) => number; format: (v: number) => string;
}) {
  return (
    <>
      {niceTicks(min, max).map((v, i) => (
        <g key={i}>
          {i > 0 ? <line className="gridLine" opacity={0.4} x1={padding} x2={width - padding} y1={y(v)} y2={y(v)} /> : null}
          <text className="axisText" fontSize={10} textAnchor="end" x={padding - 6} y={y(v) + 3}>{format(v)}</text>
        </g>
      ))}
      <line className="gridLine" opacity={0.4} x1={padding} x2={width - padding} y1={y(max)} y2={y(max)} />
    </>
  );
}

function XAxisTicks({ labels, padding, width, y }: { labels: string[]; padding: number; width: number; y: number }) {
  if (labels.length < 2) return null;
  return (
    <>
      {labels.map((label, i) => (
        <text className="axisText" fontSize={10} key={i} textAnchor={i === 0 ? "start" : i === labels.length - 1 ? "end" : "middle"} x={padding + (i / (labels.length - 1)) * (width - padding * 2)} y={y}>
          {label}
        </text>
      ))}
    </>
  );
}

function downloadText(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

// Simple cumulative-growth line chart -- same visual idiom as the other
// SVG charts in this file (axisChart/gridLine), not the sibling
// backtester's more elaborate hover-tooltip AxisCurve. Turns a return
// series into an indexed growth path starting at 100.
function EquityCurveChart({ title, series }: { title: string; series: { label: string; returnsPct: number[]; color: string }[] }) {
  const width = 640;
  const height = 240;
  const padding = 40;
  const paths = series.map((s) => {
    let value = 100;
    const points = [value, ...s.returnsPct.map((r) => (value *= 1 + r / 100))];
    return { ...s, points };
  });
  const allValues = paths.flatMap((p) => p.points);
  if (!allValues.length) return null;
  const minV = Math.min(...allValues);
  const maxV = Math.max(...allValues);
  const n = paths[0]?.points.length ?? 1;
  const x = (i: number) => padding + (i / Math.max(n - 1, 1)) * (width - padding * 2);
  const y = (v: number) => height - padding - ((v - minV) / (maxV - minV || 1)) * (height - padding * 2);

  return (
    <section className="chartPanel">
      <h3>{title}</h3>
      <div className="chartCanvas">
        <svg className="axisChart" viewBox={`0 0 ${width} ${height}`}>
          <line className="gridLine" x1={padding} x2={width - padding} y1={height - padding} y2={height - padding} />
          <line className="gridLine" x1={padding} x2={padding} y1={padding} y2={height - padding} />
          <YAxisTicks format={(v) => v.toFixed(0)} height={height} max={maxV} min={minV} padding={padding} width={width} y={y} />
          <XAxisTicks labels={n > 1 ? ["1", String(n)] : ["1"]} padding={padding} width={width} y={height - padding + 14} />
          {paths.map((p) => (
            <path
              d={p.points.map((v, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(v)}`).join(" ")}
              fill="none"
              key={p.label}
              stroke={p.color}
              strokeWidth={2}
            />
          ))}
          <text className="axisText" x={width / 2} y={height - 6}>Period</text>
          <text className="axisText" transform={`translate(12, ${height / 2}) rotate(-90)`}>Growth of 100</text>
        </svg>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 8 }}>
        {paths.map((p) => (
          <div key={p.label} style={{ alignItems: "center", display: "flex", fontSize: 12.5, gap: 6 }}>
            <span style={{ background: p.color, borderRadius: 2, display: "inline-block", height: 10, width: 10 }} />
            {p.label} &mdash; ends at {p.points[p.points.length - 1].toFixed(1)}
          </div>
        ))}
      </div>
    </section>
  );
}

// Underwater curve -- the sibling backtester ships a full dedicated
// Drawdown tab; this project had no visual representation of drawdown at
// all despite CDaR (Conditional Drawdown-at-Risk) being a selectable risk
// measure. Same growth-of-100 math as EquityCurveChart, then tracks the
// running peak and plots (value - peak) / peak as a filled area below 0.
function DrawdownChart({ returnsPct }: { returnsPct: number[] }) {
  if (!returnsPct.length) return null;
  const width = 640;
  const height = 200;
  const padding = 40;
  let value = 100;
  let peak = 100;
  const drawdowns = returnsPct.map((r) => {
    value *= 1 + r / 100;
    peak = Math.max(peak, value);
    return ((value - peak) / peak) * 100;
  });
  const minDd = Math.min(...drawdowns, 0);
  const n = drawdowns.length;
  const x = (i: number) => padding + (i / Math.max(n - 1, 1)) * (width - padding * 2);
  const yZero = padding + 4;
  const yBottom = height - padding;
  const y = (dd: number) => (minDd === 0 ? yZero : yZero + (dd / minDd) * (yBottom - yZero));
  const areaPath = `M ${x(0)} ${yZero} ${drawdowns.map((dd, i) => `L ${x(i)} ${y(dd)}`).join(" ")} L ${x(n - 1)} ${yZero} Z`;
  const linePath = drawdowns.map((dd, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(dd)}`).join(" ");
  const maxDrawdown = minDd;

  return (
    <section className="chartPanel">
      <h3>Drawdown</h3>
      <div className="chartCanvas">
        <svg className="axisChart" viewBox={`0 0 ${width} ${height}`}>
          <line className="gridLine" x1={padding} x2={width - padding} y1={yZero} y2={yZero} />
          <line className="gridLine" x1={padding} x2={padding} y1={padding} y2={yBottom} />
          <YAxisTicks format={(v) => `${v.toFixed(0)}%`} height={height} max={0} min={minDd} padding={padding} width={width} y={y} />
          <XAxisTicks labels={n > 1 ? ["1", String(n)] : ["1"]} padding={padding} width={width} y={yBottom + 14} />
          <path d={areaPath} fill="var(--danger)" fillOpacity={0.18} stroke="none" />
          <path d={linePath} fill="none" stroke="var(--danger)" strokeWidth={2} />
          <text className="axisText" x={width / 2} y={height - 6}>Period</text>
          <text className="axisText" transform={`translate(12, ${height / 2}) rotate(-90)`}>Drawdown (%)</text>
        </svg>
      </div>
      <p className="field-hint">Max drawdown over this series: {pct.format(maxDrawdown)}%.</p>
    </section>
  );
}

// PV shows a "possible range of expected annual portfolio returns" note at
// the top of every results page, framed against the efficient frontier's
// own endpoints -- gives immediate context for where the optimized
// portfolio sits within what's achievable at all from this shortlist,
// before the user reads a single tab. Uses data already computed
// (result.frontier), no new math.
// Shared renderer for the backend's four optional caveat strings
// (robustNote, robustOptimizationNote, constraintNote, compareNote). Each
// is null whenever there's nothing to say, and rendering an empty badged
// box in that case is worse than rendering nothing -- so this returns null
// for a missing or blank note rather than making every caller repeat the
// guard.
function CaveatNote({ badge, note }: { badge: string; note: string | null }) {
  if (!note || !note.trim()) return null;
  return (
    <div className="notePanel">
      <span className="badge">{badge}</span>
      <p>{note}</p>
    </div>
  );
}

// robustNote's message is always exactly "Rolling validation: X of Y
// scheduled folds produced a result (...)." (backend/app/optimizer/rolling.py)
// -- as a wall of prose, the one number that actually matters (how much of
// the schedule is trustworthy) was easy to miss. Pull it out into a
// headline fraction + coverage bar, same track/fill styling as
// RiskContributionBars, and keep the full sentence underneath so nothing
// is lost -- just easier to scan.
function RollingValidationNote({ note }: { note: string | null }) {
  if (!note || !note.trim()) return null;
  const match = note.match(/(\d+) of (\d+) scheduled folds/);
  if (!match) return <CaveatNote badge="Rolling Validation" note={note} />;
  const scored = Number(match[1]);
  const scheduled = Number(match[2]);
  const coveragePct = scheduled > 0 ? (scored / scheduled) * 100 : 0;
  return (
    <div className="notePanel">
      <span className="badge">Rolling Validation</span>
      <div style={{ alignItems: "baseline", display: "flex", gap: 10, margin: "6px 0 8px" }}>
        <strong style={{ fontSize: 20 }}>{scored} / {scheduled} folds scored</strong>
        <span style={{ color: "var(--text-tertiary)", fontSize: 13 }}>({pct.format(coveragePct)}%)</span>
      </div>
      <div style={{ background: "var(--surface-2)", borderRadius: 4, height: 8, marginBottom: 10, width: "100%" }}>
        <div style={{ background: PALETTE[0], borderRadius: 4, height: "100%", width: `${coveragePct}%` }} />
      </div>
      <p className="field-hint">{note}</p>
    </div>
  );
}

function feasibilityTitle(status: OptimizeResult["feasibility"]): string {
  if (status === "non_convergence") return "The solver did not converge.";
  if (status === "infeasible_constraints") return "Constraints are mutually infeasible.";
  return "Not enough data to optimize.";
}

// Horizontal bar chart -- riskfolio-lib's own jupyter_report() visualizes
// risk contribution as a bar chart, not a bare table, with each fund's
// share of total portfolio risk easy to compare at a glance.
function RiskContributionBars({ riskContributionPct, nameOf }: { riskContributionPct: Record<string, number>; nameOf: (id: string) => string }) {
  const rows = Object.entries(riskContributionPct).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...rows.map(([, share]) => share), 1);
  const equalShare = 100 / (rows.length || 1);
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {rows.map(([projId, share], index) => (
        <div key={projId} style={{ display: "grid", gap: 4 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5 }}>
            <span>{nameOf(projId)}</span>
            <span>{pct.format(share)}%</span>
          </div>
          <div style={{ background: "var(--surface-2)", borderRadius: 4, height: 10, position: "relative", width: "100%" }}>
            <div style={{ background: PALETTE[index % PALETTE.length], borderRadius: 4, height: "100%", width: `${(share / max) * 100}%` }} />
            {/* Equal-risk-contribution reference line, matching riskfolio-lib's own report */}
            <div style={{ background: "var(--text-tertiary)", bottom: 0, left: `${(equalShare / max) * 100}%`, position: "absolute", top: 0, width: 1 }} />
          </div>
        </div>
      ))}
      <p className="field-hint">Vertical line marks equal risk contribution ({pct.format(equalShare)}% each).</p>
    </div>
  );
}

function SummaryTab({ result, nameOf, compareLabel, setActiveTab, request }: { result: OptimizeResult; nameOf: (id: string) => string; compareLabel: string | null; setActiveTab: (tab: ResultTab) => void; request?: OptimizeRequest }) {
  const topWeights = Object.entries(result.optimalWeights).sort((a, b) => b[1] - a[1]);
  const topFund = topWeights[0];
  const optimized = result.performanceSummary[0];
  const compared = result.performanceSummary[1];
  return (
    <div className="tabStack">
      {/* robustOptimizationNote is a separate concept from robustNote (the
          rolling out-of-sample validation caveat rendered below, next to
          Risk contribution) -- robustOptimizationNote is about the
          robustOptimization toggle specifically. */}
      <CaveatNote badge="Robust Optimization" note={result.robustOptimizationNote} />
      <div className="metricGrid">
        <ClickableMetric label="Expected return" onClick={() => setActiveTab("Performance")} sub="See Performance tab" value={`${pct.format(optimized?.expectedReturnPct ?? 0)}%`} />
        <ClickableMetric label="Volatility" onClick={() => setActiveTab("Performance")} sub="See Performance tab" value={`${pct.format(optimized?.stdDevPct ?? 0)}%`} />
        <ClickableMetric label="Sharpe (ex-ante)" onClick={() => setActiveTab("Performance")} sub="See Performance tab" value={`${optimized?.sharpeExAnte ?? 0}`} />
        <ClickableMetric label="Top holding" onClick={() => setActiveTab("Weights")} sub="See Weights tab" value={topFund ? nameOf(topFund[0]) : "-"} />
        {result.tradeList.length ? (
          <ClickableMetric label="Turnover to rebalance" onClick={() => setActiveTab("Weights")} sub="See Weights tab" value={`${pct.format(result.totalTurnoverPct)}%`} />
        ) : null}
        {result.benchmarkComparison ? (
          <ClickableMetric label="vs. Benchmark" onClick={() => setActiveTab("Performance")} sub="See Performance tab" value={`${result.benchmarkComparison.excessReturnPct >= 0 ? "+" : ""}${pct.format(result.benchmarkComparison.excessReturnPct)}%`} />
        ) : null}
      </div>
      <RollingValidationNote note={result.robustNote} />
      <section className="chartPanel">
        <h3>Risk contribution</h3>
        <RiskContributionBars nameOf={nameOf} riskContributionPct={result.riskContributionPct} />
      </section>
      <ResultChecklist compareLabel={compareLabel} request={request} result={result} />
      <CaveatNote badge="Constraints" note={result.constraintNote} />
      {result.bindingConstraints.length ? (
        <section className="tablePanel">
          <h3>What's actually constraining this result</h3>
          <p className="field-hint">Which limits the solver actually hit -- distinct from what's merely set in Assumptions. Loosening one of these would change the result; the rest are slack.</p>
          <div className="tableScroller">
            <table>
              <tbody>
                {result.bindingConstraints.map((b) => (
                  <tr key={b.label}><td><b>{b.label}</b></td><td>{b.detail}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
      {compareLabel ? (
        <p className="field-hint">Compared against <b>{compareLabel}</b> in the Weights and Performance tabs.</p>
      ) : null}
    </div>
  );
}

function ClickableMetric({ label, value, sub, onClick }: { label: string; value: string; sub: string; onClick: () => void }) {
  return (
    <button className="metricCard clickableMetric" onClick={onClick} type="button">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{sub}</small>
    </button>
  );
}

// Non-interactive counterpart to ClickableMetric -- for metrics with
// nowhere to jump to (there's no other tab a "positive folds" count would
// link into), a plain metricCard reads correctly; wrapping it in a
// <button> with a no-op onClick would falsely signal it's clickable.
function StaticMetric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="metricCard">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}

// Mirrors the sibling backtester's own Summary-tab "Result checklist" --
// a quick pass/fail scan of the run, not just headline numbers.
function ResultChecklist({ result, compareLabel, request }: { result: OptimizeResult; compareLabel: string | null; request?: OptimizeRequest }) {
  const weightSum = Object.values(result.optimalWeights).reduce((a, b) => a + b, 0);
  const items: { label: string; status: "ok" | "warn"; detail: string }[] = [
    {
      label: "Weights sum to 100%",
      status: Math.abs(weightSum - 100) < 0.5 ? "ok" : "warn",
      detail: `${pct.format(weightSum)}%`
    },
    { label: "Solver converged", status: "ok", detail: "feasible solution found" },
    {
      // Driven by the toggle the user actually set in Assumptions. It used
      // to be driven by result.robustNote's presence, which is a rolling
      // out-of-sample caveat and says nothing about robust optimization.
      label: "Robust optimization",
      status: "ok",
      detail: request?.robustOptimization ? "applied" : "not enabled"
    },
    {
      label: "Comparison allocation",
      status: "ok",
      detail: compareLabel ? `vs. ${compareLabel}` : "none selected"
    },
    {
      label: "Benchmark",
      status: "ok",
      detail: result.benchmarkComparison ? `set: ${result.benchmarkComparison.displayName}` : "none selected"
    }
  ];
  if (result.blackLitterman) {
    items.push({ label: "Black-Litterman views", status: "ok", detail: "equilibrium returns adjusted" });
  }
  const turnoverCap = request?.constraints.maxTurnoverPct ?? null;
  if (result.tradeList.length) {
    items.push({
      label: "Turnover within limit",
      status: turnoverCap === null || result.totalTurnoverPct <= turnoverCap ? "ok" : "warn",
      detail: turnoverCap === null ? `${pct.format(result.totalTurnoverPct)}%, no limit set` : `${pct.format(result.totalTurnoverPct)}% of ${turnoverCap}% max`
    });
  }
  return (
    <section className="tablePanel">
      <h3>Result checklist</h3>
      <div className="tableScroller">
        <table>
          <tbody>
            {items.map((item) => (
              <tr key={item.label}>
                <td>{item.label}</td>
                {/* "OK" on every row regardless of what it's actually saying
                    told the user nothing -- only render a pill for the
                    genuinely conditional "Check" case, where it actually
                    flags something worth looking at. */}
                <td>{item.status === "warn" ? <span className="pill warn">Check</span> : null}</td>
                <td>{item.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function FrontierTab({ result, nameOf }: { result: OptimizeResult; nameOf: (id: string) => string }) {
  const width = 640;
  const height = 320;
  const padding = 40;
  // With a small shortlist the global-minimum-variance point and the
  // max-Sharpe (tangency) point can legitimately coincide (the leftmost
  // frontier point is sometimes also the highest-Sharpe one) -- drawing
  // both as separate same-size circles at the same pixel position means
  // one silently covers the other, so the legend lists two markers but
  // only one is visible on the chart. Merge markers that land on (nearly)
  // the same point into a single combined marker instead.
  const rawMarkers = [result.optimalPoint, result.gmvPoint, result.tangencyPoint].filter((m): m is NonNullable<typeof m> => Boolean(m));
  const markers = rawMarkers.reduce<typeof rawMarkers>((merged, marker) => {
    const dup = merged.find((m) => Math.abs(m.volatilityPct - marker.volatilityPct) < 0.05 && Math.abs(m.expectedReturnPct - marker.expectedReturnPct) < 0.05);
    if (dup) {
      dup.label = `${dup.label} = ${marker.label}`;
      return merged;
    }
    return [...merged, { ...marker }];
  }, []);
  // PV's own frontier chart plots each individual asset at its own
  // (volatility, return) coordinate, not just the frontier curve and a
  // couple of named portfolios -- shows at a glance how much the
  // optimizer actually improved on any single holding. When the optimal
  // portfolio collapses to a single fund (e.g. a tight bound forces ~100%
  // into one holding), that asset's own point coincides with a marker;
  // drawing both means the larger marker circle silently hides the
  // smaller asset circle underneath it (same overlap bug as the merged
  // markers above), so skip the asset point in that case and fold its
  // name into the marker's own label instead.
  const rawAssetPoints = result.assetSummary.map((row) => ({ id: row.projId, volatilityPct: row.volatilityPct, expectedReturnPct: row.expectedReturnPct }));
  const assetPoints = rawAssetPoints.filter((a) => {
    const coincidesWithMarker = markers.find((m) => Math.abs(m.volatilityPct - a.volatilityPct) < 0.05 && Math.abs(m.expectedReturnPct - a.expectedReturnPct) < 0.05);
    if (coincidesWithMarker) {
      coincidesWithMarker.label = `${coincidesWithMarker.label} (${nameOf(a.id)})`;
      return false;
    }
    return true;
  });
  const vols = [...result.frontier.map((p) => p.volatilityPct), ...markers.map((m) => m.volatilityPct), ...assetPoints.map((a) => a.volatilityPct)];
  const rets = [...result.frontier.map((p) => p.expectedReturnPct), ...markers.map((m) => m.expectedReturnPct), ...assetPoints.map((a) => a.expectedReturnPct)];
  const minVol = Math.min(...vols);
  const maxVol = Math.max(...vols);
  const minRet = Math.min(...rets);
  const maxRet = Math.max(...rets);
  const x = (v: number) => padding + ((v - minVol) / (maxVol - minVol || 1)) * (width - padding * 2);
  const y = (r: number) => height - padding - ((r - minRet) / (maxRet - minRet || 1)) * (height - padding * 2);
  const path = result.frontier.map((p, i) => `${i === 0 ? "M" : "L"} ${x(p.volatilityPct)} ${y(p.expectedReturnPct)}`).join(" ");
  const markerColors: Record<string, string> = {
    "Your optimal portfolio": "#5b21d6",
    "Global minimum variance": "#0ea5e9",
    "Max Sharpe (tangency)": "#92620a"
  };
  // Merged labels ("A = B") won't exact-match markerColors -- fall back to
  // whichever known marker name the merged label contains, keeping a
  // consistent, recognizable color instead of the generic var(--text).
  function colorForMarker(label: string): string {
    if (markerColors[label]) return markerColors[label];
    const match = Object.keys(markerColors).find((key) => label.includes(key));
    return match ? markerColors[match] : "var(--text)";
  }

  return (
    <div className="tabStack">
      <section className="chartPanel">
        <h3>Efficient frontier</h3>
        <div className="chartCanvas">
          <svg className="axisChart" viewBox={`0 0 ${width} ${height}`}>
            <line className="gridLine" x1={padding} x2={width - padding} y1={height - padding} y2={height - padding} />
            <line className="gridLine" x1={padding} x2={padding} y1={padding} y2={height - padding} />
            <YAxisTicks format={(v) => `${v.toFixed(1)}%`} height={height} max={maxRet} min={minRet} padding={padding} width={width} y={y} />
            <XAxisTicks labels={[`${minVol.toFixed(1)}%`, `${maxVol.toFixed(1)}%`]} padding={padding} width={width} y={height - padding + 14} />
            <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} />
            {assetPoints.map((a, index) => (
              <g key={a.id}>
                <circle cx={x(a.volatilityPct)} cy={y(a.expectedReturnPct)} fill={PALETTE[index % PALETTE.length]} r={4} stroke="var(--bg)" strokeWidth={1.5} />
                <text className="axisText" fontSize={10} paintOrder="stroke" stroke="var(--bg)" strokeWidth={3} textAnchor="middle" x={x(a.volatilityPct)} y={y(a.expectedReturnPct) - 8}>{nameOf(a.id)}</text>
              </g>
            ))}
            {markers.map((m) => (
              <circle cx={x(m.volatilityPct)} cy={y(m.expectedReturnPct)} fill={colorForMarker(m.label)} key={m.label} r={5} stroke="var(--bg)" strokeWidth={2} />
            ))}
            <text className="axisText" x={width / 2} y={height - 6}>Volatility (%)</text>
            <text className="axisText" transform={`translate(12, ${height / 2}) rotate(-90)`}>Expected return (%)</text>
          </svg>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 8 }}>
          {markers.map((m) => (
            <div key={m.label} style={{ alignItems: "center", display: "flex", fontSize: 12.5, gap: 6 }}>
              <span style={{ background: colorForMarker(m.label), borderRadius: "50%", display: "inline-block", height: 10, width: 10 }} />
              {m.label} ({pct.format(m.volatilityPct)}% vol, {pct.format(m.expectedReturnPct)}% return)
            </div>
          ))}
          {assetPoints.map((a, index) => (
            <div key={a.id} style={{ alignItems: "center", display: "flex", fontSize: 12.5, gap: 6 }}>
              <span style={{ background: PALETTE[index % PALETTE.length], borderRadius: "50%", display: "inline-block", height: 8, width: 8 }} />
              {nameOf(a.id)} (individual holding)
            </div>
          ))}
        </div>
        <p className="field-hint">Frontier points come from riskfolio-lib's efficient-frontier solve over the selected time period.</p>
      </section>
      <TransitionMap nameOf={nameOf} result={result} />
      <section className="tablePanel">
        <h3>Asset summary</h3>
        <div className="tableScroller">
          <table>
            <thead><tr><th>Fund</th><th>Expected return</th><th>Volatility</th><th>Sharpe</th><th>Min-Max weight</th></tr></thead>
            <tbody>
              {result.assetSummary.map((row) => (
                <tr key={row.projId}>
                  <td>{nameOf(row.projId)}</td>
                  <td>{pct.format(row.expectedReturnPct)}%</td>
                  <td>{pct.format(row.volatilityPct)}%</td>
                  <td>{row.sharpe}</td>
                  <td>{row.minWeightPct}% &ndash; {row.maxWeightPct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="tablePanel">
        <h3>Asset correlations</h3>
        <div className="tableScroller">
          <table>
            <thead><tr><th>Fund A</th><th>Fund B</th><th>Correlation</th></tr></thead>
            <tbody>
              {result.correlations.map((row) => (
                <tr key={`${row.projId1}-${row.projId2}`}>
                  <td>{nameOf(row.projId1)}</td><td>{nameOf(row.projId2)}</td><td>{row.correlation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="chartPanel">
        <h3>Correlation matrix</h3>
        <p className="field-hint">Same pairwise correlations as the table above, laid out as a grid so clusters of highly correlated funds -- the ones giving the least diversification benefit -- are visible at a glance.</p>
        <CorrelationMatrix nameOf={nameOf} result={result} />
      </section>
      <section className="tablePanel compactTable">
        <h3>Efficient frontier points</h3>
        <div className="tableScroller">
          <table>
            <thead>
              <tr>
                <th>#</th><th>Volatility</th><th>Expected return</th><th>Sharpe</th>
                {result.assetSummary.map((row) => <th key={row.projId}>{nameOf(row.projId)}</th>)}
              </tr>
            </thead>
            <tbody>
              {result.frontier.map((point, index) => (
                <tr key={index}>
                  <td>{index + 1}</td>
                  <td>{pct.format(point.volatilityPct)}%</td>
                  <td>{pct.format(point.expectedReturnPct)}%</td>
                  <td>{point.sharpe}</td>
                  {result.assetSummary.map((row) => <td key={row.projId}>{pct.format(point.weights[row.projId] ?? 0)}%</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

// PV's own Efficient Frontier Transition Map: a stacked-area chart showing
// how each fund's weight shifts across the frontier (x-axis: frontier
// point / risk level), not just the endpoint allocation -- confirmed live
// this session, previously spec'd in docs/mock-ui-spec.md but not built.
function TransitionMap({ result, nameOf }: { result: OptimizeResult; nameOf: (id: string) => string }) {
  const width = 640;
  const height = 260;
  const padding = 40;
  const ids = result.assetSummary.map((row) => row.projId);
  const n = result.frontier.length;
  if (!n || !ids.length) return null;
  const stepX = (width - padding * 2) / Math.max(n - 1, 1);

  // Cumulative stack per point, in the same fund order every time so the
  // bands don't swap which fund is "on top" between points.
  const stacks = result.frontier.map((point) => {
    let running = 0;
    return ids.map((id) => {
      const w = point.weights[id] ?? 0;
      const from = running;
      running += w;
      return { id, from, to: running };
    });
  });

  function bandPath(fundIndex: number): string {
    const top = result.frontier.map((_, pointIndex) => {
      const x = padding + stepX * pointIndex;
      const y = height - padding - (stacks[pointIndex][fundIndex].to / 100) * (height - padding * 2);
      return `${x},${y}`;
    });
    const bottom = result.frontier.map((_, pointIndex) => {
      const x = padding + stepX * pointIndex;
      const y = height - padding - (stacks[pointIndex][fundIndex].from / 100) * (height - padding * 2);
      return `${x},${y}`;
    }).reverse();
    return `M${top.join(" L")} L${bottom.join(" L")} Z`;
  }

  return (
    <section className="chartPanel">
      <h3>Efficient frontier transition map</h3>
      <div className="chartCanvas">
        <svg className="axisChart" viewBox={`0 0 ${width} ${height}`}>
          <line className="gridLine" x1={padding} x2={width - padding} y1={height - padding} y2={height - padding} />
          <line className="gridLine" x1={padding} x2={padding} y1={padding} y2={height - padding} />
          {ids.map((id, index) => (
            <path d={bandPath(index)} fill={PALETTE[index % PALETTE.length]} fillOpacity={0.85} key={id} stroke="var(--bg)" strokeWidth={0.5} />
          ))}
          <text className="axisText" x={width / 2} y={height - 8}>Frontier point (low to high risk)</text>
          <text className="axisText" transform={`translate(12, ${height / 2}) rotate(-90)`}>Allocation (%)</text>
        </svg>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 8 }}>
        {ids.map((id, index) => (
          <div key={id} style={{ alignItems: "center", display: "flex", fontSize: 12.5, gap: 6 }}>
            <span style={{ background: PALETTE[index % PALETTE.length], borderRadius: 2, display: "inline-block", height: 10, width: 10 }} />
            {nameOf(id)}
          </div>
        ))}
      </div>
    </section>
  );
}

// Grid/heatmap layout of the same pairwise correlations as the row-list
// table above it -- clusters of highly-correlated funds (low diversification
// benefit) are visible at a glance in a way a flat list doesn't show.
function CorrelationMatrix({ result, nameOf }: { result: OptimizeResult; nameOf: (id: string) => string }) {
  const ids = result.assetSummary.map((row) => row.projId);
  function correlationOf(a: string, b: string): number {
    if (a === b) return 1;
    const row = result.correlations.find((c) => (c.projId1 === a && c.projId2 === b) || (c.projId1 === b && c.projId2 === a));
    return row?.correlation ?? 0;
  }
  function colorFor(value: number): string {
    if (value >= 0.7) return "rgba(180, 35, 24, 0.75)";
    if (value >= 0.4) return "rgba(180, 35, 24, 0.4)";
    if (value >= 0.1) return "rgba(180, 35, 24, 0.15)";
    if (value <= -0.4) return "rgba(14, 165, 233, 0.4)";
    if (value <= -0.1) return "rgba(14, 165, 233, 0.15)";
    return "transparent";
  }
  return (
    <div className="tableScroller">
      <table>
        <thead>
          <tr><th /> {ids.map((id) => <th key={id}>{nameOf(id)}</th>)}</tr>
        </thead>
        <tbody>
          {ids.map((rowId) => (
            <tr key={rowId}>
              <td><b>{nameOf(rowId)}</b></td>
              {ids.map((colId) => {
                const value = correlationOf(rowId, colId);
                return <td key={colId} style={{ background: colorFor(value), textAlign: "center" }}>{value.toFixed(2)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Read-only pie -- PortfolioStep's AllocationDonut is built for the
// drag-to-edit interaction on Step 1's Row type; this is the same visual
// shape but for a plain, non-editable weight map (PV shows a pie beside
// every allocation table, both the optimized one and the compared one).
function StaticPie({ weights, nameOf }: { weights: Record<string, number>; nameOf: (id: string) => string }) {
  const entries = Object.entries(weights).filter(([, w]) => w > 0);
  const total = entries.reduce((sum, [, w]) => sum + w, 0) || 1;
  const cx = 60;
  const cy = 60;
  const r = 50;
  const inner = 30;
  let angle = -90;
  const arcs = entries.map(([id, weight], index) => {
    // A full 360deg sweep (single fund at 100%) makes the arc's start and
    // end points identical -- per the SVG spec that degenerates to nothing
    // being drawn at all, so a portfolio that's 100% one fund would render
    // an empty pie even though the legend correctly says "100%". Capping
    // just under 360 keeps the arc's two endpoints distinct so the circle
    // actually renders, with no visible gap at this radius/stroke width.
    const sweep = Math.min((weight / total) * 360, 359.99);
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
    return { d, color, id, weight };
  });
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
      <svg height={120} viewBox="0 0 120 120" width={120}>
        {arcs.map((arc) => <path d={arc.d} fill={arc.color} key={arc.id} />)}
        <circle cx={cx} cy={cy} fill="var(--surface)" r={inner} />
      </svg>
      <div style={{ display: "grid", gap: 4 }}>
        {arcs.map((arc) => (
          <div key={arc.id} style={{ alignItems: "center", display: "flex", fontSize: 12.5, gap: 6 }}>
            <span style={{ background: arc.color, borderRadius: 2, display: "inline-block", height: 10, width: 10 }} />
            {nameOf(arc.id)} &mdash; {pct.format(arc.weight)}%
          </div>
        ))}
      </div>
    </div>
  );
}

// The single most actionable output: what to actually buy/sell/hold to go
// from the Step 1 "current" weights to the optimized target, and the
// resulting turnover -- previously Step 1's own weight column was
// collected but never used anywhere downstream.
function TradeListPanel({ result }: { result: OptimizeResult }) {
  if (!result.tradeList.length) return null;
  const actionLabel: Record<OptimizeResult["tradeList"][number]["action"], string> = { buy: "Buy", sell: "Sell", hold: "Hold" };
  return (
    <section className="tablePanel">
      <div className="panelHeader">
        <h3>Trade list -- current vs. optimal</h3>
        <span className="pill">{pct.format(result.totalTurnoverPct)}% one-way turnover</span>
      </div>
      <div className="tableScroller">
        <table>
          <thead><tr><th>Fund</th><th>Current</th><th>Optimal</th><th>Change</th><th>Action</th></tr></thead>
          <tbody>
            {result.tradeList.map((row) => (
              <tr key={row.projId}>
                <td>{row.displayName}</td>
                <td>{pct.format(row.currentWeightPct)}%</td>
                <td>{pct.format(row.optimalWeightPct)}%</td>
                <td>{row.deltaPct >= 0 ? "+" : ""}{pct.format(row.deltaPct)}%</td>
                <td><span className={row.action === "buy" ? "pill ok" : row.action === "sell" ? "pill warn" : "pill"}>{actionLabel[row.action]}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function WeightsTab({ result, nameOf, compareLabel }: { result: OptimizeResult; nameOf: (id: string) => string; compareLabel: string | null }) {
  const ids = Object.keys(result.optimalWeights);
  return (
    <div className="tabStack">
      <CaveatNote badge="Comparison" note={result.compareNote} />
      <TradeListPanel result={result} />
      <section className="panelGrid">
        <div className="chartPanel">
          <h3>Optimized</h3>
          <StaticPie nameOf={nameOf} weights={result.optimalWeights} />
        </div>
        {result.compareWeights ? (
          <div className="chartPanel">
            <h3>{compareLabel}</h3>
            <StaticPie nameOf={nameOf} weights={result.compareWeights} />
          </div>
        ) : null}
      </section>
      <section className="tablePanel">
        <div className="panelHeader">
          <h3>Optimal weights{compareLabel ? ` vs. ${compareLabel}` : ""}</h3>
          <button
            className="secondaryButton"
            onClick={() => downloadText(
              "optimal-weights.json",
              JSON.stringify({ optimized: result.optimalWeights, compared: result.compareWeights }, null, 2),
              "application/json"
            )}
            type="button"
          >
            weights.json
          </button>
        </div>
        <div className="tableScroller">
          <table>
            <thead>
              <tr><th>Fund</th><th>Optimized</th>{result.compareWeights ? <th>{compareLabel}</th> : null}</tr>
            </thead>
            <tbody>
              {ids.map((id) => (
                <tr key={id}>
                  <td>{nameOf(id)}</td>
                  <td>{pct.format(result.optimalWeights[id])}%</td>
                  {result.compareWeights ? <td>{pct.format(result.compareWeights[id] ?? 0)}%</td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {result.blackLitterman ? (
        <section className="tablePanel">
          <h3>Black-Litterman: equilibrium vs. adjusted returns</h3>
          <div className="tableScroller">
            <table>
              <thead><tr><th>Fund</th><th>Equilibrium return</th><th>Adjusted return</th></tr></thead>
              <tbody>
                {Object.keys(result.blackLitterman.equilibriumReturnPct).map((id) => (
                  <tr key={id}>
                    <td>{nameOf(id)}</td>
                    <td>{pct.format(result.blackLitterman!.equilibriumReturnPct[id])}%</td>
                    <td>{pct.format(result.blackLitterman!.adjustedReturnPct[id])}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="field-hint">Adjusted returns are the equilibrium returns updated by your views.</p>
        </section>
      ) : null}
    </div>
  );
}

// riskfolio-lib's own jupyter_report() ships a return histogram alongside
// weight/risk-contribution charts -- this app had no return-distribution
// view anywhere before this.
function ReturnHistogram({ monthlyReturnsPct }: { monthlyReturnsPct: number[] }) {
  if (!monthlyReturnsPct.length) return null;
  const width = 640;
  const height = 220;
  const padding = 40;
  const min = Math.min(...monthlyReturnsPct);
  const max = Math.max(...monthlyReturnsPct);
  const binCount = 12;
  const binSize = (max - min || 1) / binCount;
  const bins = new Array(binCount).fill(0);
  for (const r of monthlyReturnsPct) {
    const index = Math.min(binCount - 1, Math.floor((r - min) / binSize));
    bins[index] += 1;
  }
  const maxCount = Math.max(...bins, 1);
  const barWidth = (width - padding * 2) / binCount;

  return (
    <section className="chartPanel">
      <h3>Monthly return distribution</h3>
      <div className="chartCanvas">
        <svg className="axisChart" viewBox={`0 0 ${width} ${height}`}>
          <line className="gridLine" x1={padding} x2={width - padding} y1={height - padding} y2={height - padding} />
          <YAxisTicks format={(v) => v.toFixed(0)} height={height} max={maxCount} min={0} padding={padding} width={width} y={(v) => height - padding - (v / maxCount) * (height - padding * 2)} />
          <XAxisTicks labels={[`${min.toFixed(1)}%`, `${max.toFixed(1)}%`]} padding={padding} width={width} y={height - padding + 14} />
          {bins.map((count, index) => {
            const barHeight = (count / maxCount) * (height - padding * 2);
            const x = padding + index * barWidth;
            const binStart = min + index * binSize;
            const isNegative = binStart < 0;
            return (
              <rect
                fill={isNegative ? "var(--danger)" : "var(--accent)"}
                fillOpacity={0.85}
                height={barHeight}
                key={index}
                width={barWidth - 2}
                x={x}
                y={height - padding - barHeight}
              />
            );
          })}
          <text className="axisText" x={width / 2} y={height - 6}>Monthly return (%)</text>
        </svg>
      </div>
      <p className="field-hint">{monthlyReturnsPct.length}-month realized return series for the optimized weights over the selected time period.</p>
    </section>
  );
}

// PV's own Trailing Returns table compounds the last N calendar periods
// (3 Month/YTD/1Y/3Y/5Y/Full). result.monthlyReturnsPct is a real realized
// series but arrives as bare values with no accompanying dates, so this
// labels periods generically ("Last 3 periods") instead of borrowing
// calendar labels the response can't actually justify.
function trailingReturn(monthlyReturnsPct: number[], periods: number): number {
  const slice = monthlyReturnsPct.slice(-periods);
  const compounded = slice.reduce((acc, r) => acc * (1 + r / 100), 1);
  return (compounded - 1) * 100;
}

function TrailingReturnsPanel({ monthlyReturnsPct }: { monthlyReturnsPct: number[] }) {
  if (!monthlyReturnsPct.length) return null;
  const windows = [3, 6, 12, monthlyReturnsPct.length].filter((n, i, arr) => arr.indexOf(n) === i && n <= monthlyReturnsPct.length);
  const labelFor = (n: number) => (n === monthlyReturnsPct.length ? "Full series" : `Last ${n} periods`);
  return (
    <section className="tablePanel">
      <h3>Trailing returns</h3>
      <div className="tableScroller">
        <table>
          <thead><tr>{windows.map((n) => <th key={n}>{labelFor(n)}</th>)}</tr></thead>
          <tbody>
            <tr>{windows.map((n) => <td key={n}>{pct.format(trailingReturn(monthlyReturnsPct, n))}%</td>)}</tr>
          </tbody>
        </table>
      </div>
      <p className="field-hint">Compounded return over the trailing N periods of the {monthlyReturnsPct.length}-period realized series -- numbered by position, since the series arrives without per-period dates.</p>
    </section>
  );
}

interface DrawdownPeriod {
  startIndex: number;
  troughIndex: number;
  recoveryIndex: number | null;
  lengthPeriods: number;
  drawdownPct: number;
}

// Same running-peak logic as DrawdownChart, but grouped into discrete
// underwater periods (a new period starts each time a fresh peak is set)
// instead of a continuous series -- matches PV's own "worst drawdowns"
// table shape (Start/Trough/Length/Recovery), derived from the same
// monthlyReturnsPct data already used for the drawdown chart, no new math.
function computeDrawdownPeriods(monthlyReturnsPct: number[]): DrawdownPeriod[] {
  let value = 100;
  let peak = 100;
  let peakIndex = 0;
  let current: DrawdownPeriod | null = null;
  const periods: DrawdownPeriod[] = [];

  monthlyReturnsPct.forEach((r, i) => {
    value *= 1 + r / 100;
    if (value >= peak) {
      if (current) {
        current.recoveryIndex = i;
        periods.push(current);
        current = null;
      }
      peak = value;
      peakIndex = i;
      return;
    }
    const drawdownPct = ((value - peak) / peak) * 100;
    if (!current) {
      current = { startIndex: peakIndex, troughIndex: i, recoveryIndex: null, lengthPeriods: i - peakIndex, drawdownPct };
    } else if (drawdownPct < current.drawdownPct) {
      current.troughIndex = i;
      current.drawdownPct = drawdownPct;
      current.lengthPeriods = i - current.startIndex;
    } else {
      current.lengthPeriods = i - current.startIndex;
    }
  });
  if (current) periods.push(current);
  return periods.sort((a, b) => a.drawdownPct - b.drawdownPct).slice(0, 5);
}

function DrawdownPeriodsPanel({ monthlyReturnsPct }: { monthlyReturnsPct: number[] }) {
  const periods = computeDrawdownPeriods(monthlyReturnsPct);
  if (!periods.length) return null;
  return (
    <section className="tablePanel">
      <h3>Worst drawdown periods</h3>
      <div className="tableScroller">
        <table>
          <thead><tr><th>Rank</th><th>Start</th><th>Trough</th><th>Length</th><th>Recovery</th><th>Drawdown</th></tr></thead>
          <tbody>
            {periods.map((p, index) => (
              <tr key={index}>
                <td>{index + 1}</td>
                <td>Period {p.startIndex + 1}</td>
                <td>Period {p.troughIndex + 1}</td>
                <td>{p.lengthPeriods} period{p.lengthPeriods === 1 ? "" : "s"}</td>
                <td>{p.recoveryIndex !== null ? `Period ${p.recoveryIndex + 1}` : "Not recovered in series"}</td>
                <td>{pct.format(p.drawdownPct)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="field-hint">Worst {periods.length} underwater periods in the realized return series (numbered by position, not calendar dates).</p>
    </section>
  );
}

function PerformanceTab({ result }: { result: OptimizeResult }) {
  const rm = result.selectedRiskMeasure;
  return (
    <div className="tabStack">
      <section className="tablePanel">
        <h3>Performance summary</h3>
        <div className="tableScroller">
          <table>
            <thead>
              <tr><th>Metric</th>{result.performanceSummary.map((col) => <th key={col.label}>{col.label}</th>)}</tr>
            </thead>
            <tbody>
              <tr><td>CAGR</td>{result.performanceSummary.map((c) => <td key={c.label}>{pct.format(c.cagrPct)}%</td>)}</tr>
              <tr><td>Expected return</td>{result.performanceSummary.map((c) => <td key={c.label}>{pct.format(c.expectedReturnPct)}%</td>)}</tr>
              <tr><td>Std deviation</td>{result.performanceSummary.map((c) => <td key={c.label}>{pct.format(c.stdDevPct)}%</td>)}</tr>
              {/* These five are nullable server-side (undefined for this
                  request, e.g. no complete calendar year in the window) --
                  render "N/A" rather than letting null format as 0%. */}
              <tr><td>Best year</td>{result.performanceSummary.map((c) => <td key={c.label}>{fmtPct(c.bestYearPct)}</td>)}</tr>
              <tr><td>Worst year</td>{result.performanceSummary.map((c) => <td key={c.label}>{fmtPct(c.worstYearPct)}</td>)}</tr>
              <tr><td>Max drawdown</td>{result.performanceSummary.map((c) => <td key={c.label}>{fmtPct(c.maxDrawdownPct)}</td>)}</tr>
              <tr><td>Sharpe (ex-ante)</td>{result.performanceSummary.map((c) => <td key={c.label}>{c.sharpeExAnte}</td>)}</tr>
              <tr><td>Sharpe (ex-post)</td>{result.performanceSummary.map((c) => <td key={c.label}>{fmtNum(c.sharpeExPost)}</td>)}</tr>
              <tr><td>Sortino</td>{result.performanceSummary.map((c) => <td key={c.label}>{fmtNum(c.sortino)}</td>)}</tr>
              <tr>
                <td>Selected risk measure: {rm.label}</td>
                <td>{pct.format(rm.optimizedValue)}%</td>
                {result.performanceSummary[1] ? <td>{fmtPct(rm.comparedValue)}</td> : null}
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      {result.benchmarkComparison ? (
        <section className="tablePanel">
          <h3>Benchmark: {result.benchmarkComparison.displayName}</h3>
          <div className="tableScroller">
            <table>
              <thead><tr><th>Excess return (vs. benchmark)</th><th>Tracking error</th></tr></thead>
              <tbody>
                <tr>
                  <td>{result.benchmarkComparison.excessReturnPct >= 0 ? "+" : ""}{pct.format(result.benchmarkComparison.excessReturnPct)}%</td>
                  <td>{pct.format(result.benchmarkComparison.trackingErrorPct)}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
      <TrailingReturnsPanel monthlyReturnsPct={result.monthlyReturnsPct} />
      <EquityCurveChart series={[{ label: "Optimized", returnsPct: result.monthlyReturnsPct, color: "#5b21d6" }]} title="Growth of 100 (optimized portfolio)" />
      <DrawdownChart returnsPct={result.monthlyReturnsPct} />
      <DrawdownPeriodsPanel monthlyReturnsPct={result.monthlyReturnsPct} />
      <ReturnHistogram monthlyReturnsPct={result.monthlyReturnsPct} />
    </div>
  );
}

// Rolling line chart for a single non-return-indexed series -- realizedSharpe
// per fold doesn't compound like a return series does, so this plots the
// raw values directly instead of reusing EquityCurveChart's growth-of-100 math.
function RollingSharpeChart({ rolling }: { rolling: OptimizeResult["rolling"] }) {
  if (!rolling.length) return null;
  const width = 640;
  const height = 200;
  const padding = 40;
  const values = rolling.map((f) => f.realizedSharpe);
  const minV = Math.min(...values, 0);
  const maxV = Math.max(...values, 0);
  const n = values.length;
  const x = (i: number) => padding + (i / Math.max(n - 1, 1)) * (width - padding * 2);
  const y = (v: number) => height - padding - ((v - minV) / (maxV - minV || 1)) * (height - padding * 2);
  const path = values.map((v, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(v)}`).join(" ");
  return (
    <section className="chartPanel">
      <h3>Rolling Sharpe across folds</h3>
      <p className="field-hint">A single end-of-run Sharpe can look good purely by luck of the sample; this tracks how the realized, out-of-sample Sharpe held up fold to fold.</p>
      <div className="chartCanvas">
        <svg className="axisChart" viewBox={`0 0 ${width} ${height}`}>
          <line className="gridLine" x1={padding} x2={width - padding} y1={y(0)} y2={y(0)} />
          <line className="gridLine" x1={padding} x2={padding} y1={padding} y2={height - padding} />
          <YAxisTicks format={(v) => v.toFixed(2)} height={height} max={maxV} min={minV} padding={padding} width={width} y={y} />
          <XAxisTicks labels={n > 1 ? [rolling[0].periodLabel, rolling[n - 1].periodLabel] : [rolling[0].periodLabel]} padding={padding} width={width} y={height - padding + 14} />
          <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} />
          <text className="axisText" x={width / 2} y={height - 6}>Fold</text>
          <text className="axisText" transform={`translate(12, ${height / 2}) rotate(-90)`}>Realized Sharpe</text>
        </svg>
      </div>
    </section>
  );
}

function RollingTab({ result }: { result: OptimizeResult }) {
  const folds = result.rolling;
  const mean = (values: number[]) => values.reduce((a, b) => a + b, 0) / (values.length || 1);
  const avgReturn = mean(folds.map((f) => f.realizedReturnPct));
  const avgVol = mean(folds.map((f) => f.realizedVolatilityPct));
  const avgSharpe = mean(folds.map((f) => f.realizedSharpe));
  const positiveFolds = folds.filter((f) => f.realizedReturnPct > 0).length;
  return (
    <div className="tabStack">
      {folds.length ? (
        <div className="metricGrid">
          <StaticMetric label="Avg. realized return" sub={`across ${folds.length} folds`} value={`${pct.format(avgReturn)}%`} />
          <StaticMetric label="Avg. realized volatility" sub={`across ${folds.length} folds`} value={`${pct.format(avgVol)}%`} />
          <StaticMetric label="Avg. realized Sharpe" sub="out-of-sample" value={`${avgSharpe.toFixed(2)}`} />
          <StaticMetric label="Positive folds" sub="realized return > 0" value={`${positiveFolds} / ${folds.length}`} />
        </div>
      ) : null}
      <EquityCurveChart
        series={[{ label: "Rolling out-of-sample", returnsPct: result.rolling.map((f) => f.realizedReturnPct), color: "#5b21d6" }]}
        title="Growth of 100 (rolling out-of-sample)"
      />
      <RollingSharpeChart rolling={result.rolling} />
      <section className="tablePanel">
        <h3>Rolling out-of-sample folds</h3>
        <p className="field-hint">Each fold re-optimizes on the lookback window, then scores realized performance on the next period.</p>
        <div className="tableScroller">
          <table>
            <thead><tr><th>Period</th><th>Realized return</th><th>Realized volatility</th><th>Realized Sharpe</th></tr></thead>
            <tbody>
              {result.rolling.map((fold) => (
                <tr key={fold.periodLabel}>
                  <td>{fold.periodLabel}</td>
                  <td>{pct.format(fold.realizedReturnPct)}%</td>
                  <td>{pct.format(fold.realizedVolatilityPct)}%</td>
                  <td>{fold.realizedSharpe}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function ReportTab({ result, compareLabel, nameOf, request }: { result: OptimizeResult; compareLabel: string | null; nameOf: (id: string) => string; request?: OptimizeRequest }) {
  return (
    <div className="tabStack">
      <section className="chartPanel">
        <h3>Export</h3>
        <div className="exportActions">
          <button className="secondaryButton" onClick={() => downloadText("optimization-result.json", JSON.stringify(result, null, 2), "application/json")} type="button">result.json</button>
          {request ? (
            <button className="secondaryButton" onClick={() => downloadText("run_config.json", JSON.stringify(request, null, 2), "application/json")} type="button">run_config.json</button>
          ) : null}
          <button className="secondaryButton" onClick={() => downloadText("metrics.json", JSON.stringify(result.performanceSummary, null, 2), "application/json")} type="button">metrics.json</button>
          <button className="secondaryButton" onClick={() => window.print()} type="button">Print / Save PDF</button>
        </div>
      </section>

      <section className="reportPanel">
        <h3>Optimization Report</h3>
        <p className="footnote">Generated {result.generatedAt}</p>

        {/* Section numbers are assigned dynamically (not hardcoded "4."/"5."
            etc) because several sections only render when their data is
            present (trade list needs a Step 1 current weight, binding
            constraints only fire when a bound is actually hit, benchmark/BL
            need those set in Assumptions). A hardcoded "1,2,3,8,9" gap when
            the conditional sections don't apply reads as broken/missing
            content, not as "nothing to show here". */}
        {buildReportSections({ result, compareLabel, nameOf, request }).map((section, index) => (
          <ReportSection index={index + 1} key={section.label} title={section.label}>
            {section.content}
          </ReportSection>
        ))}
      </section>
    </div>
  );
}

interface ReportSectionSpec {
  label: string;
  content: ReactNode;
}

function buildReportSections({ result, compareLabel, nameOf, request }: {
  result: OptimizeResult; compareLabel: string | null; nameOf: (id: string) => string; request?: OptimizeRequest;
}): ReportSectionSpec[] {
  const sections: ReportSectionSpec[] = [];

  sections.push({
    label: "Objective",
    content: (
      <p>Risk measure: <b>{result.selectedRiskMeasure.label}</b> (achieved value: {pct.format(result.selectedRiskMeasure.optimizedValue)}%). {compareLabel ? `Compared against ${compareLabel}.` : "No comparison allocation was selected."}</p>
    )
  });

  sections.push({
    label: "Data and methodology",
    content: (
      <>
        {request ? (
          <p>
            Time period: <b>{request.timePeriod.startDate}</b> to <b>{request.timePeriod.endDate}</b> ({request.dataFrequency} data).
            Return method: <b>{request.returnMethod.replace(/_/g, " ")}</b>. Covariance method: <b>{request.covarianceMethod}</b>.
            Risk-free rate: <b>{request.constraints.riskFreeRatePct}%/yr</b>.
            {request.constraints.longOnly ? " Long-only." : " Short positions permitted."}
            {" "}Default weight bounds: <b>{request.constraints.minWeightPct}%</b> to <b>{request.constraints.maxWeightPct}%</b> per fund.
            {request.constraints.groupConstraintsEnabled ? " Group constraints enabled." : ""}
            {request.constraints.maxTurnoverPct !== null ? ` Max turnover: ${request.constraints.maxTurnoverPct}% per rebalance.` : ""}
            {request.constraints.maxTrackingErrorPct !== null ? ` Max tracking error: ${request.constraints.maxTrackingErrorPct}%.` : ""}
            {" "}Re-validated every <b>{request.constraints.optimizationFrequency}</b> on a <b>{request.constraints.lookbackPeriodMonths}-month</b> lookback.
          </p>
        ) : (
          <p>This run used the objective, risk measure, return/covariance estimation method, and constraints set in the Assumptions step.</p>
        )}
        <p className="footnote">See <code>docs/optimization-assumptions.md</code> and <code>docs/mock-ui-spec.md</code> for the sourced methodology behind every field.</p>
      </>
    )
  });

  sections.push({
    label: "Optimal allocation",
    content: (
      <div className="tableScroller">
        <table>
          <thead><tr><th>Fund</th><th>Weight</th></tr></thead>
          <tbody>
            {Object.entries(result.optimalWeights).sort((a, b) => b[1] - a[1]).map(([id, w]) => (
              <tr key={id}><td>{nameOf(id)}</td><td>{pct.format(w)}%</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  });

  if (result.tradeList.length) {
    sections.push({
      label: "Trade list to get there",
      content: (
        <>
          <p>From your current portfolio, reaching the optimal allocation needs <b>{pct.format(result.totalTurnoverPct)}%</b> one-way turnover.</p>
          <div className="tableScroller">
            <table>
              <thead><tr><th>Fund</th><th>Current</th><th>Optimal</th><th>Change</th><th>Action</th></tr></thead>
              <tbody>
                {result.tradeList.map((row) => (
                  <tr key={row.projId}>
                    <td>{row.displayName}</td>
                    <td>{pct.format(row.currentWeightPct)}%</td>
                    <td>{pct.format(row.optimalWeightPct)}%</td>
                    <td>{row.deltaPct >= 0 ? "+" : ""}{pct.format(row.deltaPct)}%</td>
                    <td>{row.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )
    });
  }

  if (result.bindingConstraints.length) {
    sections.push({
      label: "What's actually constraining this result",
      content: (
        <div className="tableScroller">
          <table>
            <tbody>
              {result.bindingConstraints.map((b) => (
                <tr key={b.label}><td>{b.label}</td><td>{b.detail}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    });
  }

  if (result.benchmarkComparison) {
    const bc = result.benchmarkComparison;
    sections.push({
      label: "Benchmark comparison",
      content: (
        <p>
          Against <b>{bc.displayName}</b>: {bc.excessReturnPct >= 0 ? "excess return of" : "shortfall of"} <b>{pct.format(Math.abs(bc.excessReturnPct))}%</b>,
          tracking error <b>{pct.format(bc.trackingErrorPct)}%</b>.
        </p>
      )
    });
  }

  if (result.blackLitterman && request?.blackLitterman) {
    const bl = request.blackLitterman;
    sections.push({
      label: "Black-Litterman inputs",
      content: (
        <>
          <p>Risk aversion (&delta;): <b>{bl.riskAversion}</b>. Tau (&tau;): <b>{bl.tau}</b>. Benchmark expected return: <b>{bl.benchmarkExpectedReturnPct}%</b>.</p>
          <div className="tableScroller">
            <table>
              <thead><tr><th>View</th><th>Value</th><th>Confidence</th></tr></thead>
              <tbody>
                {bl.views.map((view) => (
                  <tr key={view.key}>
                    <td>
                      {nameOf(view.assetProjId1)} {view.viewType === "absolute" ? "will return" : `will outperform ${view.assetProjId2 ? nameOf(view.assetProjId2) : "-"} by`}
                    </td>
                    <td>{view.adjustedPerformancePct}%</td>
                    <td>{view.confidence}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )
    });
  }

  sections.push({
    label: "Performance results",
    content: (
      <div className="tableScroller">
        <table>
          <thead><tr><th>Metric</th>{result.performanceSummary.map((c) => <th key={c.label}>{c.label}</th>)}</tr></thead>
          <tbody>
            <tr><td>Expected return</td>{result.performanceSummary.map((c) => <td key={c.label}>{pct.format(c.expectedReturnPct)}%</td>)}</tr>
            <tr><td>Std deviation</td>{result.performanceSummary.map((c) => <td key={c.label}>{pct.format(c.stdDevPct)}%</td>)}</tr>
            <tr><td>Sharpe (ex-ante)</td>{result.performanceSummary.map((c) => <td key={c.label}>{c.sharpeExAnte}</td>)}</tr>
          </tbody>
        </table>
      </div>
    )
  });

  sections.push({
    label: "Status",
    content: (
      <p>
        Computed by the riskfolio-lib-backed optimizer (<code>POST /api/optimize</code>) over the cached SEC Open Data NAV history for the funds and time period above. Solver status: <b>feasible solution found</b>.
        {result.robustNote ? ` ${result.robustNote}` : ""}
        {result.robustOptimizationNote ? ` ${result.robustOptimizationNote}` : ""}
        {result.constraintNote ? ` ${result.constraintNote}` : ""}
      </p>
    )
  });

  return sections;
}

function ReportSection({ title, index, children }: { title: string; index: number; children: ReactNode }) {
  return (
    <section>
      <strong>{index}. {title}</strong>
      {children}
    </section>
  );
}
