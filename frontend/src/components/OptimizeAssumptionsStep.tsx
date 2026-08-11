import { useState } from "react";
import { Play, Plus, Trash2 } from "lucide-react";
import { estimateEquilibriumReturns } from "../lib/blackLittermanPreview";
import type { SecFund } from "../types/backtest";
import { ASSET_GROUP_IDS } from "../types/optimize";
import type {
  AssetGroup,
  AssetGroupId,
  BlackLittermanView,
  CompareAgainst,
  CovarianceMethod,
  DataFrequency,
  ObjectiveGoal,
  OptimizeRequest,
  ReturnEstimationMethod,
  RiskMeasure,
  TailConfidence,
  ViewConfidence,
  ViewType
} from "../types/optimize";

interface Props {
  active: boolean;
  request: OptimizeRequest;
  funds: SecFund[];
  error: string;
  loading: boolean;
  onChange: (request: OptimizeRequest) => void;
  onBack: () => void;
  onRun: () => void;
  // Longest gap-free window for the selected funds, computed server-side
  // (GET /api/funds/testable-range) -- same landmine fix as the sibling
  // backtester's AssumptionsStep: a client-side nav_start/nav_end
  // intersection would miss gaps inside the range.
  testableRange: { start: string | null; end: string | null };
}

// docs/mock-ui-spec.md 2a: scoped down from PV's full 15-goal list to what
// riskfolio-lib supports and this project's decided scope. Min Volatility's
// title/blurb spell out "at a target return" -- mathematically, argmin(sigma)
// and argmin(sigma^2) are the same portfolio, so without a target return
// this card would be indistinguishable from Minimize Variance (GMV).
const OBJECTIVES: Array<{ id: ObjectiveGoal; title: string; blurb: string }> = [
  { id: "max_sharpe", title: "Maximize Sharpe Ratio", blurb: "Best risk-adjusted return across the shortlist." },
  { id: "min_volatility", title: "Minimize Volatility at a Target Return", blurb: "Lowest risk among mixes that hit the return you set." },
  { id: "max_return_target_vol", title: "Max Return, Target Volatility", blurb: "Highest return subject to a volatility ceiling you set." },
  { id: "min_variance", title: "Minimize Variance (GMV)", blurb: "The unconstrained global minimum-variance portfolio." },
  { id: "risk_parity", title: "Risk Parity", blurb: "Equalize each fund's contribution to total risk." },
  { id: "hrp", title: "Hierarchical Risk Parity", blurb: "Cluster-based allocation, no covariance inversion." },
  { id: "black_litterman", title: "Black-Litterman", blurb: "Blend market equilibrium with your own views." }
];

// docs/mock-ui-spec.md 2a: per-measure rationale, not just "legibility" --
// Std Dev is riskfolio-lib's own default rm; Semi-variance is Markowitz's
// own preferred alternative; CVaR is the measure gaining consistent
// adoption among risk managers; CDaR ties to this project's sibling
// backtester already shipping a full Drawdown tab.
const RISK_MEASURES: Array<{ id: RiskMeasure; label: string }> = [
  { id: "std_dev", label: "Standard Deviation" },
  { id: "semi_variance", label: "Semi-Variance (downside only)" },
  { id: "cvar", label: "CVaR (Conditional Value-at-Risk)" },
  { id: "cdar", label: "CDaR (Conditional Drawdown-at-Risk)" }
];

const RANGE_PRESETS: Array<{ label: string; years: number | "max" }> = [
  { label: "1Y", years: 1 },
  { label: "3Y", years: 3 },
  { label: "5Y", years: 5 },
  { label: "Max", years: "max" }
];

function shiftYears(dateStr: string, years: number): string {
  const d = new Date(dateStr);
  d.setFullYear(d.getFullYear() + years);
  return d.toISOString().slice(0, 10);
}

let viewSeq = 0;
function nextViewKey() {
  viewSeq += 1;
  return `view-${viewSeq}`;
}

