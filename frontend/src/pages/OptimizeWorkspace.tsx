import { useEffect, useMemo, useState } from "react";
import { fetchDataStatus, fetchFunds, fetchOptimizeByRunId, fetchTestableRange, runOptimize } from "../api/client";
import DarkVeil from "../components/DarkVeil";
import { OptimizeAssumptionsStep } from "../components/OptimizeAssumptionsStep";
import { OptimizeResults } from "../components/OptimizeResults";
import { PortfolioStep } from "../components/PortfolioStep";
import { RunOverlay } from "../components/RunOverlay";
import { Stepper } from "../components/Stepper";
import type { SecFund, SecFundAllocation } from "../types/backtest";
import { ASSET_GROUP_IDS } from "../types/optimize";
import type { AssetGroup, AssetGroupId, OptimizeRequest, OptimizeResult } from "../types/optimize";

const COMPARE_LABELS: Record<OptimizeRequest["constraints"]["compareAgainst"], string | null> = {
  none: null,
  equal_weighted: "Equal Weighted",
  max_sharpe: "Max Sharpe Ratio Weights",
  inverse_volatility: "Inverse Volatility Weighted",
  risk_parity: "Risk Parity Weighted",
  current: "Your Current Portfolio"
};

function defaultAssetGroups(): Record<AssetGroupId, AssetGroup> {
  const groups = {} as Record<AssetGroupId, AssetGroup>;
  for (const id of ASSET_GROUP_IDS) groups[id] = { name: "", minWeightPct: 0, maxWeightPct: 100 };
  return groups;
}

// Reasonable default window: about 5 years back from the SEC cache's
// approximate freshness -- the sibling backtester's own AssumptionsStep
// uses the same "recent N years" framing for its range presets.
const initialRequest: OptimizeRequest = {
  funds: [],
  fundBounds: {},
  currentWeightPct: {},
  fundGroups: {},
  assetGroups: defaultAssetGroups(),
  timePeriod: { startDate: "2020-01-31", endDate: "2026-07-31" },
  dataFrequency: "monthly",
  goal: "max_sharpe",
  riskMeasure: "std_dev",
  tailConfidence: 95,
  targetAnnualVolatilityPct: 10,
  targetAnnualReturnPct: 6,
  robustOptimization: false,
  useHistoricalReturns: true,
  useHistoricalVolatility: true,
  useHistoricalCorrelations: true,
  expectedReturnOverrides: {},
  volatilityOverrides: {},
  correlationOverrides: {},
  returnMethod: "historical_mean",
  covarianceMethod: "sample",
  blackLitterman: null,
  benchmarkProjId: null,
  constraints: {
    longOnly: true,
    minWeightPct: 0,
    maxWeightPct: 100,
    groupConstraintsEnabled: false,
    maxHoldings: 20,
    lookbackPeriodMonths: 36,
    optimizationFrequency: "quarterly",
    riskFreeRatePct: 1.5,
    compareAgainst: "equal_weighted",
    maxTurnoverPct: null,
    maxTrackingErrorPct: null,
    rollingWindowMode: "expanding"
  }
};

// Keep the old request-in-URL format readable so links copied before persisted
// optimization runs were introduced do not break. New runs use the much
// smaller server-issued ?run=<run_id> URL and load the saved result directly.
type SharedRequest = Omit<OptimizeRequest, "funds"> & { fundProjIds: string[] };

function encodeShareState(request: OptimizeRequest): string {
  const { funds, ...rest } = request;
  const shared: SharedRequest = { ...rest, fundProjIds: funds.map((f) => f.proj_id) };
  return btoa(encodeURIComponent(JSON.stringify(shared)));
}

function decodeShareState(raw: string): SharedRequest | null {
  try {
    const decoded = JSON.parse(decodeURIComponent(atob(raw))) as SharedRequest;
    // A link shared before a constraint field existed decodes without it,
    // leaving e.g. constraints.rollingWindowMode undefined -- which makes
    // the Assumptions <select> bound to it flip from controlled to
    // uncontrolled (React warns, and the field renders blank). Layer the
    // current defaults underneath whatever the link actually carried so an
    // older link is upgraded to a complete request instead of a partial one.
    return {
      ...decoded,
      constraints: { ...initialRequest.constraints, ...decoded.constraints }
    };
  } catch {
    return null;
  }
}

