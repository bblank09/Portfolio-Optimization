import { useState } from "react";
import { Play, Plus, Trash2 } from "lucide-react";
import type { SecFund } from "../types/backtest";
import { ASSET_GROUP_IDS } from "../types/optimize";
import type {
  AssetGroup,
  AssetGroupId,
  BlackLittermanView,
  CompareAgainst,
  CovarianceMethod,
  ObjectiveGoal,
  OptimizeRequest,
  ReturnEstimationMethod,
  RiskMeasure,
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
}

// docs/mock-ui-spec.md 2a: scoped down from PV's full 15-goal list to what
// riskfolio-lib supports and this project's decided scope.
const OBJECTIVES: Array<{ id: ObjectiveGoal; title: string; blurb: string }> = [
  { id: "max_sharpe", title: "Maximize Sharpe Ratio", blurb: "Best risk-adjusted return across the shortlist." },
  { id: "min_volatility", title: "Minimize Volatility", blurb: "Lowest-risk combination of the selected funds." },
  { id: "max_return_target_vol", title: "Max Return, Target Volatility", blurb: "Highest return subject to a volatility ceiling you set." },
  { id: "min_variance", title: "Minimize Variance (GMV)", blurb: "The global minimum-variance portfolio." },
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

let viewSeq = 0;
function nextViewKey() {
  viewSeq += 1;
  return `view-${viewSeq}`;
}

export function OptimizeAssumptionsStep({ active, request, funds, error, loading, onChange, onBack, onRun }: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const isBlackLitterman = request.goal === "black_litterman";
  const isTargetVol = request.goal === "max_return_target_vol";
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

  function setExpectedReturnOverride(projId: string, value: number) {
    onChange({ ...request, expectedReturnOverrides: { ...request.expectedReturnOverrides, [projId]: value } });
  }

  function patchAssetGroup(id: AssetGroupId, next: Partial<AssetGroup>) {
    onChange({ ...request, assetGroups: { ...request.assetGroups, [id]: { ...request.assetGroups[id], ...next } } });
  }

  function setGoal(goal: ObjectiveGoal) {
    const blackLitterman = goal === "black_litterman"
      ? (request.blackLitterman ?? { riskAversion: 2.5, tau: 0.05, benchmarkExpectedReturnPct: 7, views: [] })
      : null;
    patch({ goal, blackLitterman });
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

      <div className="card">
        <div className="section-title">Time period</div>
        <p className="field-hint">The historical window used to estimate returns, volatility, and correlations for every selected fund.</p>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="periodStart">Start date</label>
            <input className="field" id="periodStart" onChange={(event) => patchTimePeriod({ startDate: event.target.value })} type="date" value={request.timePeriod.startDate} />
          </div>
          <div className="form-field">
            <label htmlFor="periodEnd">End date</label>
            <input className="field" id="periodEnd" onChange={(event) => patchTimePeriod({ endDate: event.target.value })} type="date" value={request.timePeriod.endDate} />
          </div>
        </div>
      </div>

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
            <p className="field-hint">CDaR ties directly to the Drawdown view in the Results tabs -- the same drawdown concept, used here as the risk measure.</p>
          </div>
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
              <p className="field-hint">Constrains the risky-asset mix directly to hit this volatility ceiling -- it does not shift the portfolio into cash.</p>
            </div>
          ) : null}
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
            <p className="field-hint">Resamples the optimization inputs to reduce sensitivity to estimation error and improve diversification.</p>
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
            <p className="field-hint">Set independently -- you can use historical returns while overriding volatility or correlations, or vice versa.</p>
          </div>
        </div>

        {!request.useHistoricalReturns ? (
          <>
            <div className="section-title" style={{ marginTop: 20 }}>Expected return per fund</div>
            <p className="field-hint">Set your own expected return per fund instead of the historical average.</p>
            <div className="holdings-table">
              <div className="holdings-head" style={{ gridTemplateColumns: "1fr 120px" }}>
                <span>Fund</span><span>Expected return (%)</span>
              </div>
              {selectedFunds.map((fund) => (
                <div className="holdings-row" key={fund.proj_id} style={{ gridTemplateColumns: "1fr 120px" }}>
                  <span className="field-static">{fund.display_name}</span>
                  <input
                    className="field num"
                    onChange={(event) => setExpectedReturnOverride(fund.proj_id, Number(event.target.value))}
                    step={0.1}
                    type="number"
                    value={request.expectedReturnOverrides[fund.proj_id] ?? 0}
                  />
                </div>
              ))}
            </div>
          </>
        ) : null}
      </div>

      {isBlackLitterman && request.blackLitterman ? (
        <div className="card">
          <div className="section-title">Black-Litterman inputs</div>
          <p className="field-hint">Benchmark weights first (equal-weighted from your shortlist by default), then the views that adjust the equilibrium returns.</p>
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="riskAversion">Risk aversion (&delta;)</label>
              <input className="field num" id="riskAversion" min={0.1} onChange={(event) => patchBl({ riskAversion: Number(event.target.value) })} step={0.1} type="number" value={request.blackLitterman.riskAversion} />
            </div>
            <div className="form-field">
              <label htmlFor="tau">Tau (&tau;)</label>
              <input className="field num" id="tau" max={1} min={0.01} onChange={(event) => patchBl({ tau: Number(event.target.value) })} step={0.01} type="number" value={request.blackLitterman.tau} />
              <p className="field-hint">Controls how much weight the market-equilibrium prior carries versus your views. Typical range: 0.01-1. Default 0.05.</p>
            </div>
            <div className="form-field">
              <label htmlFor="benchmarkReturn">Benchmark expected return (%)</label>
              <input className="field num" id="benchmarkReturn" onChange={(event) => patchBl({ benchmarkExpectedReturnPct: Number(event.target.value) })} step={0.1} type="number" value={request.blackLitterman.benchmarkExpectedReturnPct} />
            </div>
          </div>

          <div className="section-title" style={{ marginTop: 20 }}>Investor views</div>
          <div className="holdings-table">
            <div className="holdings-head" style={{ gridTemplateColumns: "1fr 140px 1fr 100px 110px 34px" }}>
              <span>Asset 1</span><span>View type</span><span>Asset 2 (relative only)</span><span>Value (%)</span><span>Confidence</span><span />
            </div>
            {request.blackLitterman.views.map((view) => (
              <div className="holdings-row" key={view.key} style={{ gridTemplateColumns: "1fr 140px 1fr 100px 110px 34px" }}>
                <select className="field" onChange={(event) => updateView(view.key, { assetProjId1: event.target.value })} value={view.assetProjId1}>
                  {selectedFunds.map((fund) => <option key={fund.proj_id} value={fund.proj_id}>{fund.display_name}</option>)}
                </select>
                <select className="field" onChange={(event) => updateView(view.key, { viewType: event.target.value as ViewType, assetProjId2: event.target.value === "relative" ? (selectedFunds[1]?.proj_id ?? null) : null })} value={view.viewType}>
                  <option value="absolute">will return</option>
                  <option value="relative">will outperform by</option>
                </select>
                {view.viewType === "relative" ? (
                  <select className="field" onChange={(event) => updateView(view.key, { assetProjId2: event.target.value })} value={view.assetProjId2 ?? ""}>
                    {selectedFunds.map((fund) => <option key={fund.proj_id} value={fund.proj_id}>{fund.display_name}</option>)}
                  </select>
                ) : <span className="field-static">&mdash;</span>}
                <input className="field num" onChange={(event) => updateView(view.key, { adjustedPerformancePct: Number(event.target.value) })} step={0.1} type="number" value={view.adjustedPerformancePct} />
                <select className="field" onChange={(event) => updateView(view.key, { confidence: Number(event.target.value) as ViewConfidence })} value={view.confidence}>
                  <option value={100}>100%</option>
                  <option value={75}>75%</option>
                  <option value={50}>50%</option>
                  <option value={25}>25%</option>
                </select>
                <button aria-label="Remove view" className="btn btn-ghost" onClick={() => removeView(view.key)} type="button"><Trash2 size={15} /></button>
              </div>
            ))}
          </div>
          <button className="btn btn-chip" onClick={addView} style={{ marginTop: 10 }} type="button">
            <Plus size={14} /> Add view
          </button>
        </div>
      ) : null}

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
            <input className="field num" id="minWeight" min={0} onChange={(event) => patchConstraints({ minWeightPct: Number(event.target.value) })} step={0.5} type="number" value={request.constraints.minWeightPct} />
            <p className="field-hint">Used for any fund without its own Min % set in the Portfolio step -- per-fund bounds there take priority.</p>
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
            <p className="field-hint">Adds a Group dropdown (None/A-F) to each fund in the Portfolio step, plus the group-level bounds below.</p>
          </div>
          <div className="form-field">
            <label htmlFor="maxHoldings">Max holdings</label>
            <input className="field num" id="maxHoldings" min={1} onChange={(event) => patchConstraints({ maxHoldings: Number(event.target.value) })} type="number" value={request.constraints.maxHoldings} />
          </div>
          <div className="form-field">
            <label htmlFor="riskFreeRate">Risk-free rate (% / yr)</label>
            <input className="field num" id="riskFreeRate" min={0} onChange={(event) => patchConstraints({ riskFreeRatePct: Number(event.target.value) })} step={0.1} type="number" value={request.constraints.riskFreeRatePct} />
          </div>
        </div>

        {request.constraints.groupConstraintsEnabled ? (
          <>
            <div className="section-title" style={{ marginTop: 20 }}>Asset groups</div>
            <p className="field-hint">6 fixed groups (A-F), each with its own name and weight bounds. Assign funds to a group in the Portfolio step.</p>
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
              <p className="field-hint">Re-optimizes on a fixed trailing window at the chosen frequency, then scores realized performance on the next period.</p>
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
