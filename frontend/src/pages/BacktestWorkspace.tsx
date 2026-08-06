import { useEffect, useMemo, useState } from "react";
import { fetchBacktestByRunId, fetchDataStatus, fetchFunds, fetchTestableRange, runBacktest } from "../api/client";
import { AssumptionsStep } from "../components/AssumptionsStep";
import { PortfolioStep } from "../components/PortfolioStep";
import { RunOverlay } from "../components/RunOverlay";
import { RunSummary } from "../components/RunSummary";
import { Stepper } from "../components/Stepper";
import type { BacktestRequest, BacktestResult, SecFund, SecFundAllocation } from "../types/backtest";

const initialRequest: BacktestRequest = {
  assets: [],
  start_date: "2020-01-31",
  end_date: "2024-06-30",
  initial_capital: 100000,
  benchmark_proj_id: "",
  risk_free_rate_pct: 0,
  cashflow: { enabled: false, type: "contribution", amount: 0, frequency: "monthly", timing: "end" },
  rebalancing: { mode: "annual", threshold_pct: 5 },
  costs: { transaction_bps: 0, slippage_bps: 0, annual_drag_pct: 0 },
  data: { source: "sec_open_data", price_field: "nav_per_unit", frequency: "monthly" }
};

export function BacktestWorkspace() {
  const [funds, setFunds] = useState<SecFund[]>([]);
  const [navAsOf, setNavAsOf] = useState<string | null>(null);
  const [navStart, setNavStart] = useState<string | null>(null);
  const [request, setRequest] = useState<BacktestRequest>(initialRequest);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [unlockedStep, setUnlockedStep] = useState(0);
  const [linkCopied, setLinkCopied] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(() => (localStorage.getItem("pb-theme") === "dark" ? "dark" : "light"));

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("pb-theme", theme);
  }, [theme]);

  useEffect(() => {
    fetchFunds()
      .then((loadedFunds) => setFunds(loadedFunds))
      .catch((caught: Error) => setError(caught.message));
  }, []);

  useEffect(() => {
    // Best-effort only -- not knowing the NAV freshness date shouldn't block
    // using the app, so failures here are silently ignored rather than
    // surfaced as a page-level error.
    fetchDataStatus()
      .then((status) => {
        setNavAsOf(status.nav_as_of);
        setNavStart(status.nav_start);
      })
      .catch(() => {
        setNavAsOf(null);
        setNavStart(null);
      });
  }, []);

  useEffect(() => {
    // A shared link carries ?run=<run_id> -- reload that exact persisted
    // run (both the inputs and the result) so opening the link reproduces
    // what was shared, without re-running the backtest.
    //
    // React 19 StrictMode double-invokes effects in dev (mount -> cleanup ->
    // mount), so this fires two overlapping fetches for the same run_id on
    // every load. Both resolve harmlessly to the same data on their own,
    // but the `ignore` flag is the standard React-docs pattern for async
    // effects regardless -- it avoids a stale response from a superseded
    // invocation ever winning a race against a newer one.
    const runId = new URLSearchParams(window.location.search).get("run");
    if (!runId) return;
    let ignore = false;
    setLoading(true);
    fetchBacktestByRunId(runId)
      .then((response) => {
        if (ignore) return;
        setRequest(response.request);
        setResult(response);
        advanceTo(2);
      })
      .catch((caught: Error) => {
        if (ignore) return;
        setError(`Could not load shared run "${runId}": ${caught.message}`);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, []);

  const totalWeight = request.assets.reduce((sum, asset) => sum + asset.weight, 0);
  const fieldErrors = validateRequest(request, totalWeight);
  const validationErrors = Object.values(fieldErrors);

  const selectedProjIds = useMemo(() => {
    const ids = new Set(request.assets.map((asset) => asset.proj_id).filter(Boolean));
    if (request.benchmark_proj_id) ids.add(request.benchmark_proj_id);
    return [...ids].sort();
  }, [request.assets, request.benchmark_proj_id]);

  const [testableRange, setTestableRange] = useState<{ start: string | null; end: string | null }>({ start: null, end: null });

  useEffect(() => {
    if (!selectedProjIds.length) {
      setTestableRange({ start: null, end: null });
      return;
    }
    let ignore = false;
    fetchTestableRange(selectedProjIds)
      .then((range) => { if (!ignore) setTestableRange(range); })
      .catch(() => { if (!ignore) setTestableRange({ start: null, end: null }); });
    return () => {
      ignore = true;
    };
    // selectedProjIds is a derived, order-independent array recomputed from
    // request.assets/benchmark_proj_id above -- depending on its joined
    // value (not the array reference) avoids refetching on every keystroke
    // that doesn't actually change which funds are selected.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjIds.join(",")]);

  function updateRequest(next: BacktestRequest | ((current: BacktestRequest) => BacktestRequest)) {
    setResult(null);
    setError("");
    setRequest(next);
  }

  function handleAssetsChange(assets: SecFundAllocation[]) {
    updateRequest((current) => {
      const stillHasBenchmark = assets.some((asset) => asset.proj_id === current.benchmark_proj_id);
      return {
        ...current,
        assets,
        benchmark_proj_id: stillHasBenchmark ? current.benchmark_proj_id : (assets[0]?.proj_id ?? "")
      };
    });
  }

  function goToStep(index: number) {
    setCurrentStep(index);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function advanceTo(index: number) {
    setUnlockedStep((current) => Math.max(current, index));
    goToStep(index);
  }

  async function submit() {
    setLoading(true);
    setError("");
    try {
      const response = await runBacktest(request);
      setResult(response);
      // Reflect the run in the URL so copying the address bar shares this
      // exact result -- replaceState (not push) so "back" doesn't just
      // toggle the query string.
      const url = new URL(window.location.href);
      url.searchParams.set("run", response.run_id);
      window.history.replaceState(null, "", url);
      advanceTo(2);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Backtest failed");
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
    const url = new URL(window.location.href);
    url.searchParams.delete("run");
    window.history.replaceState(null, "", url);
  }

  async function copyShareLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setLinkCopied(true);
      window.setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      // Clipboard access can be denied by the browser -- fail silently,
      // the URL is still visible and copyable from the address bar.
    }
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <img alt="Portfolio Backtester" className="mark" src="/brand/topbar-mark.png" />
          <span>Portfolio Backtester</span>
          <span className="tag">Historical portfolio backtesting</span>
          {navAsOf ? <span className="tag nav-as-of">NAV data as of {formatNavDate(navAsOf)}</span> : null}
        </div>
        <Stepper currentStep={currentStep} unlockedStep={unlockedStep} onStepClick={goToStep} />
        <button className="theme-toggle" onClick={() => setTheme((current) => (current === "light" ? "dark" : "light"))} type="button">
          Toggle theme
        </button>
      </header>

      <div className="main">
        <PortfolioStep
          active={currentStep === 0}
          funds={funds}
          onAssetsChange={handleAssetsChange}
          onContinue={() => advanceTo(1)}
        />
        <AssumptionsStep
          active={currentStep === 1}
          request={request}
          funds={funds}
          fieldErrors={fieldErrors}
          validationErrors={validationErrors}
          navStart={navStart}
          navAsOf={navAsOf}
          testableRange={testableRange}
          error={error}
          loading={loading}
          onChange={updateRequest}
          onBack={() => goToStep(0)}
          onRun={submit}
        />
        <div className={currentStep === 2 ? "page active" : "page"}>
          <RunSummary result={result} />
          <div className="actions">
            <button className="btn btn-ghost" onClick={() => goToStep(1)} type="button">&larr; Adjust assumptions</button>
            <button className="btn btn-ghost" onClick={startOver} type="button">Start a new portfolio</button>
            {result ? (
              <button className="btn btn-ghost" onClick={copyShareLink} type="button">
                {linkCopied ? "Link copied" : "Copy shareable link"}
              </button>
            ) : null}
          </div>
        </div>
      </div>

      <footer className="app-footer">
        <img alt="Supachok Julaupay signature mark" className="app-footer-mark" src={theme === "dark" ? "/brand/author-logo-dark.png" : "/brand/author-logo-light.png"} />
        <div className="app-footer-text">
          <span className="app-footer-name">Supachok Julaupay</span>
          <a href="https://github.com/bblank09" rel="noreferrer" target="_blank">github.com/bblank09</a>
        </div>
      </footer>

      <RunOverlay open={loading} />
    </div>
  );
}

function formatNavDate(isoDate: string): string {
  const parsed = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return isoDate;
  return parsed.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}

function validateRequest(request: BacktestRequest, totalWeight: number): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!request.assets.length) errors.assets = "Add at least one SEC fund.";
  if (Math.abs(totalWeight - 100) > 0.01) errors.assets = `Weights sum to ${totalWeight.toFixed(1)}%, not 100%.`;
  if (!request.benchmark_proj_id) errors.benchmark = "Select a benchmark SEC fund.";
  if (new Date(request.start_date) >= new Date(request.end_date)) {
    errors.endDate = "Start date must be before end date.";
  }
  if (!(request.initial_capital > 0)) errors.initialCapital = "Initial capital must be greater than zero.";
  if (request.cashflow.enabled && !(request.cashflow.amount > 0)) {
    errors.cashflowAmount = "Cashflow amount must be greater than zero when cashflow is enabled.";
  }
  return errors;
}
