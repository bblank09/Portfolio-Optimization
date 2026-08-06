import { AlertTriangle, BarChart3, Download, ShieldCheck } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";
import type { BacktestResult, TableSection, TimeSeriesPoint } from "../types/backtest";

interface Props {
  result: BacktestResult | null;
}

type OutputTab = "Summary" | "Growth" | "Drawdown" | "Returns" | "Metrics" | "Cashflows" | "Rebalancing" | "Report";

const outputTabs: OutputTab[] = ["Summary", "Growth", "Drawdown", "Returns", "Metrics", "Cashflows", "Rebalancing", "Report"];
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const pct = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 });

// Mirrors DEGENERACY_TOLERANCE in backend/app/engine/metrics.py: a computed
// std never lands on exactly 0, so a truthiness guard lets a ratio divide by
// ~1e-17 and report a meaningless astronomical value.
const DEGENERACY_TOLERANCE = 1e-12;

function slugify(label: string) {
  return label.replace(/[^a-zA-Z0-9]+/g, "-");
}

interface SummaryMetric {
  label: string;
  value: string;
  sub?: string;
  tone?: "positive" | "negative";
  emphasis?: boolean;
}

function toneOf(value: number): "positive" | "negative" | undefined {
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return undefined;
}

export function RunSummary({ result }: Props) {
  const [activeTab, setActiveTab] = useState<OutputTab>("Summary");

  useEffect(() => {
    setActiveTab("Summary");
  }, [result?.run_id]);

  if (!result) {
    return (
      <section className="resultShell emptyResult">
        <span className="emptyResultIcon"><BarChart3 size={22} /></span>
        <h2>Run a backtest to see results.</h2>
        <p>Add funds, set weights to 100%, then run to see growth, drawdown, and the research report.</p>
      </section>
    );
  }

  return (
    <section className="resultShell" id="report-output">
      <div className="resultHeader">
        <div>
          <span className="sourceLine"><ShieldCheck size={16} /> Backtest result</span>
          <h2>{result.request.start_date} to {result.request.end_date}</h2>
        </div>
        <button className="secondaryButton" onClick={() => downloadJson(result)} type="button">
          <Download size={16} /> Result JSON
        </button>
      </div>

      <nav className="resultTabs" aria-label="Backtest output tabs">
        {outputTabs.map((tab) => (
          <button className={activeTab === tab ? "resultTab active" : "resultTab"} key={tab} onClick={() => setActiveTab(tab)} type="button">
            {tab}
          </button>
        ))}
      </nav>

      {activeTab === "Summary" ? <SummaryTab result={result} setActiveTab={setActiveTab} /> : null}
      {activeTab === "Growth" ? <GrowthTab result={result} /> : null}
      {activeTab === "Drawdown" ? <DrawdownTab result={result} /> : null}
      {activeTab === "Returns" ? <ReturnsTab result={result} /> : null}
      {activeTab === "Metrics" ? <MetricsTab result={result} /> : null}
      {activeTab === "Cashflows" ? <CashflowsTab result={result} /> : null}
      {activeTab === "Rebalancing" ? <RebalancingTab result={result} /> : null}
      {activeTab === "Report" ? <ReportTab result={result} /> : null}
    </section>
  );
}

function SummaryTab({ result, setActiveTab }: { result: BacktestResult; setActiveTab: (tab: OutputTab) => void }) {
  const m = result.summary;
  const metrics = summaryMetrics(result);
  return (
    <div className="tabStack">
      <section className="chartPanel">
        <h3>Run summary</h3>
        <p className="summaryText">{resultNarrative(result)}</p>
      </section>
      <div className="metricGrid">
        {metrics.map((metric) => (
          <Metric key={metric.label} emphasis={metric.emphasis} label={metric.label} sub={metric.sub} tone={metric.tone} value={metric.value} />
        ))}
      </div>
      <section className="chartPanel">
        <h3>Result checklist</h3>
        <DataTable caption="Result checklist" compact section={{ title: "", rows: resultChecklist(result) }} />
      </section>
      <section className="chartPanel">
        <h3>Always-on analysis</h3>
        <div className="alwaysOnGrid">
          <ClickableMetric label="Benchmark Risk" value={`Beta ${formatNumber(findRiskValue(result, "beta"))}`} sub={`Alpha ${formatPercentLike(findRiskValue(result, "alpha"))} · TE ${formatPercentLike(findRiskValue(result, "tracking_error"))}`} onClick={() => setActiveTab("Metrics")} />
          <ClickableMetric label="Drawdown Stress" value={pct.format(m.max_drawdown)} sub="Worst historical loss and stress values" onClick={() => setActiveTab("Drawdown")} />
          <ClickableMetric label="Diversification" value={`${result.diversification.rows.length} rows`} sub="Correlation and concentration checks" onClick={() => setActiveTab("Metrics")} />
          <ClickableMetric label="Research Report" value="Ready" sub="Method, formulas, caveats" onClick={() => setActiveTab("Report")} />
        </div>
      </section>
      <AxisCurve title="Portfolio vs Benchmark Growth" series={[
        { label: "Portfolio", points: result.equity_curve, color: "#5b21d6", valueFormat: money.format },
        { label: "Benchmark", points: result.benchmark_curve, color: "#0ea5e9", valueFormat: money.format }
      ]} valueFormat={money.format} />
    </div>
  );
}

function GrowthTab({ result }: { result: BacktestResult }) {
  const netInvested = buildNetInvestedCurve(result);
  const derived = deriveResult(result);
  return (
    <div className="tabStack">
      <div className="metricGrid">
        <Metric label="Start value" value={money.format(result.equity_curve[0]?.value ?? 0)} sub={result.equity_curve[0]?.date} />
        <Metric label="Ending value" value={money.format(result.summary.ending_value)} sub={lastDate(result.equity_curve)} />
        <Metric label="Net invested" value={money.format(lastPoint(netInvested)?.value ?? result.request.initial_capital)} />
        <Metric label="Benchmark value" value={money.format(lastPoint(result.benchmark_curve)?.value ?? 0)} />
      </div>
      <AxisCurve title="Portfolio growth path" series={[
        { label: "Portfolio", points: result.equity_curve, color: "#5b21d6", valueFormat: money.format },
        { label: "Benchmark", points: result.benchmark_curve, color: "#0ea5e9", valueFormat: money.format },
        { label: "Net invested", points: netInvested, color: "#6b7280", dashed: true, valueFormat: money.format }
      ]} valueFormat={money.format} />
      <section className="chartPanel">
        <h3>Value milestones</h3>
        <DataTable caption="Value milestones" section={{ title: "", rows: milestoneRows(result, netInvested) }} />
      </section>
      <section className="chartPanel">
        <h3>Trailing performance</h3>
        <DataTable caption="Trailing performance" section={{ title: "", rows: derived.trailingReturns }} />
      </section>
      <AxisCurve title="Rolling 12M return and volatility" series={[
        { label: "Rolling return", points: derived.rolling.map((row) => ({ date: row.date, value: row.return })), color: "#5b21d6", valueFormat: pct.format },
        { label: "Rolling volatility", points: derived.rolling.map((row) => ({ date: row.date, value: row.volatility })), color: "#0ea5e9", valueFormat: pct.format }
      ]} valueFormat={pct.format} />
      {derived.rolling.some((row) => row.sharpe !== null) ? (
        <section className="chartPanel">
          <h3>Rolling 12M Sharpe</h3>
          <p className="summaryText">A point-in-time Sharpe ratio can look good purely by luck of the end date; this tracks how the risk-adjusted return held up across every trailing 12-month window.</p>
          <AxisCurve title="Rolling 12M Sharpe ratio" series={[
            {
              label: "Rolling Sharpe",
              points: derived.rolling.filter((row) => row.sharpe !== null).map((row) => ({ date: row.date, value: row.sharpe as number })),
              color: "#5b21d6",
              valueFormat: number.format
            }
          ]} valueFormat={number.format} />
        </section>
      ) : null}
      <section className="chartPanel">
        <h3>Rolling 12M table</h3>
        <DataTable caption="Rolling 12M table" section={{ title: "", rows: derived.rolling }} />
      </section>
    </div>
  );
}

