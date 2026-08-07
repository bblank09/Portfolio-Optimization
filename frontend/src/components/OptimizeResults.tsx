import { AlertTriangle, BarChart3 } from "lucide-react";
import { useState } from "react";
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

      {activeTab === "Summary" ? <SummaryTab compareLabel={compareLabel} nameOf={nameOf} result={result} /> : null}
      {activeTab === "Frontier" ? <FrontierTab nameOf={nameOf} result={result} /> : null}
      {activeTab === "Weights" ? <WeightsTab compareLabel={compareLabel} nameOf={nameOf} result={result} /> : null}
      {activeTab === "Performance" ? <PerformanceTab result={result} /> : null}
      {activeTab === "Rolling" ? <RollingTab result={result} /> : null}
      {activeTab === "Report" ? <ReportTab compareLabel={compareLabel} result={result} /> : null}
    </section>
  );
}

function feasibilityTitle(status: OptimizeResult["feasibility"]): string {
  if (status === "non_convergence") return "The solver did not converge.";
  if (status === "infeasible_constraints") return "Constraints are mutually infeasible.";
  return "Not enough data to optimize.";
}

function SummaryTab({ result, nameOf, compareLabel }: { result: OptimizeResult; nameOf: (id: string) => string; compareLabel: string | null }) {
  const topWeights = Object.entries(result.optimalWeights).sort((a, b) => b[1] - a[1]).slice(0, 3);
  return (
    <div className="tabStack">
      {result.robustNote ? (
        <div className="notePanel">
          <span className="badge">Robust Optimization</span>
          <p>{result.robustNote}</p>
        </div>
      ) : null}
      <section className="chartPanel">
        <h3>Top holdings</h3>
        <div className="metricGrid">
          {topWeights.map(([projId, weight]) => (
            <div className="metricCard" key={projId}>
              <span>{nameOf(projId)}</span>
              <strong>{pct.format(weight)}%</strong>
            </div>
          ))}
        </div>
      </section>
      <section className="tablePanel">
        <h3>Risk contribution</h3>
        <div className="tableScroller">
          <table>
            <thead><tr><th>Fund</th><th>Risk contribution</th></tr></thead>
            <tbody>
              {Object.entries(result.riskContributionPct).sort((a, b) => b[1] - a[1]).map(([projId, share]) => (
                <tr key={projId}><td>{nameOf(projId)}</td><td>{pct.format(share)}%</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {compareLabel ? (
        <p className="field-hint">Compared against <b>{compareLabel}</b> in the Weights and Performance tabs.</p>
      ) : null}
    </div>
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
    </div>
  );
}

function WeightsTab({ result, nameOf, compareLabel }: { result: OptimizeResult; nameOf: (id: string) => string; compareLabel: string | null }) {
  const ids = Object.keys(result.optimalWeights);
  return (
    <div className="tabStack">
      <section className="tablePanel">
        <h3>Optimal weights{compareLabel ? ` vs. ${compareLabel}` : ""}</h3>
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
          <p className="field-hint">Adjusted returns are equilibrium returns adjusted for the given views -- same phrasing PortfolioVisualizer uses.</p>
        </section>
      ) : null}
    </div>
  );
}

function PerformanceTab({ result }: { result: OptimizeResult }) {
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
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function RollingTab({ result }: { result: OptimizeResult }) {
  return (
    <div className="tabStack">
      <section className="tablePanel">
        <h3>Rolling out-of-sample folds</h3>
        <p className="field-hint">Each fold re-optimizes on the lookback window, then scores realized performance on the next period -- same pattern as PortfolioVisualizer's rolling-optimization tool.</p>
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

function ReportTab({ result, compareLabel }: { result: OptimizeResult; compareLabel: string | null }) {
  return (
    <div className="reportPanel">
      <section>
        <h3>Methodology</h3>
        <p>This run used the objective, risk measure, return/covariance estimation method, and constraints set in the Assumptions step. See <code>docs/optimization-assumptions.md</code> and <code>docs/mock-ui-spec.md</code> for the sourced methodology behind every field.</p>
      </section>
      <section>
        <h3>Comparison</h3>
        <p>{compareLabel ? `Compared against ${compareLabel}.` : "No comparison allocation was selected."}</p>
      </section>
      <section>
        <h3>Status</h3>
        <p>Phase 4 mock -- these numbers are deterministically generated from your inputs for UI review, not a real optimization. Phase 5 wires this to a real riskfolio-lib-backed backend.</p>
      </section>
    </div>
  );
}
