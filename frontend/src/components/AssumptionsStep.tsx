import { useState } from "react";
import { Play } from "lucide-react";
import type { BacktestRequest, SecFund } from "../types/backtest";

interface Props {
  active: boolean;
  request: BacktestRequest;
  funds: SecFund[];
  fieldErrors: Record<string, string>;
  validationErrors: string[];
  navStart: string | null;
  navAsOf: string | null;
  // The longest continuous gap-free window for the currently selected
  // funds + benchmark, computed server-side (GET /api/funds/testable-range)
  // with the exact same completeness logic the backtest engine applies.
  // A client-side "latest nav_start .. earliest nav_end" intersection was
  // tried first and rejected: it still let "Max" land on a range containing
  // a real internal gap (e.g. the 2024-06 to 2024-11 SEC-wide incident),
  // so Max kept producing INSUFFICIENT_NAV_HISTORY.
  testableRange: { start: string | null; end: string | null };
  error: string;
  loading: boolean;
  onChange: (request: BacktestRequest) => void;
  onBack: () => void;
  onRun: () => void;
}

const RANGE_PRESETS: Array<{ label: string; years: number | "max" }> = [
  { label: "1Y", years: 1 },
  { label: "3Y", years: 3 },
  { label: "5Y", years: 5 },
  { label: "Max", years: "max" }
];