function DrawdownTab({ result }: { result: BacktestResult }) {
  const derived = deriveResult(result);
  return (
    <div className="tabStack">
      <div className="metricGrid">
        <Metric label="Worst drawdown" value={pct.format(result.summary.max_drawdown)} />
        <Metric label="Ulcer proxy" value={formatNumber(ulcerIndex(result.drawdown_curve))} sub="From SEC drawdown path" />
        <Metric label="Stress -10%" value={money.format(result.summary.ending_value * 0.9)} />
      </div>
      <AxisCurve title="Drawdown path" series={[
        { label: "Portfolio drawdown", points: result.drawdown_curve, color: "#b42318", area: true, valueFormat: pct.format }
      ]} valueFormat={pct.format} />
      <section className="chartPanel">
        <h3>Drawdown stress scenarios</h3>
        <DataTable caption="Drawdown stress scenarios" section={{ title: "", rows: stressRows(result) }} />
      </section>
      <div className="panelGrid">
        <section className="chartPanel">
          <h3>Worst drawdown periods</h3>
          <DataTable caption="Worst drawdown periods" section={{ title: "", rows: derived.drawdownPeriods }} />
        </section>
        <section className="chartPanel">
          <h3>Stress interpretation</h3>
          <DataTable caption="Stress interpretation" section={{ title: "", rows: stressInterpretationRows(result, derived) }} />
        </section>
      </div>
    </div>
  );
}

function ReturnsTab({ result }: { result: BacktestResult }) {
  const derived = deriveResult(result);
  return (
    <div className="tables oneColumn">
      <DataTable section={{ title: "Annual returns", rows: derived.annualReturns }} />
      <MonthlyHeatmap rows={derived.monthlyGrid} />
      <section className="chartPanel">
        <h3>Monthly return distribution</h3>
        <Histogram rows={derived.histogram} />
        <DataTable caption="Monthly return distribution" compact section={{ title: "", rows: derived.histogram }} />
      </section>
      <div className="panelGrid">
        <section className="chartPanel">
          <h3>Best months</h3>
          <DataTable caption="Best months" section={{ title: "", rows: derived.bestMonths }} />
        </section>
        <section className="chartPanel">
          <h3>Worst months</h3>
          <DataTable caption="Worst months" section={{ title: "", rows: derived.worstMonths }} />
        </section>
      </div>
    </div>
  );
}

function MetricsTab({ result }: { result: BacktestResult }) {
  const derived = deriveResult(result);
  return (
    <div className="tabStack">
      <section className="chartPanel">
        <h3>Metrics</h3>
        <DataTable caption="Metrics" section={{ title: "", rows: keyMetricRows(result) }} />
      </section>
      <section className="chartPanel">
        <h3>Asset risk and allocation</h3>
        <DataTable caption="Asset risk and allocation" section={{ title: "", rows: assetRows(result) }} />
      </section>
      <section className="chartPanel">
        <h3>Diversification Check</h3>
        <DataTable caption="Diversification Check" section={{ title: "", rows: result.diversification.rows }} />
      </section>
      {result.diversification.rows.length ? (
        <section className="chartPanel">
          <h3>Correlation matrix</h3>
          <p className="summaryText">Same pairwise correlations as the table above, laid out as a grid so clusters of highly correlated funds &mdash; the ones providing the least diversification benefit &mdash; are visible at a glance.</p>
          <CorrelationMatrix result={result} />
        </section>
      ) : null}
      {result.rolling_correlation.length ? (
        <section className="chartPanel">
          <h3>Rolling correlation</h3>
          <p className="summaryText">A single end-of-run correlation can hide regime changes; this tracks each asset pair's correlation over a rolling window.</p>
          <AxisCurve title="Rolling asset-pair correlation" series={rollingCorrelationSeries(result)} valueFormat={number.format} />
        </section>
      ) : null}
      <section className="chartPanel">
        <h3>Benchmark risk decomposition</h3>
        <DataTable caption="Benchmark risk decomposition" section={{ title: "", rows: benchmarkDecompositionRows(result, derived) }} />
      </section>
      <p className="footnote">Full equations for every metric on this page are in the Report tab's Formula reference section.</p>
    </div>
  );
}

function CashflowsTab({ result }: { result: BacktestResult }) {
  if (!result.request.cashflow.enabled) {
    return <div className="emptyState">Cashflows are disabled for this run.</div>;
  }
  return (
    <div className="tabStack">
      <div className="metricGrid">
        <Metric label="Total contributions" value={money.format(result.summary.total_contributed)} />
        <Metric label="Total withdrawals" value={money.format(result.summary.total_withdrawn)} />
        <Metric label="Net invested" value={money.format(lastPoint(buildNetInvestedCurve(result))?.value ?? result.request.initial_capital)} />
        <Metric label="Net profit" value={money.format(result.summary.ending_value + result.summary.total_withdrawn - result.summary.total_contributed)} />
        <Metric label="Events" value={String(result.summary.cashflow_count)} />
      </div>
      <DataTable section={{ title: "Yearly cashflow summary", rows: yearlyCashflowRows(result) }} />
      <DataTable section={{ title: "Cashflow events", rows: result.cashflows.map((row) => ({ date: row.date, amount: row.amount })) }} />
    </div>
  );
}

function RebalancingTab({ result }: { result: BacktestResult }) {
  if (result.request.rebalancing.mode === "none") {
    return <div className="emptyState">Rebalancing is set to None.</div>;
  }
  return (
    <div className="tabStack">
      <div className="metricGrid">
        <Metric label="Rebalance count" value={String(result.summary.rebalance_count)} />
        <Metric label="Average turnover" value={pct.format(mean(result.rebalances.map((row) => row.turnover)))} />
        <Metric label="Max turnover" value={pct.format(Math.max(...result.rebalances.map((row) => row.turnover), 0))} />
        <Metric label="Total costs" value={money.format(result.summary.total_costs)} />
        <Metric label="Mode" value={result.request.rebalancing.mode} />
        <Metric label="Max single cost" value={money.format(Math.max(...result.rebalances.map((row) => row.cost), 0))} />
      </div>
      <section className="chartPanel">
        <h3>Target allocation</h3>
        {result.request.assets.map((asset) => (
          <div className="allocationBarRow" key={asset.proj_id}>
            <span>{asset.display_name}: target {asset.weight.toFixed(1)}%</span>
            <div className="bar"><span style={{ width: `${asset.weight}%` }} /></div>
          </div>
        ))}
      </section>
      <DataTable section={{ title: "Rebalance events", rows: result.rebalances.map((row) => ({ ...row, turnover: pct.format(row.turnover), cost: money.format(row.cost) })) }} />
    </div>
  );
}

