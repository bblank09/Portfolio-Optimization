import { AlertTriangle, BarChart3 } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { SecFund } from "../types/backtest";
import type { OptimizeResult } from "../types/optimize";

interface Props {
  result: OptimizeResult | null;
  funds: SecFund[]; // selected shortlist, for display-name lookups
  compareLabel: string | null;
}

type ResultTab = "Summary" | "Frontier" | "Weights" | "Performance" | "Rolling" | "Report";
const TABS: ResultTab[] = ["Summary", "Frontier", "Weights", "Performance", "Rolling", "Report"];

const pct = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
// Same palette PortfolioStep's AllocationDonut uses, so a fund reads as
// the same color across the Portfolio step and these Results charts.
const PALETTE = ["#5b21d6", "#34383e", "#92620a", "#9aa1ac", "#7c4ded"];

export function OptimizeResults({ result, funds, compareLabel }: Props) {
  const [activeTab, setActiveTab] = useState<ResultTab>("Summary");
  const nameOf = (projId: string) => funds.find((f) => f.proj_id === projId)?.display_name ?? projId;

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
          <h2>{funds.length} funds &middot; mock data (Phase 4, no backend yet)</h2>
        </div>
      </div>

      <nav aria-label="Optimization output tabs" className="resultTabs">
        {TABS.map((tab) => (
          <button className={activeTab === tab ? "resultTab active" : "resultTab"} key={tab} onClick={() => setActiveTab(tab)} type="button">
            {tab}
          </button>
        ))}
      </nav>

      {activeTab === "Summary" ? <SummaryTab compareLabel={compareLabel} nameOf={nameOf} result={result} setActiveTab={setActiveTab} /> : null}
      {activeTab === "Frontier" ? <FrontierTab nameOf={nameOf} result={result} /> : null}
      {activeTab === "Weights" ? <WeightsTab compareLabel={compareLabel} nameOf={nameOf} result={result} /> : null}
      {activeTab === "Performance" ? <PerformanceTab result={result} /> : null}
      {activeTab === "Rolling" ? <RollingTab result={result} /> : null}
      {activeTab === "Report" ? <ReportTab compareLabel={compareLabel} nameOf={nameOf} result={result} /> : null}
    </section>
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
          {paths.map((p) => (
            <path
              d={p.points.map((v, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(v)}`).join(" ")}
              fill="none"
              key={p.label}
              stroke={p.color}
              strokeWidth={2}
            />
          ))}
          <text className="axisText" x={width / 2} y={height - 8}>Period</text>
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

function SummaryTab({ result, nameOf, compareLabel, setActiveTab }: { result: OptimizeResult; nameOf: (id: string) => string; compareLabel: string | null; setActiveTab: (tab: ResultTab) => void }) {
  const topWeights = Object.entries(result.optimalWeights).sort((a, b) => b[1] - a[1]);
  const topFund = topWeights[0];
  const optimized = result.performanceSummary[0];
  const compared = result.performanceSummary[1];
  return (
    <div className="tabStack">
      <section className="chartPanel">
        <h3>Run summary</h3>
        <p className="summaryText">
          The optimizer put the most weight in <b>{topFund ? nameOf(topFund[0]) : "-"}</b> ({pct.format(topFund?.[1] ?? 0)}%) across {topWeights.length} funds,
          for an expected return of <b>{pct.format(optimized?.expectedReturnPct ?? 0)}%</b> at <b>{pct.format(optimized?.stdDevPct ?? 0)}%</b> volatility
          (Sharpe {optimized?.sharpeExAnte ?? 0}).
          {compareLabel && compared ? (
            <> Compared against <b>{compareLabel}</b> ({pct.format(compared.expectedReturnPct)}% return, {pct.format(compared.stdDevPct)}% volatility), the optimized mix {optimized && compared && optimized.sharpeExAnte >= compared.sharpeExAnte ? "has a better" : "has a lower"} risk-adjusted return.</>
          ) : null}
          {" "}Selected risk measure (<b>{result.selectedRiskMeasure.label}</b>): <b>{pct.format(result.selectedRiskMeasure.optimizedValue)}%</b>.
        </p>
      </section>
      {result.robustNote ? (
        <div className="notePanel">
          <span className="badge">Robust Optimization</span>
          <p>{result.robustNote}</p>
        </div>
      ) : null}
      <div className="metricGrid">
        <ClickableMetric label="Expected return" onClick={() => setActiveTab("Performance")} sub="See Performance tab" value={`${pct.format(optimized?.expectedReturnPct ?? 0)}%`} />
        <ClickableMetric label="Volatility" onClick={() => setActiveTab("Performance")} sub="See Performance tab" value={`${pct.format(optimized?.stdDevPct ?? 0)}%`} />
        <ClickableMetric label="Sharpe (ex-ante)" onClick={() => setActiveTab("Performance")} sub="See Performance tab" value={`${optimized?.sharpeExAnte ?? 0}`} />
        <ClickableMetric label="Top holding" onClick={() => setActiveTab("Weights")} sub="See Weights tab" value={topFund ? nameOf(topFund[0]) : "-"} />
      </div>
      <section className="chartPanel">
        <h3>Risk contribution</h3>
        <RiskContributionBars nameOf={nameOf} riskContributionPct={result.riskContributionPct} />
      </section>
      <ResultChecklist compareLabel={compareLabel} result={result} />
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

// Mirrors the sibling backtester's own Summary-tab "Result checklist" --
// a quick pass/fail scan of the run, not just headline numbers.
function ResultChecklist({ result, compareLabel }: { result: OptimizeResult; compareLabel: string | null }) {
  const weightSum = Object.values(result.optimalWeights).reduce((a, b) => a + b, 0);
  const items: { label: string; status: "ok" | "warn"; detail: string }[] = [
    {
      label: "Weights sum to 100%",
      status: Math.abs(weightSum - 100) < 0.5 ? "ok" : "warn",
      detail: `${pct.format(weightSum)}%`
    },
    { label: "Solver converged", status: "ok", detail: "feasible solution found" },
    {
      label: "Robust optimization",
      status: "ok",
      detail: result.robustNote ? "applied" : "not enabled"
    },
    {
      label: "Comparison allocation",
      status: "ok",
      detail: compareLabel ? `vs. ${compareLabel}` : "none selected"
    }
  ];
  if (result.blackLitterman) {
    items.push({ label: "Black-Litterman views", status: "ok", detail: "equilibrium returns adjusted" });
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
                <td><span className={item.status === "ok" ? "pill ok" : "pill warn"}>{item.status === "ok" ? "OK" : "Check"}</span></td>
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
  const vols = result.frontier.map((p) => p.volatilityPct);
  const rets = result.frontier.map((p) => p.expectedReturnPct);
  const minVol = Math.min(...vols);
  const maxVol = Math.max(...vols);
  const minRet = Math.min(...rets);
  const maxRet = Math.max(...rets);
  const x = (v: number) => padding + ((v - minVol) / (maxVol - minVol || 1)) * (width - padding * 2);
  const y = (r: number) => height - padding - ((r - minRet) / (maxRet - minRet || 1)) * (height - padding * 2);
  const path = result.frontier.map((p, i) => `${i === 0 ? "M" : "L"} ${x(p.volatilityPct)} ${y(p.expectedReturnPct)}`).join(" ");

  return (
    <div className="tabStack">
      <section className="chartPanel">
        <h3>Efficient frontier</h3>
        <div className="chartCanvas">
          <svg className="axisChart" viewBox={`0 0 ${width} ${height}`}>
            <line className="gridLine" x1={padding} x2={width - padding} y1={height - padding} y2={height - padding} />
            <line className="gridLine" x1={padding} x2={padding} y1={padding} y2={height - padding} />
            <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} />
            <text className="axisText" x={width / 2} y={height - 8}>Volatility (%)</text>
            <text className="axisText" transform={`translate(12, ${height / 2}) rotate(-90)`}>Expected return (%)</text>
          </svg>
        </div>
        <p className="field-hint">Mock frontier -- Phase 5 replaces this with riskfolio-lib's real efficient_frontier() output.</p>
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
    const sweep = (weight / total) * 360;
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

function WeightsTab({ result, nameOf, compareLabel }: { result: OptimizeResult; nameOf: (id: string) => string; compareLabel: string | null }) {
  const ids = Object.keys(result.optimalWeights);
  return (
    <div className="tabStack">
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
          <text className="axisText" x={width / 2} y={height - 8}>Monthly return (%)</text>
        </svg>
      </div>
      <p className="field-hint">{monthlyReturnsPct.length}-month synthetic return series for the optimized portfolio (mock -- Phase 5 uses the real historical/simulated series).</p>
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
              <tr><td>Best year</td>{result.performanceSummary.map((c) => <td key={c.label}>{pct.format(c.bestYearPct)}%</td>)}</tr>
              <tr><td>Worst year</td>{result.performanceSummary.map((c) => <td key={c.label}>{pct.format(c.worstYearPct)}%</td>)}</tr>
              <tr><td>Max drawdown</td>{result.performanceSummary.map((c) => <td key={c.label}>{pct.format(c.maxDrawdownPct)}%</td>)}</tr>
              <tr><td>Sharpe (ex-ante)</td>{result.performanceSummary.map((c) => <td key={c.label}>{c.sharpeExAnte}</td>)}</tr>
              <tr><td>Sharpe (ex-post)</td>{result.performanceSummary.map((c) => <td key={c.label}>{c.sharpeExPost}</td>)}</tr>
              <tr><td>Sortino</td>{result.performanceSummary.map((c) => <td key={c.label}>{c.sortino}</td>)}</tr>
              <tr>
                <td>Selected risk measure: {rm.label}</td>
                <td>{pct.format(rm.optimizedValue)}%</td>
                {result.performanceSummary[1] ? <td>{rm.comparedValue !== null ? `${pct.format(rm.comparedValue)}%` : "-"}</td> : null}
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <EquityCurveChart series={[{ label: "Optimized", returnsPct: result.monthlyReturnsPct, color: "#5b21d6" }]} title="Growth of 100 (optimized portfolio)" />
      <ReturnHistogram monthlyReturnsPct={result.monthlyReturnsPct} />
    </div>
  );
}

function RollingTab({ result }: { result: OptimizeResult }) {
  return (
    <div className="tabStack">
      <EquityCurveChart
        series={[{ label: "Rolling out-of-sample", returnsPct: result.rolling.map((f) => f.realizedReturnPct), color: "#5b21d6" }]}
        title="Growth of 100 (rolling out-of-sample)"
      />
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

function ReportTab({ result, compareLabel, nameOf }: { result: OptimizeResult; compareLabel: string | null; nameOf: (id: string) => string }) {
  return (
    <div className="tabStack">
      <section className="chartPanel">
        <h3>Export</h3>
        <div className="exportActions">
          <button className="secondaryButton" onClick={() => downloadText("optimization-result.json", JSON.stringify(result, null, 2), "application/json")} type="button">result.json</button>
          <button className="secondaryButton" onClick={() => window.print()} type="button">Print / Save PDF</button>
        </div>
      </section>

      <section className="reportPanel">
        <h3>Optimization Report</h3>
        <p className="footnote">Generated {result.generatedAt} &middot; mock data, Phase 4 &mdash; no real optimization has run yet</p>

        <ReportSection title="1. Objective">
          <p>Risk measure: <b>{result.selectedRiskMeasure.label}</b> (achieved value: {pct.format(result.selectedRiskMeasure.optimizedValue)}%). {compareLabel ? `Compared against ${compareLabel}.` : "No comparison allocation was selected."}</p>
        </ReportSection>

        <ReportSection title="2. Data and methodology">
          <p>This run used the objective, risk measure, return/covariance estimation method, and constraints set in the Assumptions step. See <code>docs/optimization-assumptions.md</code> and <code>docs/mock-ui-spec.md</code> for the sourced methodology behind every field.</p>
        </ReportSection>

        <ReportSection title="3. Optimal allocation">
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
        </ReportSection>

        <ReportSection title="4. Performance results">
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
        </ReportSection>

        <ReportSection title="5. Status">
          <p>Phase 4 mock &mdash; these numbers are deterministically generated from your inputs for UI review, not a real optimization. Phase 5 wires this to a real riskfolio-lib-backed backend.</p>
        </ReportSection>
      </section>
    </div>
  );
}

function ReportSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <strong>{title}</strong>
      {children}
    </section>
  );
}