export function OptimizeAssumptionsStep({ active, request, funds, error, loading, onChange, onBack, onRun, testableRange }: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const isBlackLitterman = request.goal === "black_litterman";
  const isTargetVol = request.goal === "max_return_target_vol";
  const isMinVolatility = request.goal === "min_volatility";
  const isTailRisk = request.riskMeasure === "cvar" || request.riskMeasure === "cdar";
  const selectedFunds = request.funds;
  const canRun = selectedFunds.length >= 2 && !loading;

  function patch(next: Partial<OptimizeRequest>) {
    onChange({ ...request, ...next });
  }

  function patchConstraints(next: Partial<OptimizeRequest["constraints"]>) {
    onChange({ ...request, constraints: { ...request.constraints, ...next } });
  }

  function patchTimePeriod(next: Partial<OptimizeRequest["timePeriod"]>) {
    onChange({ ...request, timePeriod: { ...request.timePeriod, ...next } });
  }

  function applyRangePreset(years: number | "max") {
    const end = testableRange.end ?? request.timePeriod.endDate;
    const start = years === "max" ? (testableRange.start ?? request.timePeriod.startDate) : shiftYears(end, -years);
    patchTimePeriod({ startDate: testableRange.start && start < testableRange.start ? testableRange.start : start, endDate: end });
  }

  function setExpectedReturnOverride(projId: string, value: number) {
    onChange({ ...request, expectedReturnOverrides: { ...request.expectedReturnOverrides, [projId]: value } });
  }

  function setVolatilityOverride(projId: string, value: number) {
    onChange({ ...request, volatilityOverrides: { ...request.volatilityOverrides, [projId]: value } });
  }

  function correlationKey(projId1: string, projId2: string): string {
    return [projId1, projId2].sort().join("|");
  }

  function setCorrelationOverride(projId1: string, projId2: string, value: number) {
    const clamped = Math.max(-1, Math.min(1, value));
    onChange({ ...request, correlationOverrides: { ...request.correlationOverrides, [correlationKey(projId1, projId2)]: clamped } });
  }

  function patchAssetGroup(id: AssetGroupId, next: Partial<AssetGroup>) {
    onChange({ ...request, assetGroups: { ...request.assetGroups, [id]: { ...request.assetGroups[id], ...next } } });
  }

  function setGoal(goal: ObjectiveGoal) {
    const wasBlackLitterman = request.goal === "black_litterman";
    const blackLitterman = goal === "black_litterman"
      ? (request.blackLitterman ?? { riskAversion: 2.5, tau: 0.05, benchmarkExpectedReturnPct: 7, views: [] })
      : null;
    // The Expected-return method select's `value` prop already forces the
    // "Black-Litterman posterior" option to *display* as selected whenever
    // goal is black_litterman (it's disabled while that's true) -- but
    // request.returnMethod itself was never actually written, so a report
    // generated in this state printed "historical mean" or whatever it was
    // before, silently disagreeing with what the dropdown showed selected.
    // Keep the two in sync for real: set it going in, and put a sane
    // default back going out (black_litterman_posterior has no meaning
    // once BL isn't the objective anymore).
    const returnMethod = goal === "black_litterman"
      ? "black_litterman_posterior" as const
      : wasBlackLitterman
        ? "historical_mean" as const
        : request.returnMethod;
    patch({ goal, blackLitterman, returnMethod });
  }

  function patchBl(next: Partial<OptimizeRequest["blackLitterman"]>) {
    if (!request.blackLitterman) return;
    patch({ blackLitterman: { ...request.blackLitterman, ...next } });
  }

  function addView() {
    if (!request.blackLitterman) return;
    const view: BlackLittermanView = {
      key: nextViewKey(),
      assetProjId1: selectedFunds[0]?.proj_id ?? "",
      viewType: "absolute",
      assetProjId2: null,
      adjustedPerformancePct: 8,
      confidence: 50
    };
    patchBl({ views: [...request.blackLitterman.views, view] });
  }

  function updateView(key: string, next: Partial<BlackLittermanView>) {
    if (!request.blackLitterman) return;
    patchBl({ views: request.blackLitterman.views.map((v) => (v.key === key ? { ...v, ...next } : v)) });
  }

  function removeView(key: string) {
    if (!request.blackLitterman) return;
    patchBl({ views: request.blackLitterman.views.filter((v) => v.key !== key) });
  }

  return (
    <div className={active ? "page active" : "page"}>
      <div className="page-head">
        <h1>Set the optimization objective</h1>
        <p>Choose what "optimal" means for this shortlist, then set constraints. Every field here maps to a documented method in <code>docs/optimization-assumptions.md</code>.</p>
      </div>

      {/* 1. Data and time period */}
      <div className="card">
        <div className="section-title">Data and time period</div>
        <div className="range-presets">
          {RANGE_PRESETS.map((preset) => (
            <button className="btn btn-chip" key={preset.label} onClick={() => applyRangePreset(preset.years)} type="button">
              {preset.label}
            </button>
          ))}
        </div>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="periodStart">Start date</label>
            <input
              className="field"
              id="periodStart"
              max={testableRange.end ?? undefined}
              min={testableRange.start ?? undefined}
              onChange={(event) => patchTimePeriod({ startDate: event.target.value })}
              type="date"
              value={request.timePeriod.startDate}
            />
          </div>
          <div className="form-field">
            <label htmlFor="periodEnd">End date</label>
            <input
              className="field"
              id="periodEnd"
              max={testableRange.end ?? undefined}
              min={testableRange.start ?? undefined}
              onChange={(event) => patchTimePeriod({ endDate: event.target.value })}
              type="date"
              value={request.timePeriod.endDate}
            />
          </div>
          <div className="form-field">
            <label htmlFor="dataFrequency">Data frequency</label>
            <select
              className="field"
              id="dataFrequency"
              onChange={(event) => patch({ dataFrequency: event.target.value as DataFrequency })}
              value={request.dataFrequency}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
        </div>
      </div>

      {/* 2. Objective -- comes before Input estimation to match how PV's own
          live optimize-portfolio form orders these (Time Period ->
          Optimization Goal -> the historical-returns/robust toggles), and
          because deciding intent ("what do I want") before configuration
          detail ("how should inputs be estimated") is the more natural
          order for a first-time user. */}
      <div className="card">
        <div className="section-title">Objective</div>
        <div className="obj-grid">
          {OBJECTIVES.map((objective) => (
            <button
              className={request.goal === objective.id ? "obj-card selected" : "obj-card"}
              key={objective.id}
              onClick={() => setGoal(objective.id)}
              type="button"
            >
              <h3>{objective.title}</h3>
              <p className="q">{objective.blurb}</p>
            </button>
          ))}
        </div>

        <div className="section-title" style={{ marginTop: 20 }}>Risk measure</div>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="riskMeasure">Risk measure</label>
            <select
              className="field"
              id="riskMeasure"
              onChange={(event) => patch({ riskMeasure: event.target.value as RiskMeasure })}
              value={request.riskMeasure}
            >
              {RISK_MEASURES.map((measure) => (
                <option key={measure.id} value={measure.id}>{measure.label}</option>
              ))}
            </select>
          </div>
          {isTailRisk ? (
            <div className="form-field">
              <label htmlFor="tailConfidence">Confidence level</label>
              <select
                className="field"
                id="tailConfidence"
                onChange={(event) => patch({ tailConfidence: Number(event.target.value) as TailConfidence })}
                value={request.tailConfidence}
              >
                <option value={95}>95%</option>
                <option value={97.5}>97.5%</option>
                <option value={99}>99%</option>
              </select>
            </div>
          ) : null}
          {isTargetVol ? (
            <div className="form-field">
              <label htmlFor="targetVol">Targeted annual volatility (%)</label>
              <input
                className="field num"
                id="targetVol"
                min={0.1}
                onChange={(event) => patch({ targetAnnualVolatilityPct: Number(event.target.value) })}
                step={0.1}
                type="number"
                value={request.targetAnnualVolatilityPct ?? 10}
              />
            </div>
          ) : null}
          {isMinVolatility ? (
            <div className="form-field">
              <label htmlFor="targetReturn">Targeted annual return (%)</label>
              <input
                className="field num"
                id="targetReturn"
                onChange={(event) => patch({ targetAnnualReturnPct: Number(event.target.value) })}
                step={0.1}
                type="number"
                value={request.targetAnnualReturnPct ?? 6}
              />
            </div>
          ) : null}
        </div>
      </div>

      {isBlackLitterman && request.blackLitterman ? (
        <BlackLittermanCard
          bl={request.blackLitterman}
          patchBl={patchBl}
          request={request}
          selectedFunds={selectedFunds}
          onAddView={addView}
          onRemoveView={removeView}
          onUpdateView={updateView}
        />
      ) : null}

      {/* 3. Input estimation (mu, Sigma) */}
      <div className="card">
        <div className="section-title">Input estimation (expected return &amp; risk)</div>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="returnMethod">Expected-return method</label>
            <select
              className="field"
              disabled={isBlackLitterman}
              id="returnMethod"
              onChange={(event) => patch({ returnMethod: event.target.value as ReturnEstimationMethod })}
              value={isBlackLitterman ? "black_litterman_posterior" : request.returnMethod}
            >
              <option value="historical_mean">Historical mean</option>
              <option value="capm_implied">CAPM-implied</option>
              <option value="black_litterman_posterior">Black-Litterman posterior</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="covarianceMethod">Covariance estimation</label>
            <select
              className="field"
              id="covarianceMethod"
              onChange={(event) => patch({ covarianceMethod: event.target.value as CovarianceMethod })}
              value={request.covarianceMethod}
            >
              <option value="sample">Sample</option>
              <option value="shrinkage">Shrinkage (toward constant correlation)</option>
              <option value="ewma">EWMA</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="robustOptimization">Robust Optimization</label>
            <select
              className="field"
              id="robustOptimization"
              onChange={(event) => patch({ robustOptimization: event.target.value === "true" })}
              value={String(request.robustOptimization)}
            >
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="useHistoricalReturns">Use historical returns</label>
            <select
              className="field"
              id="useHistoricalReturns"
              onChange={(event) => patch({ useHistoricalReturns: event.target.value === "true" })}
              value={String(request.useHistoricalReturns)}
            >
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="useHistoricalVolatility">Use historical volatility</label>
            <select
              className="field"
              id="useHistoricalVolatility"
              onChange={(event) => patch({ useHistoricalVolatility: event.target.value === "true" })}
              value={String(request.useHistoricalVolatility)}
            >
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="useHistoricalCorrelations">Use historical correlations</label>
            <select
              className="field"
              id="useHistoricalCorrelations"
              onChange={(event) => patch({ useHistoricalCorrelations: event.target.value === "true" })}
              value={String(request.useHistoricalCorrelations)}
            >
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </div>
        </div>

        {!request.useHistoricalReturns || !request.useHistoricalVolatility ? (
          <>
            <div className="section-title" style={{ marginTop: 20 }}>Expected return &amp; volatility per fund</div>
            <div className="holdings-table">
              <div className="holdings-head" style={{ gridTemplateColumns: "1fr 140px 140px" }}>
                <span>Fund</span>
                <span>Expected return (%)</span>
                <span>Expected volatility (%)</span>
              </div>
              {selectedFunds.map((fund) => (
                <div className="holdings-row" key={fund.proj_id} style={{ gridTemplateColumns: "1fr 140px 140px" }}>
                  <span className="field-static">{fund.display_name}</span>
                  {!request.useHistoricalReturns ? (
                    <input
                      className="field num"
                      onChange={(event) => setExpectedReturnOverride(fund.proj_id, Number(event.target.value))}
                      step={0.1}
                      type="number"
                      value={request.expectedReturnOverrides[fund.proj_id] ?? 0}
                    />
                  ) : <span className="field-static">&mdash;</span>}
                  {!request.useHistoricalVolatility ? (
                    <input
                      className="field num"
                      min={0.1}
                      onChange={(event) => setVolatilityOverride(fund.proj_id, Number(event.target.value))}
                      step={0.1}
                      type="number"
                      value={request.volatilityOverrides[fund.proj_id] ?? 0}
                    />
                  ) : <span className="field-static">&mdash;</span>}
                </div>
              ))}
            </div>
          </>
        ) : null}

        {!request.useHistoricalCorrelations && selectedFunds.length >= 2 ? (
          <>
            <div className="section-title" style={{ marginTop: 20 }}>Correlations</div>
            <div className="tableScroller">
              <table>
                <thead>
                  <tr>
                    <th />
                    {selectedFunds.map((fund) => <th key={fund.proj_id}>{fund.display_name}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {selectedFunds.map((rowFund) => (
                    <tr key={rowFund.proj_id}>
                      <td><b>{rowFund.display_name}</b></td>
                      {selectedFunds.map((colFund) => {
                        if (rowFund.proj_id === colFund.proj_id) return <td key={colFund.proj_id}>1.00</td>;
                        const key = correlationKey(rowFund.proj_id, colFund.proj_id);
                        return (
                          <td key={colFund.proj_id}>
                            <input
                              className="field num"
                              max={1}
                              min={-1}
                              onChange={(event) => setCorrelationOverride(rowFund.proj_id, colFund.proj_id, Number(event.target.value))}
                              step={0.05}
                              type="number"
                              value={request.correlationOverrides[key] ?? 0}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </div>

      {/* 4. Constraints */}
      <div className="card">
        <div className="section-title">Constraints</div>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="longOnly">Long-only</label>
            <select className="field" id="longOnly" onChange={(event) => patchConstraints({ longOnly: event.target.value === "true" })} value={String(request.constraints.longOnly)}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="minWeight">Default min weight (%)</label>
            <input className="field num" id="minWeight" min={request.constraints.longOnly ? 0 : -100} onChange={(event) => patchConstraints({ minWeightPct: Number(event.target.value) })} step={0.5} type="number" value={request.constraints.minWeightPct} />
          </div>
          <div className="form-field">
            <label htmlFor="maxWeight">Default max weight (%)</label>
            <input className="field num" id="maxWeight" max={100} min={0} onChange={(event) => patchConstraints({ maxWeightPct: Number(event.target.value) })} step={0.5} type="number" value={request.constraints.maxWeightPct} />
          </div>
          <div className="form-field">
            <label htmlFor="groupConstraints">Group Constraints</label>
            <select className="field" id="groupConstraints" onChange={(event) => patchConstraints({ groupConstraintsEnabled: event.target.value === "true" })} value={String(request.constraints.groupConstraintsEnabled)}>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="maxHoldings">Max holdings</label>
            <input className="field num" id="maxHoldings" min={1} onChange={(event) => patchConstraints({ maxHoldings: Number(event.target.value) })} type="number" value={request.constraints.maxHoldings} />
          </div>
          <div className="form-field">
            <label htmlFor="maxTurnover">Max turnover per rebalance (%)</label>
            <input
              className="field num"
              id="maxTurnover"
              min={0}
              onChange={(event) => patchConstraints({ maxTurnoverPct: event.target.value === "" ? null : Number(event.target.value) })}
              placeholder="No limit"
              step={1}
              type="number"
              value={request.constraints.maxTurnoverPct ?? ""}
            />
          </div>
        </div>
        {!request.constraints.longOnly ? (
          <p className="field-hint">Long-only is off -- set a fund's Min % below 0 in the Portfolio step to permit a short position for that fund.</p>
        ) : null}

        {request.constraints.groupConstraintsEnabled ? (
          <>
            <div className="section-title" style={{ marginTop: 20 }}>Asset groups</div>
            <div className="holdings-table">
              <div className="holdings-head" style={{ gridTemplateColumns: "40px 1fr 90px 90px" }}>
                <span /><span>Group name</span><span>Min %</span><span>Max %</span>
              </div>
              {ASSET_GROUP_IDS.map((id) => (
                <div className="holdings-row" key={id} style={{ gridTemplateColumns: "40px 1fr 90px 90px" }}>
                  <span className="field-static">{id}</span>
                  <input className="field" onChange={(event) => patchAssetGroup(id, { name: event.target.value })} placeholder={`Full name for group ${id}`} value={request.assetGroups[id].name} />
                  <input className="field num" min={0} onChange={(event) => patchAssetGroup(id, { minWeightPct: Number(event.target.value) })} type="number" value={request.assetGroups[id].minWeightPct} />
                  <input className="field num" max={100} min={0} onChange={(event) => patchAssetGroup(id, { maxWeightPct: Number(event.target.value) })} type="number" value={request.assetGroups[id].maxWeightPct} />
                </div>
              ))}
            </div>
          </>
        ) : null}
      </div>

      {/* 5. Evaluation and comparison */}
      <div className="card">
        <div className="section-title">Evaluation &amp; comparison</div>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="riskFreeRate">Risk-free rate (% / yr)</label>
            <input className="field num" id="riskFreeRate" min={0} onChange={(event) => patchConstraints({ riskFreeRatePct: Number(event.target.value) })} step={0.1} type="number" value={request.constraints.riskFreeRatePct} />
          </div>
          <div className="form-field">
            <label htmlFor="benchmark">Benchmark</label>
            <select
              className="field"
              id="benchmark"
              onChange={(event) => patch({ benchmarkProjId: event.target.value || null })}
              value={request.benchmarkProjId ?? ""}
            >
              <option value="">None</option>
              {selectedFunds.map((fund) => <option key={fund.proj_id} value={fund.proj_id}>{fund.display_name}</option>)}
            </select>
          </div>
          {request.benchmarkProjId ? (
            <div className="form-field">
              <label htmlFor="maxTrackingError">Max tracking error vs. benchmark (%)</label>
              <input
                className="field num"
                id="maxTrackingError"
                min={0}
                onChange={(event) => patchConstraints({ maxTrackingErrorPct: event.target.value === "" ? null : Number(event.target.value) })}
                placeholder="No limit"
                step={0.5}
                type="number"
                value={request.constraints.maxTrackingErrorPct ?? ""}
              />
            </div>
          ) : null}
        </div>

        <div className={advancedOpen ? "advanced-toggle open" : "advanced-toggle"} onClick={() => setAdvancedOpen((open) => !open)}>
          <span className="chev">&#9654;</span> Rolling-window validation &amp; comparison
        </div>
        <div className={advancedOpen ? "advanced-body open" : "advanced-body"}>
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="lookback">Lookback period</label>
              <select className="field" id="lookback" onChange={(event) => patchConstraints({ lookbackPeriodMonths: Number(event.target.value) as OptimizeRequest["constraints"]["lookbackPeriodMonths"] })} value={request.constraints.lookbackPeriodMonths}>
                <option value={12}>12 months</option>
                <option value={24}>24 months</option>
                <option value={36}>36 months</option>
                <option value={48}>48 months</option>
                <option value={60}>60 months</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="rollingWindowMode">Rolling window mode</label>
              <select className="field" id="rollingWindowMode" onChange={(event) => patchConstraints({ rollingWindowMode: event.target.value as OptimizeRequest["constraints"]["rollingWindowMode"] })} value={request.constraints.rollingWindowMode}>
                <option value="expanding">Expanding (grows from the start date)</option>
                <option value="trailing">Trailing (fixed-length, slides forward)</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="frequency">Optimization frequency</label>
              <select className="field" id="frequency" onChange={(event) => patchConstraints({ optimizationFrequency: event.target.value as OptimizeRequest["constraints"]["optimizationFrequency"] })} value={request.constraints.optimizationFrequency}>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
                <option value="annually">Annually</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="compareAgainst">Compared Allocation</label>
              <select className="field" id="compareAgainst" onChange={(event) => patchConstraints({ compareAgainst: event.target.value as CompareAgainst })} value={request.constraints.compareAgainst}>
                <option value="none">None</option>
                <option value="current">Your Current Portfolio</option>
                <option value="equal_weighted">Equal Weighted</option>
                <option value="max_sharpe">Max Sharpe Ratio Weights</option>
                <option value="inverse_volatility">Inverse Volatility Weighted</option>
                <option value="risk_parity">Risk Parity Weighted</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="review-box">
        Optimizing <b>{selectedFunds.length} funds</b> for <b>{OBJECTIVES.find((o) => o.id === request.goal)?.title}</b> using <b>{RISK_MEASURES.find((m) => m.id === request.riskMeasure)?.label}</b>
        {request.robustOptimization ? <>, with <b>Monte Carlo robust optimization</b> enabled</> : null}, re-validated every <b>{request.constraints.optimizationFrequency}</b> on a <b>{request.constraints.lookbackPeriodMonths}-month</b> lookback.
      </div>

      {selectedFunds.length < 2 ? (
        <div className="card" style={{ display: "grid", gap: 8 }}>
          <div className="errorLine">Go back and select at least 2 funds to optimize.</div>
        </div>
      ) : null}

      {error ? (
        <div className="banner">
          <span className="ic">&#9888;</span>
          <span>{error}</span>
        </div>
      ) : null}

      <div className="actions">
        <button className="btn btn-ghost" onClick={onBack} type="button">&larr; Back</button>
        <button className="btn btn-primary" disabled={!canRun} onClick={onRun} type="button">
          <Play size={15} /> {loading ? "Optimizing" : "Run optimization"}
        </button>
      </div>
    </div>
  );
}

// BL's own order of operations is Pi (equilibrium) -> views -> posterior.
// A view like "fund A will outperform fund B" only means something once
// you know what equilibrium already implies for A and B -- so this card
// shows equilibrium returns FIRST, then the views table, instead of
// letting the user set views blind and only see equilibrium afterward in
// Results (which was backwards).
function BlackLittermanCard({
  bl,
  request,
  selectedFunds,
  patchBl,
  onAddView,
  onUpdateView,
  onRemoveView
}: {
  bl: NonNullable<OptimizeRequest["blackLitterman"]>;
  request: OptimizeRequest;
  selectedFunds: SecFund[];
  patchBl: (next: Partial<OptimizeRequest["blackLitterman"]>) => void;
  onAddView: () => void;
  onUpdateView: (key: string, next: Partial<BlackLittermanView>) => void;
  onRemoveView: (key: string) => void;
}) {
  const equilibrium = estimateEquilibriumReturns(request);
  return (
    <div className="card">
      <div className="section-title">Black-Litterman inputs</div>
      <div className="form-grid">
        <div className="form-field">
          <label htmlFor="riskAversion">Risk aversion (&delta;)</label>
          <input className="field num" id="riskAversion" min={0.1} onChange={(event) => patchBl({ riskAversion: Number(event.target.value) })} step={0.1} type="number" value={bl.riskAversion} />
        </div>
        <div className="form-field">
          <label htmlFor="tau">Tau (&tau;)</label>
          <input className="field num" id="tau" max={1} min={0.01} onChange={(event) => patchBl({ tau: Number(event.target.value) })} step={0.01} type="number" value={bl.tau} />
        </div>
        <div className="form-field">
          <label htmlFor="benchmarkReturn">Benchmark expected return (%)</label>
          <input className="field num" id="benchmarkReturn" onChange={(event) => patchBl({ benchmarkExpectedReturnPct: Number(event.target.value) })} step={0.1} type="number" value={bl.benchmarkExpectedReturnPct} />
        </div>
      </div>

      <div className="section-title" style={{ marginTop: 20 }}>1. Market equilibrium returns (&Pi;)</div>
      <p className="field-hint">What the model already implies for each fund before any view is applied -- set your views below relative to these, not blind.</p>
      <p className="field-hint">Illustrative preview only: these are client-side placeholder figures for anchoring your views. Running the optimization computes the real equilibrium returns server-side from actual NAV history, and the Results tab reports those.</p>
      <div className="tableScroller">
        <table>
          <thead><tr><th>Fund</th><th>Equilibrium return</th></tr></thead>
          <tbody>
            {selectedFunds.map((fund) => (
              <tr key={fund.proj_id}><td>{fund.display_name}</td><td>{equilibrium[fund.proj_id] ?? 0}%</td></tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-title" style={{ marginTop: 20 }}>2. Your views</div>
      <div className="holdings-table">
        <div className="holdings-head" style={{ gridTemplateColumns: "1fr 140px 1fr 100px 110px 34px" }}>
          <span>Asset 1</span><span>View type</span><span>Asset 2 (relative only)</span><span>Value (%)</span><span>Confidence</span><span />
        </div>
        {bl.views.map((view) => (
          <div className="holdings-row" key={view.key} style={{ gridTemplateColumns: "1fr 140px 1fr 100px 110px 34px" }}>
            <select className="field" onChange={(event) => onUpdateView(view.key, { assetProjId1: event.target.value })} value={view.assetProjId1}>
              {selectedFunds.map((fund) => <option key={fund.proj_id} value={fund.proj_id}>{fund.display_name}</option>)}
            </select>
            <select className="field" onChange={(event) => onUpdateView(view.key, { viewType: event.target.value as ViewType, assetProjId2: event.target.value === "relative" ? (selectedFunds[1]?.proj_id ?? null) : null })} value={view.viewType}>
              <option value="absolute">will return</option>
              <option value="relative">will outperform by</option>
            </select>
            {view.viewType === "relative" ? (
              <select className="field" onChange={(event) => onUpdateView(view.key, { assetProjId2: event.target.value })} value={view.assetProjId2 ?? ""}>
                {selectedFunds.map((fund) => <option key={fund.proj_id} value={fund.proj_id}>{fund.display_name}</option>)}
              </select>
            ) : <span className="field-static">&mdash;</span>}
            <input className="field num" onChange={(event) => onUpdateView(view.key, { adjustedPerformancePct: Number(event.target.value) })} step={0.1} type="number" value={view.adjustedPerformancePct} />
            <select className="field" onChange={(event) => onUpdateView(view.key, { confidence: Number(event.target.value) as ViewConfidence })} value={view.confidence}>
              <option value={100}>100%</option>
              <option value={75}>75%</option>
              <option value={50}>50%</option>
              <option value={25}>25%</option>
            </select>
            <button aria-label="Remove view" className="btn btn-ghost" onClick={() => onRemoveView(view.key)} type="button"><Trash2 size={15} /></button>
          </div>
        ))}
      </div>
      <button className="btn btn-chip" onClick={onAddView} style={{ marginTop: 10 }} type="button">
        <Plus size={14} /> Add view
      </button>
    </div>
  );
}