function ReportTab({ result }: { result: BacktestResult }) {
  const derived = deriveResult(result);
  const hasCashflow = result.request.cashflow.enabled;
  const hasRebalancing = result.request.rebalancing.mode !== "none";
  return (
    <div className="tabStack">
      <section className="chartPanel">
        <h3>Export</h3>
        <div className="exportActions">
          <button className="secondaryButton" onClick={() => downloadText("report.md", reportMarkdown(result, derived), "text/markdown")} type="button">report.md</button>
          <button className="secondaryButton" onClick={() => downloadText("run_config.json", JSON.stringify(result.request, null, 2), "application/json")} type="button">run_config.json</button>
          <button className="secondaryButton" onClick={() => downloadText("metrics.json", JSON.stringify(result.summary, null, 2), "application/json")} type="button">metrics.json</button>
          <button className="secondaryButton" onClick={() => window.print()} type="button">Print / Save PDF</button>
        </div>
      </section>

      <section className="reportPanel">
        <h3>Research Report &mdash; {result.request.start_date} to {result.request.end_date}</h3>
        <p className="footnote">Run {result.run_id} &middot; generated {result.created_at} &middot; SEC Open Data, NAV per unit</p>

        <ReportSection title="1. Research question">
          <p>{resultNarrative(result)}</p>
        </ReportSection>

        <ReportSection title="2. Data and methodology">
          <p>All returns are computed from cached SEC Open Data mutual fund NAV series (month-end frequency, {"m"} = 12 periods/year). No mock, simulated, or forecast price series are used. Fund period returns use simple returns r_t = NAV_t / NAV_(t-1) - 1; missing NAV observations are never forward-filled into a fabricated return. Portfolio time-weighted return removes external cashflows using the configured timing so contributions/withdrawals do not themselves create investment return.</p>
        </ReportSection>

        <ReportSection title="3. Portfolio specification">
          <DataTable caption="Portfolio specification" compact section={{ title: "", rows: assumptionRows(result) }} />
        </ReportSection>

        <ReportSection title="4. Performance results">
          <DataTable caption="Performance results" section={{ title: "", rows: keyMetricRows(result) }} />
        </ReportSection>

        <ReportSection title="5. Risk and benchmark analysis">
          <DataTable compact section={result.risk_metrics} />
          <DataTable caption="Benchmark risk decomposition" section={{ title: "", rows: benchmarkDecompositionRows(result, derived) }} />
        </ReportSection>

        <ReportSection title="6. Drawdown analysis">
          <DataTable caption="Drawdown stress scenarios" section={{ title: "", rows: stressRows(result) }} />
          <DataTable section={{ title: "Worst historical drawdown periods", rows: derived.drawdownPeriods }} />
        </ReportSection>

        <ReportSection title="7. Diversification and correlation">
          <DataTable compact section={result.diversification} />
        </ReportSection>

        <ReportSection title="8. Asset-level attribution">
          <DataTable caption="Asset-level attribution" section={{ title: "", rows: assetRows(result) }} />
        </ReportSection>

        {hasCashflow ? (
          <ReportSection title="9. Cashflow analysis">
            <DataTable caption="Cashflow analysis" compact section={{ title: "", rows: yearlyCashflowRows(result) }} />
          </ReportSection>
        ) : null}

        {hasRebalancing ? (
          <ReportSection title={hasCashflow ? "10. Rebalancing analysis" : "9. Rebalancing analysis"}>
            <DataTable
              caption="Rebalancing analysis"
              compact
              section={{
                title: "",
                rows: result.rebalances.map((row) => ({ date: row.date, turnover: pct.format(row.turnover), cost: money.format(row.cost) }))
              }}
            />
          </ReportSection>
        ) : null}

        <ReportSection title="Formula reference">
          <DataTable caption="Formula reference" compact section={{ title: "", rows: formulaReferenceRows() }} />
        </ReportSection>

        <ReportSection title="Limitations">
          <p>Historical NAV backtest only &mdash; not a forecast, not investment advice. No tax treatment, individual investor timing, unmodeled fund-specific fee changes, or survivorship-bias correction for delisted funds. Drawdown stress scenarios (Section 6) apply a deterministic shock to ending value and are not a probabilistic simulation.</p>
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

function Metric({
  label,
  value,
  sub = "",
  tone,
  emphasis
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "positive" | "negative";
  emphasis?: boolean;
}) {
  const className = ["metricCard", emphasis ? "metricCard-emphasis" : "", tone ? `metricCard-${tone}` : ""].filter(Boolean).join(" ");
  return (
    <div className={className}>
      <span>{label}</span>
      <strong>{value}</strong>
      {sub ? <small>{sub}</small> : null}
    </div>
  );
}

function ClickableMetric(props: { label: string; value: string; sub: string; onClick: () => void }) {
  return (
    <button className="metricCard clickableMetric" onClick={props.onClick} type="button">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
      <small>{props.sub}</small>
    </button>
  );
}

function AxisCurve({ title, series, valueFormat }: { title: string; series: ChartSeries[]; valueFormat: (value: number) => string }) {
  const prepared = useMemo(() => prepareSeries(series), [series]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [hover, setHover] = useState<{ index: number; x: number; y: number } | null>(null);
  const gradientId = useId();

  function handleMove(event: ReactMouseEvent<SVGRectElement>) {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const relativeX = ((event.clientX - rect.left) / rect.width) * 880;
    const length = prepared.pointCount;
    const rawIndex = ((relativeX - 70) / 780) * (length - 1);
    const index = Math.min(length - 1, Math.max(0, Math.round(rawIndex)));
    setHover({ index, x: event.clientX - rect.left, y: event.clientY - rect.top });
  }

  const hoverRows = hover
    ? prepared.paths.map((path, seriesIndex) => ({
        label: path.label,
        color: path.color,
        value: series[seriesIndex]?.valueFormat(prepared.seriesValues[seriesIndex]?.[hover.index] ?? 0) ?? ""
      }))
    : [];
  const hoverDate = hover ? prepared.dates[hover.index] ?? "" : "";
  const hoverPlotX = hover ? xForIndex(hover.index, prepared.pointCount) : 0;

  return (
    <section className="chartPanel">
      <div className="panelHeader compact">
        <div>
          <h3>{title}</h3>
          <p>{prepared.startDate} to {prepared.endDate}</p>
        </div>
        <span className="badge">{valueFormat(prepared.latestValue)}</span>
      </div>
      <div className="chartLegend">
        {series.map((item) => (
          <span key={item.label}><i style={{ background: item.color }} />{item.label}: {item.valueFormat(lastPoint(item.points)?.value ?? 0)}</span>
        ))}
      </div>
      <div className="chartCanvas" ref={containerRef}>
        <svg className="axisChart" viewBox="0 0 880 320" role="img" aria-label={title} preserveAspectRatio="none">
          <defs>
            {prepared.paths.filter((path) => path.area).map((path) => (
              <linearGradient id={`${gradientId}-${slugify(path.label)}`} key={path.label} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={path.color} stopOpacity="0.04" />
                <stop offset="100%" stopColor={path.color} stopOpacity="0.4" />
              </linearGradient>
            ))}
          </defs>
          {prepared.yTicks.map((tick) => (
            <g key={tick.value}>
              <line className="gridLine" x1="70" x2="850" y1={tick.y} y2={tick.y} />
              <text className="axisText" x="62" y={tick.y + 4} textAnchor="end">{valueFormat(tick.value)}</text>
            </g>
          ))}
          {prepared.xTicks.map((tick) => (
            <g key={tick.x}>
              <line className="gridLine vertical" x1={tick.x} x2={tick.x} y1="24" y2="280" />
              <text className="axisText" x={tick.x} y="300" textAnchor="middle">{tick.date}</text>
            </g>
          ))}
          <line className="axisLine" x1="70" x2="850" y1="280" y2="280" />
          <line className="axisLine" x1="70" x2="70" y1="24" y2="280" />
          {prepared.paths.filter((path) => path.area).map((path) => (
            <path d={path.areaD} key={`${path.label}-area`} stroke="none" style={{ fill: `url(#${gradientId}-${slugify(path.label)})` }} />
          ))}
          {prepared.paths.map((path) => (
            <path key={path.label} d={path.d} stroke={path.color} strokeDasharray={path.dashed ? "7 7" : undefined} />
          ))}
          {prepared.endpoints.map((point) => (
            <circle key={point.label} cx={point.x} cy={point.y} r="4" fill={point.color} />
          ))}
          {hover ? (
            <g>
              <line className="crosshairLine" x1={hoverPlotX} x2={hoverPlotX} y1="24" y2="280" />
              {prepared.seriesValues.map((values, seriesIndex) => {
                const value = values[hover.index];
                if (value == null) return null;
                return (
                  <circle
                    key={series[seriesIndex]?.label ?? seriesIndex}
                    cx={hoverPlotX}
                    cy={prepared.yFor(value)}
                    r="4.5"
                    fill="#ffffff"
                    stroke={series[seriesIndex]?.color}
                    strokeWidth="2.5"
                  />
                );
              })}
            </g>
          ) : null}
          <rect
            x="70"
            y="24"
            width="780"
            height="256"
            fill="transparent"
            onMouseMove={handleMove}
            onMouseLeave={() => setHover(null)}
          />
        </svg>
        {hover ? (
          <div
            className="chartTooltip"
            style={{ left: Math.min(Math.max(hover.x, 84), (containerRef.current?.clientWidth ?? 880) - 84), top: 8 }}
          >
            <strong>{hoverDate}</strong>
            {hoverRows.map((row) => (
              <span key={row.label}><i style={{ background: row.color }} />{row.label}: {row.value}</span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="chartStats">
        <span>Min: {valueFormat(prepared.min)}</span>
        <span>Max: {valueFormat(prepared.max)}</span>
        <span>Latest: {valueFormat(prepared.latestValue)}</span>
      </div>
    </section>
  );
}

function xForIndex(index: number, length: number) {
  return 70 + (index / Math.max(1, length - 1)) * 780;
}

function DataTable({ section, compact = false, caption }: { section: TableSection; compact?: boolean; caption?: string }) {
  const rows = section.rows;
  const columns = rows.length ? Object.keys(rows[0]) : [];
  const resolvedCaption = section.title || caption;
  return (
    <div className={compact ? "tablePanel compactTable" : "tablePanel"}>
      {section.title ? <h3>{section.title}</h3> : null}
      <div className="tableScroller">
        <table>
          {resolvedCaption ? <caption className="srOnly">{resolvedCaption}</caption> : null}
          <thead>
            <tr>{columns.map((column) => <th key={column}>{humanize(column)}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => <td key={column}>{formatCell(row[column])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <small>{rows.length} row{rows.length === 1 ? "" : "s"}</small>
    </div>
  );
}

function MonthlyHeatmap({ rows }: { rows: MonthlyGridRow[] }) {
  return (
    <section className="chartPanel">
      <h3>Monthly returns heatmap</h3>
      <div className="monthHeaders">
        <span />
        {["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].map((month) => <span key={month}>{month}</span>)}
      </div>
      {rows.map((row) => (
        <div className="heatRow" key={row.year}>
          <span className="heatYear">{row.year}</span>
          {row.months.map((value, index) => (
            <span
              className="heatCell"
              key={`${row.year}-${index}`}
              title={value == null ? "n/a" : pct.format(value)}
              style={{ background: value == null ? "#eef1f6" : heatColor(value) }}
            >
              {value == null ? "" : `${(value * 100).toFixed(1)}`}
            </span>
          ))}
        </div>
      ))}
    </section>
  );
}

function Histogram({ rows }: { rows: { bin: string; count: number; from: number; to: number }[] }) {
  const maxCount = Math.max(...rows.map((row) => row.count), 1);
  return (
    <div className="histWrap">
      <div className="histLegend">
        <span><i className="histSwatch histSwatch-loss" /> Loss months</span>
        <span><i className="histSwatch histSwatch-gain" /> Gain months</span>
      </div>
      <div className="hist" role="img" aria-label={`Monthly return distribution histogram: ${rows.map((row) => `${row.bin}, ${row.count} months`).join("; ")}`}>
        {rows.map((row) => (
          <div className="histCol" key={row.bin}>
            <span aria-hidden="true" className="histCount">{row.count || ""}</span>
            <div
              aria-hidden="true"
              className={row.from >= 0 ? "histBar histBar-gain" : "histBar histBar-loss"}
              style={{ height: `${Math.max(5, (row.count / maxCount) * 92)}px` }}
              title={`${row.bin}: ${row.count} month${row.count === 1 ? "" : "s"}`}
            />
            <span aria-hidden="true" className="histAxisLabel">{pct.format(row.from)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface ChartSeries {
  label: string;
  points: TimeSeriesPoint[];
  color: string;
  dashed?: boolean;
  area?: boolean;
  valueFormat: (value: number) => string;
}

interface MonthlyGridRow {
  year: number;
  months: (number | null)[];
}

function deriveResult(result: BacktestResult) {
  const portfolioReturns = returnsFromCurve(result.equity_curve);
  const benchmarkReturns = returnsFromCurve(result.benchmark_curve);
  const benchmarkReturnsByDate = new Map(benchmarkReturns.map((row) => [row.date, row.value]));
  const monthlyRows = result.monthly_returns.rows.map((row) => ({
    date: String(row.date),
    portfolio: asNumber(row.return),
    benchmark: benchmarkReturnsByDate.get(String(row.date)) ?? null
  }));
  const rolling = rollingRows(monthlyRows, result.request.risk_free_rate_pct / 100);
  return {
    portfolioReturns,
    benchmarkReturns,
    monthlyRows,
    trailingReturns: trailingRows(monthlyRows),
    rolling,
    annualReturns: annualRows(result, monthlyRows),
    monthlyGrid: monthlyGrid(monthlyRows),
    histogram: histogramRows(monthlyRows.map((row) => row.portfolio)),
    bestMonths: [...monthlyRows].sort((a, b) => b.portfolio - a.portfolio).slice(0, 10).map(monthRow),
    worstMonths: [...monthlyRows].sort((a, b) => a.portfolio - b.portfolio).slice(0, 10).map(monthRow),
    drawdownPeriods: worstDrawdownPeriods(result.drawdown_curve)
  };
}

function returnsFromCurve(points: TimeSeriesPoint[]) {
  const rows: { date: string; value: number }[] = [];
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1]?.value ?? 0;
    const current = points[index]?.value ?? 0;
    rows.push({ date: points[index]?.date ?? "", value: previous ? current / previous - 1 : 0 });
  }
  return rows;
}

function trailingRows(rows: { date: string; portfolio: number; benchmark: number | null }[]) {
  return [
    { label: "1Y", months: 12 },
    { label: "3Y", months: 36 },
    { label: "5Y", months: 60 },
    { label: "Full", months: rows.length }
  ]
    .filter((window) => window.months > 0 && rows.length >= window.months)
    .map((window) => {
      const slice = rows.slice(-window.months);
      const portfolio = annualize(productReturn(slice.map((row) => row.portfolio)), slice.length);
      const benchmarkValues = slice.map((row) => row.benchmark);
      const benchmarkAligned = benchmarkValues.every((value): value is number => value != null);
      const benchmark = benchmarkAligned ? annualize(productReturn(benchmarkValues), benchmarkValues.length) : null;
      return {
        period: window.label,
        portfolio: pct.format(portfolio),
        benchmark: benchmark == null ? "n/a" : pct.format(benchmark),
        excess: benchmark == null ? "n/a" : pct.format(portfolio - benchmark),
        volatility: pct.format(std(slice.map((row) => row.portfolio)) * Math.sqrt(12))
      };
    });
}

function rollingRows(
  rows: { date: string; portfolio: number; benchmark: number | null }[],
  riskFreeRate: number
) {
  const output = [];
  for (let index = 12; index <= rows.length; index += 1) {
    const slice = rows.slice(index - 12, index);
    const portfolioValues = slice.map((row) => row.portfolio);
    const benchmarkValues = slice.map((row) => row.benchmark);
    if (!benchmarkValues.every((value): value is number => value != null)) continue;
    const active = portfolioValues.map((value, i) => value - benchmarkValues[i]);
    const volatility = std(portfolioValues) * Math.sqrt(12);
    // A 12-month window IS one year, so the compounded window return is already
    // the annualized return -- the same geometric, risk-free-adjusted Sharpe the
    // backend reports, rather than an unadjusted arithmetic-mean variant.
    const windowReturn = productReturn(portfolioValues);
    output.push({
      date: rows[index - 1]?.date ?? "",
      return: windowReturn,
      benchmark: productReturn(benchmarkValues),
      volatility,
      sharpe: volatility <= DEGENERACY_TOLERANCE ? null : (windowReturn - riskFreeRate) / volatility,
      tracking_error: std(active) * Math.sqrt(12)
    });
  }
  return output;
}

function annualRows(result: BacktestResult, monthlyRows: { date: string; portfolio: number; benchmark: number | null }[]) {
  return result.annual_returns.rows.map((row) => {
    const year = Number(row.year);
    const yearRows = monthlyRows.filter((item) => item.date.startsWith(String(year)));
    const benchmarkValues = yearRows.map((item) => item.benchmark);
    const benchmarkAligned = yearRows.length > 0 && benchmarkValues.every((value): value is number => value != null);
    const portfolio = asNumber(row.return);
    const benchmark = benchmarkAligned ? productReturn(benchmarkValues) : null;
    return {
      year,
      portfolio: pct.format(portfolio),
      benchmark: benchmark == null ? "n/a" : pct.format(benchmark),
      diff: benchmark == null ? "n/a" : pct.format(portfolio - benchmark)
    };
  });
}

function monthlyGrid(rows: { date: string; portfolio: number }[]): MonthlyGridRow[] {
  const byYear = new Map<number, (number | null)[]>();
  rows.forEach((row) => {
    const date = new Date(`${row.date}T00:00:00`);
    const year = date.getFullYear();
    const month = date.getMonth();
    if (!byYear.has(year)) byYear.set(year, Array.from({ length: 12 }, () => null));
    byYear.get(year)![month] = row.portfolio;
  });
  return [...byYear.entries()].map(([year, months]) => ({ year, months }));
}

function histogramRows(values: number[]) {
  if (!values.length) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = (max - min) / 10 || 0.01;
  const rows = Array.from({ length: 10 }, (_, index) => {
    const from = min + index * width;
    const to = from + width;
    return { from, to, bin: `${pct.format(from)} to ${pct.format(to)}`, count: 0 };
  });
  values.forEach((value) => {
    const index = Math.max(0, Math.min(rows.length - 1, Math.floor((value - min) / width)));
    rows[index].count += 1;
  });
  return rows;
}

function worstDrawdownPeriods(points: TimeSeriesPoint[]) {
  const periods: { peak: string; trough: string; recovery: string; depth: number; months: number }[] = [];
  let start: number | null = null;
  for (let index = 0; index < points.length; index += 1) {
    const value = points[index]?.value ?? 0;
    if (start == null && value < -0.0001) start = Math.max(0, index - 1);
    if (start != null && value >= -0.0001) {
      periods.push(drawdownPeriod(points, start, index));
      start = null;
    }
  }
  if (start != null) periods.push(drawdownPeriod(points, start, points.length - 1));
  return periods.sort((a, b) => a.depth - b.depth).slice(0, 5).map((row) => ({
    peak: row.peak,
    trough: row.trough,
    recovery: row.recovery,
    depth: pct.format(row.depth),
    months: row.months
  }));
}

function drawdownPeriod(points: TimeSeriesPoint[], start: number, end: number) {
  let trough = start;
  for (let index = start; index <= end; index += 1) {
    if ((points[index]?.value ?? 0) < (points[trough]?.value ?? 0)) trough = index;
  }
  return {
    peak: points[start]?.date ?? "",
    trough: points[trough]?.date ?? "",
    recovery: end === points.length - 1 ? "Ongoing" : points[end]?.date ?? "",
    depth: points[trough]?.value ?? 0,
    months: Math.max(0, end - start)
  };
}

function prepareSeries(series: ChartSeries[]) {
  const maxLength = Math.max(1, ...series.map((item) => item.points.length));
  const step = Math.max(1, Math.floor(maxLength / 140));
  const sampledSeries = series.map((item) => ({
    ...item,
    points: item.points.filter((_, index) => index % step === 0 || index === item.points.length - 1)
  }));
  const pointCount = Math.max(1, ...sampledSeries.map((item) => item.points.length));
  const allValues = sampledSeries.flatMap((item) => item.points.map((point) => point.value));
  const min = allValues.length ? Math.min(...allValues) : 0;
  const max = allValues.length ? Math.max(...allValues) : 1;
  const range = max - min || 1;
  const yTicks = Array.from({ length: 6 }, (_, index) => {
    const value = min + (range * index) / 5;
    const y = 280 - ((value - min) / range) * 256;
    return { value, y };
  }).reverse();
  const xFor = (index: number, length: number) => 70 + (index / Math.max(1, length - 1)) * 780;
  const yFor = (value: number) => 280 - ((value - min) / range) * 256;
  const paths = sampledSeries.map((item) => {
    const d = item.points.map((point, index) => `${index ? "L" : "M"} ${xFor(index, item.points.length).toFixed(1)} ${yFor(point.value).toFixed(1)}`).join(" ");
    const baselineY = Math.min(280, Math.max(24, yFor(0)));
    const firstX = xFor(0, item.points.length).toFixed(1);
    const lastX = xFor(item.points.length - 1, item.points.length).toFixed(1);
    return {
      label: item.label,
      color: item.color,
      dashed: item.dashed,
      area: item.area,
      d,
      areaD: item.area && item.points.length ? `${d} L ${lastX} ${baselineY.toFixed(1)} L ${firstX} ${baselineY.toFixed(1)} Z` : ""
    };
  });
  const endpoints = sampledSeries.map((item) => {
    const point = lastPoint(item.points) ?? { date: "", value: 0 };
    return {
      label: item.label,
      color: item.color,
      x: 850,
      y: yFor(point.value)
    };
  });
  const dateSource = sampledSeries.reduce((longest, item) => (item.points.length > longest.length ? item.points : longest), [] as TimeSeriesPoint[]);
  const dates = dateSource.map((point) => point.date);
  const tickCount = Math.min(6, pointCount);
  const xTicks = Array.from({ length: tickCount }, (_, index) => {
    const pointIndex = tickCount > 1 ? Math.round((index * (pointCount - 1)) / (tickCount - 1)) : 0;
    return { x: xFor(pointIndex, pointCount), date: dates[pointIndex] ?? "" };
  });
  const seriesValues = sampledSeries.map((item) => item.points.map((point) => point.value));
  return {
    paths,
    endpoints,
    yTicks,
    xTicks,
    dates,
    seriesValues,
    pointCount,
    yFor,
    min,
    max,
    latestValue: lastPoint(series[0]?.points ?? [])?.value ?? 0,
    startDate: series[0]?.points[0]?.date ?? "",
    endDate: lastPoint(series[0]?.points ?? [])?.date ?? ""
  };
}

function summaryMetrics(result: BacktestResult): SummaryMetric[] {
  const m = result.summary;
  const rows: SummaryMetric[] = [
    { label: "Ending value", value: money.format(m.ending_value), emphasis: true },
    { label: "TWRR CAGR", value: pct.format(m.twrr_cagr), tone: toneOf(m.twrr_cagr) },
    { label: "Volatility", value: pct.format(m.volatility) },
    { label: "Sharpe", value: formatNumber(m.sharpe), tone: m.sharpe === null ? undefined : toneOf(m.sharpe) },
    { label: "Max drawdown", value: pct.format(m.max_drawdown) },
    { label: "Excess vs benchmark", value: formatPercentLike(m.benchmark_excess_return), tone: m.benchmark_excess_return === null ? undefined : toneOf(m.benchmark_excess_return) }
  ];
  if (result.request.cashflow.enabled) {
    rows.push(
      result.request.cashflow.type === "withdrawal"
        ? { label: "Total withdrawn", value: money.format(m.total_withdrawn), sub: m.ending_value > 0 ? "Survived" : "Depleted" }
        : { label: "Total contributed", value: money.format(m.total_contributed) }
    );
  }
  if (result.request.rebalancing.mode !== "none") {
    rows.push({ label: "Rebalance events", value: String(m.rebalance_count), sub: money.format(m.total_costs) + " total cost" });
  }
  return rows;
}

function resultNarrative(result: BacktestResult) {
  const m = result.summary;
  const parts = [`Ending value ${money.format(m.ending_value)}, TWRR CAGR ${pct.format(m.twrr_cagr)}, max drawdown ${pct.format(m.max_drawdown)}.`];
  if (result.request.cashflow.enabled) {
    parts.push(
      result.request.cashflow.type === "withdrawal"
        ? `You withdrew ${money.format(m.total_withdrawn)}; the portfolio ${m.ending_value > 0 ? "remained above zero" : "depleted"}.`
        : `You contributed ${money.format(m.total_contributed)} through SEC fund NAV history.`
    );
  }
  if (result.request.rebalancing.mode !== "none") {
    parts.push(`${m.rebalance_count} rebalance events with total modeled costs of ${money.format(m.total_costs)}.`);
  }
  return parts.join(" ");
}

function resultChecklist(result: BacktestResult) {
  const m = result.summary;
  const rows = [];
  if (result.request.cashflow.enabled) {
    rows.push(
      result.request.cashflow.type === "withdrawal"
        ? { question: "Did the portfolio survive withdrawals?", result: m.ending_value > 0 ? "Survived" : "Depleted", evidence_tab: "Cashflows" }
        : { question: "How much did the investor put in?", result: money.format(m.total_contributed), evidence_tab: "Cashflows" }
    );
  }
  if (result.request.rebalancing.mode !== "none") {
    rows.push({ question: "How often did the strategy trade?", result: `${m.rebalance_count} events`, evidence_tab: "Rebalancing" });
  }
  rows.push(
    { question: "Did allocation outperform benchmark?", result: `Excess ${formatPercentLike(m.benchmark_excess_return)}`, evidence_tab: "Metrics" },
    { question: "Benchmark risk acceptable?", result: `Beta ${formatNumber(findRiskValue(result, "beta"))}, alpha ${formatPercentLike(findRiskValue(result, "alpha"))}`, evidence_tab: "Metrics" },
    { question: "Worst historical loss visible?", result: `Max drawdown ${pct.format(m.max_drawdown)}`, evidence_tab: "Drawdown" },
    { question: "Diversification visible?", result: `${result.diversification.rows.length} diversification rows`, evidence_tab: "Metrics" },
    { question: "Research report ready?", result: "Inputs, formulas, results, limitations", evidence_tab: "Report" }
  );
  return rows;
}

function assumptionRows(result: BacktestResult) {
  const request = result.request;
  return [
    { input: "Date range", value: `${request.start_date} to ${request.end_date}` },
    { input: "Portfolio", value: request.assets.map((asset) => `${asset.display_name} ${asset.weight}%`).join("; ") },
    { input: "Benchmark", value: request.benchmark_proj_id },
    { input: "Risk-free rate", value: `${request.risk_free_rate_pct}% / yr` },
    { input: "Cashflow", value: request.cashflow.enabled ? `${request.cashflow.type} ${money.format(request.cashflow.amount)} ${request.cashflow.frequency} ${request.cashflow.timing}` : "Disabled" },
    { input: "Rebalancing", value: request.rebalancing.mode },
    { input: "Costs", value: `${request.costs.transaction_bps} bps transaction, ${request.costs.slippage_bps} bps slippage, ${request.costs.annual_drag_pct}% annual drag` },
    { input: "Data source", value: "SEC Open Data cached NAV, nav_per_unit" },
    { input: "Price basis", value: "SEC NAV per unit; adjusted close and dividend switches are not stock-price assumptions in this project" }
  ];
}

function keyMetricRows(result: BacktestResult) {
  const m = result.summary;
  // The annualization factor depends on the run's own NAV alignment frequency
  // -- daily mode uses sqrt(252), not sqrt(12) -- so the formula text shown
  // must match how *this* run's numbers were actually computed.
  const periodsPerYear = result.request.data.frequency === "daily" ? 252 : 12;
  const periodLabel = result.request.data.frequency === "daily" ? "daily" : "monthly";
  return [
    { metric: "Ending value", value: money.format(m.ending_value), formula: "Portfolio value after returns, cashflows, costs, and rebalancing" },
    { metric: "TWRR", value: pct.format(m.twrr), formula: "Product of linked sub-period returns minus 1" },
    { metric: "TWRR CAGR", value: pct.format(m.twrr_cagr), formula: "(1 + TWRR)^(1/years) - 1" },
    { metric: "IRR (money-weighted)", value: formatPercentLike(m.irr), formula: "Solve for r where sum(cashflow_i / (1+r)^year_i) = 0; diverges from CAGR when flow timing matters" },
    { metric: "Volatility", value: pct.format(m.volatility), formula: `Std(${periodLabel} returns) * sqrt(${periodsPerYear})` },
    { metric: "Sharpe ratio", value: formatNumber(m.sharpe), formula: "Annualized excess return / annualized volatility" },
    { metric: "Sortino ratio", value: formatNumber(m.sortino), formula: "Annualized excess return / downside deviation (penalises losses only)" },
    { metric: "Calmar ratio", value: formatNumber(m.calmar), formula: "Annualized return / absolute maximum drawdown" },
    { metric: "Value at Risk (95%)", value: formatPercentLike(m.var_95), formula: `Historical 5th percentile ${periodLabel} loss (non-parametric)` },
    { metric: "Value at Risk (99%)", value: formatPercentLike(m.var_99), formula: `Historical 1st percentile ${periodLabel} loss (non-parametric)` },
    { metric: "Maximum drawdown", value: pct.format(m.max_drawdown), formula: "Value / running peak - 1" },
    { metric: "Benchmark excess return", value: formatPercentLike(m.benchmark_excess_return), formula: "Cumulative portfolio TWRR - cumulative benchmark return over matched periods" },
    { metric: "Total contributed", value: money.format(m.total_contributed), formula: "Initial capital + sum of applied positive cashflows" },
    { metric: "Total withdrawn", value: money.format(m.total_withdrawn), formula: "Sum of withdrawal cashflow rules" },
    { metric: "Total costs", value: money.format(m.total_costs), formula: "Money value traded * (transaction + slippage bps) summed across rebalances, plus annual drag where applicable" }
  ];
}

function buildNetInvestedCurve(result: BacktestResult) {
  let invested = result.request.initial_capital;
  const cashflowsByDate = new Map<string, number>();
  result.cashflows.forEach((cashflow) => cashflowsByDate.set(cashflow.date, (cashflowsByDate.get(cashflow.date) ?? 0) + cashflow.amount));
  return result.equity_curve.map((point) => {
    invested += cashflowsByDate.get(point.date) ?? 0;
    return { date: point.date, value: invested };
  });
}

function milestoneRows(result: BacktestResult, netInvested: TimeSeriesPoint[]) {
  const indexes = [0, 0.25, 0.5, 0.75, 1].map((ratio) => Math.min(result.equity_curve.length - 1, Math.round((result.equity_curve.length - 1) * ratio)));
  const benchmarkByDate = new Map(result.benchmark_curve.map((point) => [point.date, point.value]));
  return indexes.map((index) => {
    const equityPoint = result.equity_curve[index];
    const benchmarkValue = equityPoint ? benchmarkByDate.get(equityPoint.date) : undefined;
    return {
      date: equityPoint?.date,
      portfolio: money.format(equityPoint?.value ?? 0),
      benchmark: benchmarkValue == null ? "n/a" : money.format(benchmarkValue),
      net_invested: money.format(netInvested[index]?.value ?? 0),
      profit_over_invested: money.format((equityPoint?.value ?? 0) - (netInvested[index]?.value ?? 0))
    };
  });
}

function stressRows(result: BacktestResult) {
  return [-0.1, -0.2, -0.35, result.summary.max_drawdown].map((shock) => ({
    scenario: shock === result.summary.max_drawdown ? "Repeat historical max drawdown" : `${pct.format(shock)} portfolio shock`,
    impact: pct.format(shock),
    value_after_stress: money.format(result.summary.ending_value * (1 + shock)),
    note: shock === result.summary.max_drawdown ? "Historical path stress from SEC NAV data" : "Deterministic shock applied to ending value"
  }));
}

function formulaReferenceRows() {
  return [
    { metric: "Simple return", formula: "r_t = NAV_t / NAV_(t-1) - 1", source: "Standard arithmetic" },
    { metric: "Time-weighted return (TWRR)", formula: "TWRR = Prod(1 + r_t) - 1, cashflow periods excluded from r_t", source: "GIPS Standards (CFA Institute)" },
    { metric: "TWRR CAGR", formula: "(1 + TWRR)^(1/years) - 1", source: "Standard annualization" },
    { metric: "IRR (money-weighted)", formula: "Solve for r: sum(cashflow_i / (1+r)^year_i) = 0, investor-perspective flows at nominal elapsed years", source: "GIPS Standards (CFA Institute)" },
    { metric: "Annualized volatility", formula: "Std(period returns, sample, ddof=1) * sqrt(m); m = 12 (monthly) or 252 (daily)", source: "Standard sample statistics" },
    { metric: "Sharpe ratio", formula: "(Annualized return - risk-free rate) / annualized volatility", source: "Sharpe (1966, 1994)" },
    { metric: "Sortino ratio", formula: "(Annualized return - risk-free rate) / downside deviation (losses only)", source: "Sortino & Price (1994)" },
    { metric: "Calmar ratio", formula: "Annualized return / |maximum drawdown|", source: "Young (1991)" },
    { metric: "Value at Risk (historical)", formula: "max(0, -percentile(period returns, (1 - confidence) * 100))", source: "Jorion; CFA Institute" },
    { metric: "Maximum drawdown", formula: "min(Value_t / running_peak_t - 1)", source: "Magdon-Ismail & Atiya" },
    { metric: "Beta", formula: "Cov(portfolio, benchmark) / Var(benchmark), sample", source: "Sharpe (1964); Lintner (1965)" },
    { metric: "Alpha (CAPM residual)", formula: "portfolio CAGR - (risk-free + beta * (benchmark CAGR - risk-free))", source: "Sharpe (1964); Lintner (1965)" },
    { metric: "Tracking error", formula: "Std(portfolio_return - benchmark_return, sample, ddof=1) * sqrt(m); m = 12 (monthly) or 252 (daily)", source: "CFA Institute (Kidd, 2012)" },
    { metric: "Information ratio", formula: "(portfolio CAGR - benchmark CAGR) / tracking error", source: "CFA Institute (Kidd, 2012)" },
    { metric: "Correlation", formula: "Pearson correlation of aligned period returns", source: "Markowitz (1952)" },
    { metric: "Rebalance turnover", formula: "sum(|target_value_i - current_value_i|) / 2 / portfolio_value, one-way fraction", source: "Standard bookkeeping" },
    { metric: "Rebalance cost", formula: "money turnover * (transaction_bps + slippage_bps) / 10,000", source: "Standard bookkeeping" }
  ];
}

function benchmarkDecompositionRows(result: BacktestResult, derived: ReturnType<typeof deriveResult>) {
  return [
    { metric: "CAGR", portfolio: pct.format(result.summary.twrr_cagr), benchmark_active_view: trailingBenchmarkFull(derived), interpretation: "Long-run compounded return" },
    { metric: "Volatility", portfolio: pct.format(result.summary.volatility), benchmark_active_view: `Correlation ${formatNumber(findRiskValue(result, "correlation"))}`, interpretation: "Total risk and market linkage" },
    { metric: "Beta", portfolio: formatNumber(findRiskValue(result, "beta")), benchmark_active_view: `Alpha ${formatPercentLike(findRiskValue(result, "alpha"))}`, interpretation: "Systematic exposure and residual return" },
    { metric: "Tracking error", portfolio: formatPercentLike(findRiskValue(result, "tracking_error")), benchmark_active_view: `Information ratio ${formatNumber(findRiskValue(result, "information_ratio"))}`, interpretation: "Active risk efficiency" }
  ];
}

function stressInterpretationRows(result: BacktestResult, derived: ReturnType<typeof deriveResult>) {
  const values = result.equity_curve.map((point) => point.value);
  return [
    { check: "Capital at risk", result: `${money.format(Math.max(...values) - Math.min(...values))} peak-to-trough path range in SEC NAV history` },
    { check: "Recovery pressure", result: `${derived.drawdownPeriods[0]?.months ?? 0} months in the deepest drawdown period` },
    { check: "Benchmark stress", result: `Portfolio beta ${formatNumber(findRiskValue(result, "beta"))}; benchmark shocks are translated through historical beta` }
  ];
}

const CORRELATION_PALETTE = ["#5b21d6", "#0ea5e9", "#92620a", "#b42318", "#0f766e", "#6b7280"];

function rollingCorrelationSeries(result: BacktestResult): ChartSeries[] {
  const byPair = new Map<string, { label: string; points: TimeSeriesPoint[] }>();
  for (const row of result.rolling_correlation) {
    if (row.correlation === null) continue;
    const key = `${row.asset_a} vs ${row.asset_b}`;
    if (!byPair.has(key)) byPair.set(key, { label: key, points: [] });
    byPair.get(key)!.points.push({ date: row.date, value: row.correlation });
  }
  return [...byPair.values()].map((series, index) => ({
    label: series.label,
    points: series.points,
    color: CORRELATION_PALETTE[index % CORRELATION_PALETTE.length],
    valueFormat: number.format
  }));
}

function assetRows(result: BacktestResult) {
  return result.asset_metrics.rows.map((row) => ({
    fund: row.fund,
    proj_id: row.proj_id,
    target: pct.format(asNumber(row.target_weight_pct) / 100),
    final: pct.format(asNumber(row.final_weight_pct) / 100),
    drift: formatPercentLike(asNumber(row.drift_pct) / 100),
    cagr: pct.format(asNumber(row.cagr)),
    volatility: pct.format(asNumber(row.volatility))
  }));
}

function yearlyCashflowRows(result: BacktestResult) {
  const byYear = new Map<string, { year: string; contributions: number; withdrawals: number; events: number }>();
  result.cashflows.forEach((cashflow) => {
    const year = cashflow.date.slice(0, 4);
    if (!byYear.has(year)) byYear.set(year, { year, contributions: 0, withdrawals: 0, events: 0 });
    const row = byYear.get(year)!;
    if (cashflow.amount >= 0) row.contributions += cashflow.amount;
    else row.withdrawals += Math.abs(cashflow.amount);
    row.events += 1;
  });
  return [...byYear.values()].map((row) => ({
    year: row.year,
    contributions: money.format(row.contributions),
    withdrawals: money.format(row.withdrawals),
    events: row.events
  }));
}

function monthRow(row: { date: string; portfolio: number; benchmark: number | null }) {
  return {
    date: row.date,
    portfolio: pct.format(row.portfolio),
    benchmark: row.benchmark == null ? "n/a" : pct.format(row.benchmark),
    diff: row.benchmark == null ? "n/a" : pct.format(row.portfolio - row.benchmark)
  };
}

function trailingBenchmarkFull(derived: ReturnType<typeof deriveResult>) {
  const full = derived.trailingReturns.find((row) => row.period === "Full");
  return full?.benchmark ?? "n/a";
}

function asNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function mean(values: number[]) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

// Sample (n-1) standard deviation, matching annualized_volatility on the
// backend. Dividing by n instead would make this table disagree with the
// volatility reported on the Summary tab.
function std(values: number[]) {
  if (values.length < 2) return 0;
  const average = mean(values);
  const sumSquares = values.reduce((total, value) => total + (value - average) ** 2, 0);
  return Math.sqrt(sumSquares / (values.length - 1));
}

function productReturn(values: number[]) {
  return values.reduce((total, value) => total * (1 + value), 1) - 1;
}

function annualize(totalReturn: number, months: number) {
  if (!months) return 0;
  return (1 + totalReturn) ** (12 / months) - 1;
}

function heatColor(value: number) {
  const opacity = Math.max(0.16, Math.min(0.9, Math.abs(value) / 0.08 + 0.12));
  return value >= 0 ? `rgb(19 122 79 / ${opacity})` : `rgb(180 35 24 / ${opacity})`;
}

// Correlation ranges -1..1 (not the +/-8% monthly-return scale heatColor was
// tuned for), so it needs its own opacity mapping rather than reusing heatColor.
function correlationColor(value: number) {
  const opacity = Math.max(0.14, Math.min(0.85, Math.abs(value)));
  return value >= 0 ? `rgb(19 122 79 / ${opacity})` : `rgb(180 35 24 / ${opacity})`;
}

function CorrelationMatrix({ result }: { result: BacktestResult }) {
  const displayNameById = new Map(result.request.assets.map((asset) => [asset.proj_id, asset.display_name]));
  const ids = result.request.assets.map((asset) => asset.proj_id);
  const correlationByPair = new Map<string, number | null>();
  result.diversification.rows.forEach((row) => {
    const a = String(row.asset_a);
    const b = String(row.asset_b);
    correlationByPair.set(`${a}|${b}`, row.correlation as number | null);
    correlationByPair.set(`${b}|${a}`, row.correlation as number | null);
  });
  return (
    <div className="tableScroller">
      <table className="correlationMatrix">
        <caption className="srOnly">Correlation matrix between every pair of portfolio funds</caption>
        <thead>
          <tr>
            <th scope="col" />
            {ids.map((id) => <th key={id} scope="col">{displayNameById.get(id) ?? id}</th>)}
          </tr>
        </thead>
        <tbody>
          {ids.map((rowId) => (
            <tr key={rowId}>
              <th scope="row">{displayNameById.get(rowId) ?? rowId}</th>
              {ids.map((colId) => {
                const value = rowId === colId ? 1 : correlationByPair.get(`${rowId}|${colId}`) ?? null;
                return (
                  <td key={colId} style={{ background: value == null ? undefined : correlationColor(value) }}>
                    {value == null ? "n/a" : number.format(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatCell(value: unknown) {
  if (value == null) return "n/a";
  if (typeof value === "number") {
    if (Math.abs(value) <= 1) return value.toFixed(4);
    if (Number.isInteger(value) && value >= 1000 && value <= 9999) return String(value);
    return number.format(value);
  }
  return String(value);
}

function findRiskValue(result: BacktestResult, metric: string) {
  const row = result.risk_metrics.rows.find((item) => String(item.metric).toLowerCase() === metric);
  return typeof row?.value === "number" ? row.value : null;
}

function formatNumber(value: number | null) {
  return value == null || Number.isNaN(value) ? "n/a" : value.toFixed(2);
}

function formatPercentLike(value: number | null) {
  return value == null || Number.isNaN(value) ? "n/a" : pct.format(value);
}

function lastDate(points: TimeSeriesPoint[]) {
  return lastPoint(points)?.date ?? "";
}

function lastPoint<T>(items: T[]) {
  return items.length ? items[items.length - 1] : undefined;
}

function ulcerIndex(points: TimeSeriesPoint[]) {
  if (!points.length) return null;
  return Math.sqrt(points.reduce((sum, point) => sum + point.value ** 2, 0) / points.length);
}

function humanize(value: string) {
  return value.replace(/_/g, " ");
}

function downloadJson(result: BacktestResult) {
  downloadText(`${result.run_id}.json`, JSON.stringify(result, null, 2), "application/json");
}

function reportMarkdown(result: BacktestResult, derived: ReturnType<typeof deriveResult>) {
  const hasCashflow = result.request.cashflow.enabled;
  const hasRebalancing = result.request.rebalancing.mode !== "none";
  const sections: { title: string; body: string }[] = [
    { title: "1. Research question", body: resultNarrative(result) },
    {
      title: "2. Data and methodology",
      body: `All returns are computed from cached SEC Open Data mutual fund NAV series (${result.request.data.frequency === "daily" ? "daily, business-day frequency, m = 252 periods/year" : "month-end frequency, m = 12 periods/year"}). No mock, simulated, or forecast price series are used. Fund period returns use simple returns r_t = NAV_t / NAV_(t-1) - 1; missing NAV observations are never forward-filled into a fabricated return. Portfolio time-weighted return removes external cashflows using the configured timing so contributions/withdrawals do not themselves create investment return.`
    },
    { title: "3. Portfolio specification", body: markdownTable(assumptionRows(result)) },
    { title: "4. Performance results", body: markdownTable(keyMetricRows(result)) },
    {
      title: "5. Risk and benchmark analysis",
      body: `${markdownTable(result.risk_metrics.rows)}\n\n${markdownTable(benchmarkDecompositionRows(result, derived))}`
    },
    {
      title: "6. Drawdown analysis",
      body: `${markdownTable(stressRows(result))}\n\n${markdownTable(derived.drawdownPeriods)}`
    },
    { title: "7. Diversification and correlation", body: markdownTable(result.diversification.rows) },
    { title: "8. Asset-level attribution", body: markdownTable(assetRows(result)) }
  ];
  if (hasCashflow) {
    sections.push({ title: "9. Cashflow analysis", body: markdownTable(yearlyCashflowRows(result)) });
  }
  if (hasRebalancing) {
    sections.push({
      title: hasCashflow ? "10. Rebalancing analysis" : "9. Rebalancing analysis",
      body: markdownTable(result.rebalances.map((row) => ({ date: row.date, turnover: pct.format(row.turnover), cost: money.format(row.cost) })))
    });
  }
  sections.push({ title: "Formula reference", body: markdownTable(formulaReferenceRows()) });
  sections.push({
    title: "Limitations",
    body: "Historical NAV backtest only — not a forecast, not investment advice. No tax treatment, individual investor timing, unmodeled fund-specific fee changes, or survivorship-bias correction for delisted funds. Drawdown stress scenarios apply a deterministic shock to ending value and are not a probabilistic simulation."
  });

  const header = `# Research Report — ${result.request.start_date} to ${result.request.end_date}\n\nRun ${result.run_id} — generated ${result.created_at} — SEC Open Data, NAV per unit`;
  return [header, ...sections.map((section) => `## ${section.title}\n\n${section.body}`)].join("\n\n");
}

function markdownTable(rows: Record<string, unknown>[]) {
  if (!rows.length) return "_No rows._";
  const columns = Object.keys(rows[0]);
  const header = `| ${columns.map(humanize).join(" | ")} |`;
  const divider = `| ${columns.map(() => "---").join(" | ")} |`;
  const body = rows.map((row) => `| ${columns.map((column) => String(row[column] ?? "")).join(" | ")} |`).join("\n");
  return [header, divider, body].join("\n");
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