export function AssumptionsStep({
  active,
  request,
  funds,
  fieldErrors,
  validationErrors,
  navStart,
  navAsOf,
  testableRange,
  error,
  loading,
  onChange,
  onBack,
  onRun
}: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const showCashflow = request.cashflow.enabled;
  const cashflowLabel = request.cashflow.type === "withdrawal" ? "Withdrawal amount" : "Contribution amount";
  const canRun = validationErrors.length === 0 && !loading;

  const effectiveNavStart = testableRange.start ?? navStart;
  const effectiveNavAsOf = testableRange.end ?? navAsOf;

  function markTouched(field: string) {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  function fieldError(field: string): string | null {
    return touched[field] ? (fieldErrors[field] ?? null) : null;
  }

  function applyRangePreset(years: number | "max") {
    const end = effectiveNavAsOf ?? request.end_date;
    const start = years === "max" ? (effectiveNavStart ?? request.start_date) : shiftYears(end, -years);
    onChange({ ...request, start_date: effectiveNavStart && start < effectiveNavStart ? effectiveNavStart : start, end_date: end });
  }

  return (
    <div className={active ? "page active" : "page"}>
      <div className="page-head">
        <h1>Set your assumptions</h1>
        <p>Every parameter below is yours to set directly &mdash; grouped by topic so it stays easy to fill in.</p>
      </div>

      <div className="card">
        <div className="section-title">Date range &amp; capital</div>
        <div className="range-presets">
          {RANGE_PRESETS.map((preset) => (
            <button
              className="btn btn-chip"
              key={preset.label}
              onClick={() => applyRangePreset(preset.years)}
              type="button"
            >
              {preset.label}
            </button>
          ))}
        </div>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="startDate">Start date</label>
            <input
              className="field"
              id="startDate"
              max={effectiveNavAsOf ?? undefined}
              min={effectiveNavStart ?? undefined}
              onBlur={() => markTouched("startDate")}
              onChange={(event) => onChange({ ...request, start_date: event.target.value })}
              type="date"
              value={request.start_date}
            />
            {fieldError("startDate") ? <div className="field-error">{fieldError("startDate")}</div> : null}
          </div>
          <div className="form-field">
            <label htmlFor="endDate">End date</label>
            <input
              className="field"
              id="endDate"
              max={effectiveNavAsOf ?? undefined}
              min={effectiveNavStart ?? undefined}
              onBlur={() => markTouched("endDate")}
              onChange={(event) => onChange({ ...request, end_date: event.target.value })}
              type="date"
              value={request.end_date}
            />
            {fieldError("endDate") ? <div className="field-error">{fieldError("endDate")}</div> : null}
          </div>
          <div className="form-field">
            <label htmlFor="initialCapital">Initial capital</label>
            <input
              className="field num"
              id="initialCapital"
              min={1}
              onBlur={() => markTouched("initialCapital")}
              onChange={(event) => onChange({ ...request, initial_capital: Number(event.target.value) })}
              type="number"
              value={request.initial_capital}
            />
            {fieldError("initialCapital") ? <div className="field-error">{fieldError("initialCapital")}</div> : null}
          </div>
          <div className="form-field">
            <label htmlFor="benchmark">Benchmark</label>
            <select
              className="field"
              id="benchmark"
              onBlur={() => markTouched("benchmark")}
              onChange={(event) => onChange({ ...request, benchmark_proj_id: event.target.value })}
              value={request.benchmark_proj_id}
            >
              {funds.map((fund) => (
                <option key={`${fund.proj_id}-${fund.fund_class_name}`} value={fund.proj_id}>{fund.display_name}</option>
              ))}
            </select>
            {fieldError("benchmark") ? <div className="field-error">{fieldError("benchmark")}</div> : null}
          </div>
        </div>

        <div className="section-title" style={{ marginTop: 20 }}>Cashflow</div>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="cashflowEnabled">Recurring cashflow</label>
            <select
              className="field"
              id="cashflowEnabled"
              value={String(request.cashflow.enabled)}
              onChange={(event) => onChange({ ...request, cashflow: { ...request.cashflow, enabled: event.target.value === "true" } })}
            >
              <option value="false">Disabled</option>
              <option value="true">Enabled</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="cashflowType">Type</label>
            <select
              className="field"
              disabled={!showCashflow}
              id="cashflowType"
              value={request.cashflow.type}
              onChange={(event) => onChange({ ...request, cashflow: { ...request.cashflow, type: event.target.value as BacktestRequest["cashflow"]["type"] } })}
            >
              <option value="contribution">Contribution</option>
              <option value="withdrawal">Withdrawal</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="cashflowAmount">{cashflowLabel}</label>
            <input
              className="field num"
              disabled={!showCashflow}
              id="cashflowAmount"
              min={0}
              onBlur={() => markTouched("cashflowAmount")}
              type="number"
              value={request.cashflow.amount}
              onChange={(event) => onChange({ ...request, cashflow: { ...request.cashflow, amount: Number(event.target.value) } })}
            />
            {fieldError("cashflowAmount") ? <div className="field-error">{fieldError("cashflowAmount")}</div> : null}
          </div>
          <div className="form-field">
            <label htmlFor="cashflowFrequency">Frequency</label>
            <select
              className="field"
              disabled={!showCashflow}
              id="cashflowFrequency"
              value={request.cashflow.frequency}
              onChange={(event) => onChange({ ...request, cashflow: { ...request.cashflow, frequency: event.target.value as BacktestRequest["cashflow"]["frequency"] } })}
            >
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="annual">Annual</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="cashflowTiming">Timing</label>
            <select
              className="field"
              disabled={!showCashflow}
              id="cashflowTiming"
              value={request.cashflow.timing}
              onChange={(event) => onChange({ ...request, cashflow: { ...request.cashflow, timing: event.target.value as BacktestRequest["cashflow"]["timing"] } })}
            >
              <option value="beginning">Beginning of period</option>
              <option value="end">End of period</option>
            </select>
          </div>
        </div>

        <div className="section-title" style={{ marginTop: 20 }}>Rebalancing</div>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="rebalancing">Mode</label>
            <select
              className="field"
              id="rebalancing"
              value={request.rebalancing.mode}
              onChange={(event) => onChange({ ...request, rebalancing: { ...request.rebalancing, mode: event.target.value as BacktestRequest["rebalancing"]["mode"] } })}
            >
              <option value="none">None</option>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="annual">Annual</option>
              <option value="threshold">Threshold (band)</option>
            </select>
          </div>
          {request.rebalancing.mode === "threshold" ? (
            <div className="form-field">
              <label htmlFor="rebalanceThreshold">Drift band (%)</label>
              <p className="field-hint">Rebalances only when a holding drifts this many percentage points away from its target weight.</p>
              <input
                className="field num"
                id="rebalanceThreshold"
                min={0.1}
                step={0.1}
                type="number"
                value={request.rebalancing.threshold_pct}
                onChange={(event) => onChange({ ...request, rebalancing: { ...request.rebalancing, threshold_pct: Number(event.target.value) } })}
              />
            </div>
          ) : null}
        </div>

        <div className={advancedOpen ? "advanced-toggle open" : "advanced-toggle"} onClick={() => setAdvancedOpen((open) => !open)}>
          <span className="chev">&#9654;</span> Advanced settings
        </div>
        <div className={advancedOpen ? "advanced-body open" : "advanced-body"}>
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="riskFreeRate">Risk-free rate (% / yr)</label>
              <input
                className="field num"
                id="riskFreeRate"
                min={0}
                step={0.1}
                type="number"
                value={request.risk_free_rate_pct}
                onChange={(event) => onChange({ ...request, risk_free_rate_pct: Number(event.target.value) })}
              />
            </div>
            <div className="form-field">
              <label htmlFor="annualDrag">Annual drag / expense (%)</label>
              <input className="field num" id="annualDrag" min={0} step={0.01} type="number" value={request.costs.annual_drag_pct} onChange={(event) => onChange({ ...request, costs: { ...request.costs, annual_drag_pct: Number(event.target.value) } })} />
            </div>
            <div className="form-field">
              <label htmlFor="transactionCost">Transaction cost (bps)</label>
              <p className="field-hint">1 bp = 0.01%. Charged on the dollar value of each trade made during rebalancing.</p>
              <input className="field num" id="transactionCost" min={0} type="number" value={request.costs.transaction_bps} onChange={(event) => onChange({ ...request, costs: { ...request.costs, transaction_bps: Number(event.target.value) } })} />
            </div>
            <div className="form-field">
              <label htmlFor="slippage">Slippage (bps)</label>
              <p className="field-hint">1 bp = 0.01%. Extra cost from the price moving between decision and execution.</p>
              <input className="field num" id="slippage" min={0} type="number" value={request.costs.slippage_bps} onChange={(event) => onChange({ ...request, costs: { ...request.costs, slippage_bps: Number(event.target.value) } })} />
            </div>
            <div className="form-field">
              <label>Price basis</label>
              <p className="field-static">SEC NAV per unit</p>
            </div>
            <div className="form-field">
              <label htmlFor="dataFrequency">NAV granularity</label>
              <select
                className="field"
                id="dataFrequency"
                value={request.data.frequency}
                onChange={(event) => onChange({ ...request, data: { ...request.data, frequency: event.target.value as BacktestRequest["data"]["frequency"] } })}
              >
                <option value="monthly">Monthly (month-end)</option>
                <option value="daily">Daily (business days)</option>
              </select>
            </div>
            <div className="form-field">
              <label>Dividend treatment</label>
              <p className="field-static">Reflected through fund NAV only</p>
            </div>
          </div>
        </div>
      </div>

      <div className="review-box">
        Run a backtest for <b>{request.assets.map((asset) => `${asset.display_name} ${asset.weight}%`).join(", ")}</b> from <b>{request.start_date}</b> to <b>{request.end_date}</b>, starting capital <b>{request.initial_capital.toLocaleString()}</b>
        {showCashflow ? <> with <b>{request.cashflow.type}</b> of <b>{request.cashflow.amount.toLocaleString()}</b> {request.cashflow.frequency}</> : null}
        {request.rebalancing.mode === "threshold" ? (
          <>, rebalanced whenever any holding drifts <b>{request.rebalancing.threshold_pct}%</b> from target</>
        ) : request.rebalancing.mode !== "none" ? (
          <>, rebalanced <b>{request.rebalancing.mode}</b></>
        ) : null}.
      </div>

      {validationErrors.length ? (
        <div className="card" style={{ display: "grid", gap: 8 }}>
          {validationErrors.map((item) => <div className="errorLine" key={item}>{item}</div>)}
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
          <Play size={15} /> {loading ? "Running" : "Run backtest"}
        </button>
      </div>
    </div>
  );
}

function shiftYears(isoDate: string, deltaYears: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return isoDate;
  date.setUTCFullYear(date.getUTCFullYear() + deltaYears);
  return date.toISOString().slice(0, 10);
}