export function OptimizeWorkspace() {
  const [funds, setFunds] = useState<SecFund[]>([]);
  const [navAsOf, setNavAsOf] = useState<string | null>(null);
  const [request, setRequest] = useState<OptimizeRequest>(initialRequest);
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [unlockedStep, setUnlockedStep] = useState(0);
  const [linkCopied, setLinkCopied] = useState(false);
  const theme = "dark" as const;

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, []);

  useEffect(() => {
    fetchFunds()
      .then((loadedFunds) => setFunds(loadedFunds))
      .catch((caught: Error) => setError(caught.message));
  }, []);

  useEffect(() => {
    // Keep the optimizer's data-freshness marker in the same top-bar seam as
    // the sibling Monte Carlo app. This is best-effort metadata: a missing
    // status response should never block fund selection or optimization.
    fetchDataStatus()
      .then((status) => setNavAsOf(status.nav_as_of))
      .catch(() => setNavAsOf(null));
  }, []);

  // Restore a persisted shared run once funds are loaded. The saved request
  // only carries fund identity fields, so resolve those ids against the live
  // SEC catalog before hydrating the form. Keep the legacy ?state= path below
  // for links created by older versions of this page.
  useEffect(() => {
    if (!funds.length) return;
    const url = new URL(window.location.href);
    const runId = url.searchParams.get("run");
    if (runId) {
      let cancelled = false;
      setLoading(true);
      setError("");
      fetchOptimizeByRunId(runId)
        .then((savedRun) => {
          if (cancelled) return;
          const restoredFunds = savedRun.request.funds
            .map((fund) => funds.find((candidate) => candidate.proj_id === fund.projId))
            .filter((fund): fund is SecFund => Boolean(fund));
          if (restoredFunds.length < 2) {
            setError("Could not restore the shared optimization because one or more funds are no longer in the SEC catalog.");
            return;
          }
          const restoredRequest: OptimizeRequest = { ...savedRun.request, funds: restoredFunds };
          setRequest(restoredRequest);
          setResult(savedRun);
          setUnlockedStep(2);
          setCurrentStep(2);
        })
        .catch((caught: unknown) => {
          if (cancelled) return;
          setError(caught instanceof Error ? `Could not load shared optimization "${runId}": ${caught.message}` : `Could not load shared optimization "${runId}".`);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
      return () => {
        cancelled = true;
      };
    }

    const raw = url.searchParams.get("state");
    if (!raw) return;
    const shared = decodeShareState(raw);
    if (!shared) return;
    const { fundProjIds, ...rest } = shared;
    const restoredFunds = fundProjIds.map((id) => funds.find((f) => f.proj_id === id)).filter((f): f is SecFund => Boolean(f));
    const restored: OptimizeRequest = { ...(rest as OptimizeRequest), funds: restoredFunds };
    setRequest(restored);
    if (restoredFunds.length >= 2) {
      let cancelled = false;
      setLoading(true);
      setError("");
      runOptimize(restored)
        .then((restoredResult) => {
          if (cancelled) return;
          setResult(restoredResult);
          if (restoredResult.runId) replaceRunUrl(restoredResult.runId);
          setUnlockedStep(2);
          setCurrentStep(2);
        })
        .catch((caught: unknown) => {
          if (cancelled) return;
          // Malformed/stale shared state (e.g. a fund the cache no longer
          // covers) -- surface why, leave the user on Step 1 with the
          // restored selections instead of a silent, unexplained stall.
          setError(caught instanceof Error ? caught.message : "Could not restore the shared optimization.");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
      return () => {
        cancelled = true;
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [funds.length]);

  const selectedFunds = request.funds;

  // Same landmine fix as the backtester: "is this date range usable" must
  // come from GET /api/funds/testable-range (server-side, gap-aware), not
  // from naively intersecting each fund's own nav_start/nav_end -- that
  // misses gaps *inside* the range. See CLAUDE.md "Known landmines".
  const selectedProjIds = useMemo(
    () => [...new Set(request.funds.map((f) => f.proj_id))].sort(),
    [request.funds]
  );
  const [testableRange, setTestableRange] = useState<{ start: string | null; end: string | null }>({ start: null, end: null });

  useEffect(() => {
    if (!selectedProjIds.length) {
      setTestableRange({ start: null, end: null });
      return;
    }
    let ignore = false;
    fetchTestableRange(selectedProjIds)
      .then((range) => {
        if (ignore) return;
        setTestableRange(range);
        // The sibling backtester has this same client-side "don't re-clamp
        // an already-set date when the bound shrinks" gap, but it's caught
        // server-side (POST /api/backtests rejects an out-of-range request
        // with INSUFFICIENT_NAV_HISTORY, and POST /api/optimize does the
        // same). Re-clamp here too, the one place both bounds are known at
        // the same time, so a fund swap to a much narrower window doesn't
        // silently leave the date inputs holding a stale value below their
        // own new `min` until the request round-trips to the server.
        if (range.start && range.end) {
          setRequest((current) => {
            const clampedStart = current.timePeriod.startDate < range.start! ? range.start! : current.timePeriod.startDate > range.end! ? range.end! : current.timePeriod.startDate;
            const clampedEnd = current.timePeriod.endDate > range.end! ? range.end! : current.timePeriod.endDate < range.start! ? range.start! : current.timePeriod.endDate;
            if (clampedStart === current.timePeriod.startDate && clampedEnd === current.timePeriod.endDate) return current;
            return { ...current, timePeriod: { startDate: clampedStart, endDate: clampedEnd } };
          });
        }
      })
      .catch(() => { if (!ignore) setTestableRange({ start: null, end: null }); });
    return () => {
      ignore = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjIds.join(",")]);

  function goToStep(index: number) {
    setCurrentStep(index);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function advanceTo(index: number) {
    setUnlockedStep((current) => Math.max(current, index));
    goToStep(index);
  }

  // PortfolioStep is reused from the backtester with weightsOptional=true
  // and showWeightBounds=true -- confirmed live against PortfolioVisualizer's
  // own optimize-portfolio tool ("Portfolio asset weights and constraints
  // are optional", and its default "Asset Constraints: Yes" puts Min./Max.
  // Weight columns directly in the same asset table). The per-fund weight
  // itself feeds the trade-list/turnover computation server-side; the
  // per-fund min/max bounds are used as solver constraints. See
  // docs/mock-ui-spec.md Step 1.
  function handleAssetsChange(assets: SecFundAllocation[]) {
    setResult(null);
    setError("");
    const chosen = assets
      .map((a) => funds.find((f) => f.proj_id === a.proj_id))
      .filter((f): f is SecFund => Boolean(f));
    const fundBounds: OptimizeRequest["fundBounds"] = {};
    const fundGroups: OptimizeRequest["fundGroups"] = {};
    const currentWeightPct: OptimizeRequest["currentWeightPct"] = {};
    for (const asset of assets) {
      // Only record a per-fund override when it actually differs from Step
      // 1's row default (0/100) -- otherwise every fund silently carries an
      // explicit 0/100 bound that always wins over Constraints' "Default
      // min/max weight" fields (allocateWeights prefers fundBounds when
      // present), making that Assumptions field dead even when the user
      // never touched Step 1's Min/Max columns at all.
      const min = asset.min_weight_pct ?? 0;
      const max = asset.max_weight_pct ?? 100;
      if (min !== 0 || max !== 100) {
        fundBounds[asset.proj_id] = { minWeightPct: min, maxWeightPct: max };
      }
      fundGroups[asset.proj_id] = (asset.group as OptimizeRequest["fundGroups"][string]) ?? "None";
      currentWeightPct[asset.proj_id] = asset.weight ?? 0;
    }
    const chosenIds = new Set(chosen.map((f) => f.proj_id));
    setRequest((current) => {
      // Benchmark and Black-Litterman views reference a specific fund by
      // proj_id. If that fund gets removed here in Step 1, the reference
      // was never cleared -- the Assumptions page's <select> just silently
      // stopped rendering it as selected (no matching <option> left), while
      // request.benchmarkProjId / the view's assetProjId1/2 kept the stale
      // id in state. That's invisible until something reads it directly
      // (e.g. a future re-add of a same-id fund would silently "restore"
      // a benchmark the user never re-picked) -- clear it here instead of
      // leaving a dangling reference.
      const benchmarkProjId = current.benchmarkProjId && chosenIds.has(current.benchmarkProjId) ? current.benchmarkProjId : null;
      const blackLitterman = current.blackLitterman
        ? {
            ...current.blackLitterman,
            views: current.blackLitterman.views.filter(
              (view) => chosenIds.has(view.assetProjId1) && (view.assetProjId2 === null || chosenIds.has(view.assetProjId2))
            )
          }
        : current.blackLitterman;
      // Same staleness as benchmark/BL views: expected-return, volatility,
      // and correlation overrides are keyed by proj_id (correlation by
      // "idA|idB"), and none of them were ever pruned when a fund left the
      // shortlist -- removing a fund then re-adding it (or re-adding a
      // different fund that happens to reuse a freed slot) silently
      // restored whatever override value the *previous* occupant had,
      // with no way for the user to tell it wasn't a fresh default.
      const pruneByKey = (overrides: Record<string, number>) =>
        Object.fromEntries(Object.entries(overrides).filter(([id]) => chosenIds.has(id)));
      const expectedReturnOverrides = pruneByKey(current.expectedReturnOverrides);
      const volatilityOverrides = pruneByKey(current.volatilityOverrides);
      const correlationOverrides = Object.fromEntries(
        Object.entries(current.correlationOverrides).filter(([key]) => {
          const [id1, id2] = key.split("|");
          return chosenIds.has(id1) && chosenIds.has(id2);
        })
      );
      return {
        ...current,
        funds: chosen,
        fundBounds,
        fundGroups,
        currentWeightPct,
        benchmarkProjId,
        blackLitterman,
        expectedReturnOverrides,
        volatilityOverrides,
        correlationOverrides
      };
    });
  }

  function updateRequest(next: OptimizeRequest) {
    setResult(null);
    setError("");
    setRequest(next);
  }

  async function submit() {
    setLoading(true);
    setError("");
    try {
      const optimizeResult = await runOptimize(request);
      setResult(optimizeResult);
      if (optimizeResult.runId) replaceRunUrl(optimizeResult.runId);
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
    const url = new URL(window.location.href);
    url.searchParams.delete("run");
    url.searchParams.delete("state");
    window.history.replaceState(null, "", url);
  }

  function replaceRunUrl(runId: string) {
    const url = new URL(window.location.href);
    url.searchParams.set("run", runId);
    url.searchParams.delete("state");
    window.history.replaceState(null, "", url);
  }

  async function copyShareLink() {
    const url = new URL(window.location.href);
    if (result?.runId) {
      url.searchParams.set("run", result.runId);
      url.searchParams.delete("state");
    } else {
      // Resilience for a result produced by an older backend during a rolling
      // deploy: it can still be shared using the legacy request encoding.
      url.searchParams.set("state", encodeShareState(request));
      url.searchParams.delete("run");
    }
    window.history.replaceState(null, "", url);
    try {
      await navigator.clipboard.writeText(url.toString());
      setLinkCopied(true);
      window.setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      // Clipboard access can be denied by the browser -- fail silently,
      // the URL is still visible and copyable from the address bar.
    }
  }

  return (
    <div className="shell">
      <div aria-hidden="true" className="app-veil">
        <DarkVeil hueShift={342} scanlineFrequency={0.5} speed={1.5} />
      </div>
      <header className="topbar">
        <div className="brand">
          <img alt="Portfolio Optimization" className="mark" src="/brand/topbar-mark.png" />
          <span>Portfolio Optimizer</span>
          <span className="tag">Risk-aware portfolio construction</span>
          {navAsOf ? <span className="tag nav-as-of">NAV data as of {formatNavDate(navAsOf)}</span> : null}
        </div>
        <Stepper currentStep={currentStep} onStepClick={goToStep} unlockedStep={unlockedStep} />
      </header>

      <div className="main">
        <PortfolioStep
          active={currentStep === 0}
          allowShort={!request.constraints.longOnly}
          funds={funds}
          onAssetsChange={handleAssetsChange}
          onContinue={() => advanceTo(1)}
          showGroupAssignment={request.constraints.groupConstraintsEnabled}
          showWeightBounds
          weightsOptional
        />

        <OptimizeAssumptionsStep
          active={currentStep === 1}
          error={error}
          funds={funds}
          loading={loading}
          onBack={() => goToStep(0)}
          onChange={updateRequest}
          onRun={submit}
          request={request}
          testableRange={testableRange}
        />

        <div className={currentStep === 2 ? "page active" : "page"}>
          <OptimizeResults
            compareLabel={COMPARE_LABELS[request.constraints.compareAgainst]}
            funds={selectedFunds}
            request={request}
            result={result}
          />
          <div className="actions">
            <button className="btn btn-ghost" onClick={() => goToStep(1)} type="button">&larr; Adjust assumptions</button>
            <button className="btn btn-ghost" onClick={startOver} type="button">Start a new optimization</button>
            <button className="btn btn-ghost" onClick={copyShareLink} type="button">{linkCopied ? "Link copied" : "Copy shareable link"}</button>
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

      <RunOverlay
        open={loading}
        stages={["Validating inputs", "Estimating returns & covariance", "Solving optimization", "Preparing report"]}
        title="Running optimization…"
      />
    </div>
  );
}

function formatNavDate(isoDate: string): string {
  const parsed = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return isoDate;
  return parsed.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}
