import { useEffect, useState } from "react";
import { fetchFunds } from "../api/client";
import { OptimizeAssumptionsStep } from "../components/OptimizeAssumptionsStep";
import { OptimizeResults } from "../components/OptimizeResults";
import { PortfolioStep } from "../components/PortfolioStep";
import { RunOverlay } from "../components/RunOverlay";
import { Stepper } from "../components/Stepper";
import { runMockOptimize } from "../lib/mockOptimize";
import type { SecFund, SecFundAllocation } from "../types/backtest";
import type { OptimizeRequest, OptimizeResult } from "../types/optimize";

const COMPARE_LABELS: Record<OptimizeRequest["constraints"]["compareAgainst"], string | null> = {
  none: null,
  equal_weighted: "Equal Weighted",
  max_sharpe: "Max Sharpe Ratio Weights",
  inverse_volatility: "Inverse Volatility Weighted",
  risk_parity: "Risk Parity Weighted"
};

const initialRequest: OptimizeRequest = {
  funds: [],
  goal: "max_sharpe",
  riskMeasure: "std_dev",
  targetAnnualVolatilityPct: 10,
  robustOptimization: false,
  useHistoricalReturns: true,
  returnMethod: "historical_mean",
  covarianceMethod: "sample",
  blackLitterman: null,
  constraints: {
    longOnly: true,
    minWeightPct: 0,
    maxWeightPct: 100,
    groupConstraintsEnabled: false,
    maxHoldings: 20,
    lookbackPeriodMonths: 36,
    optimizationFrequency: "quarterly",
    riskFreeRatePct: 1.5,
    compareAgainst: "equal_weighted"
  }
};

export function OptimizeWorkspace() {
  const [funds, setFunds] = useState<SecFund[]>([]);
  const [request, setRequest] = useState<OptimizeRequest>(initialRequest);
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [unlockedStep, setUnlockedStep] = useState(0);
  const [theme, setTheme] = useState<"light" | "dark">(() => (localStorage.getItem("po-theme") === "dark" ? "dark" : "light"));

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("po-theme", theme);
  }, [theme]);

  useEffect(() => {
    fetchFunds()
      .then((loadedFunds) => setFunds(loadedFunds))
      .catch((caught: Error) => setError(caught.message));
  }, []);

  const selectedFunds = request.funds;

  function goToStep(index: number) {
    setCurrentStep(index);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function advanceTo(index: number) {
    setUnlockedStep((current) => Math.max(current, index));
    goToStep(index);
  }

  // PortfolioStep is reused from the backtester with weightsOptional=true --
  // confirmed live against PortfolioVisualizer's own optimize-portfolio tool
  // ("Portfolio asset weights and constraints are optional"). It still
  // produces SecFundAllocation[] with a per-fund "weight", but this mock
  // doesn't yet feed that weight anywhere (Phase 5: it would become the
  // reference/starting allocation, matching PV's own optional-allocation
  // behavior). See docs/mock-ui-spec.md Step 1.
  function handleAssetsChange(assets: SecFundAllocation[]) {
    setResult(null);
    setError("");
    const chosen = assets
      .map((a) => funds.find((f) => f.proj_id === a.proj_id))
      .filter((f): f is SecFund => Boolean(f));
    setRequest((current) => ({ ...current, funds: chosen }));
  }

  function updateRequest(next: OptimizeRequest) {
    setResult(null);
    setError("");
    setRequest(next);
  }

  async function submit() {
    setLoading(true);
    setError("");
    // Phase 4 mock: no backend call yet. A short artificial delay plus the
    // existing RunOverlay staged UI keeps the loading-state UX identical to
    // what Phase 5's real POST /api/optimize will need.
    await new Promise((resolve) => window.setTimeout(resolve, 900));
    try {
      const mockResult = runMockOptimize(request);
      setResult(mockResult);
      advanceTo(2);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Optimization failed");
    } finally {
      setLoading(false);
    }
  }

  function startOver() {
    setRequest(initialRequest);
    setResult(null);
    setError("");
    setUnlockedStep(0);
    goToStep(0);
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <img alt="Portfolio Optimization" className="mark" src="/brand/topbar-mark.png" />
          <span>Portfolio Optimization</span>
          <span className="tag">Mock UI &mdash; Phase 4, no live optimizer yet</span>
        </div>
        <Stepper currentStep={currentStep} onStepClick={goToStep} unlockedStep={unlockedStep} />
        <button className="theme-toggle" onClick={() => setTheme((current) => (current === "light" ? "dark" : "light"))} type="button">
          Toggle theme
        </button>
      </header>

      <div className="main">
        <PortfolioStep active={currentStep === 0} funds={funds} onAssetsChange={handleAssetsChange} onContinue={() => advanceTo(1)} weightsOptional />

        <OptimizeAssumptionsStep
          active={currentStep === 1}
          error={error}
          funds={funds}
          loading={loading}
          onBack={() => goToStep(0)}
          onChange={updateRequest}
          onRun={submit}
          request={request}
        />

        <div className={currentStep === 2 ? "page active" : "page"}>
          <OptimizeResults compareLabel={COMPARE_LABELS[request.constraints.compareAgainst]} funds={selectedFunds} result={result} />
          <div className="actions">
            <button className="btn btn-ghost" onClick={() => goToStep(1)} type="button">&larr; Adjust assumptions</button>
            <button className="btn btn-ghost" onClick={startOver} type="button">Start a new optimization</button>
          </div>
        </div>
      </div>

      <RunOverlay
        open={loading}
        stages={["Validating inputs", "Estimating returns & covariance", "Solving optimization", "Preparing report"]}
        title="Running optimization…"
      />
    </div>
  );
}
