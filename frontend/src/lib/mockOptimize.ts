// Phase 4 mock only. There is no backend optimizer yet (Phase 5) -- this
// module stands in for a real POST /api/optimize call so the UI can be
// built, reviewed, and iterated on before any real math exists. Every
// number here is deterministically derived from the request (same inputs
// always produce the same outputs, so screenshots/demos are reproducible)
// but is NOT a real optimization -- do not treat any value as a real
// portfolio recommendation.
import type { SecFund } from "../types/backtest";
import type {
  AssetSummaryRow,
  FeasibilityStatus,
  FrontierPoint,
  OptimizeRequest,
  OptimizeResult,
  PerformanceSummaryColumn,
  RollingFold
} from "../types/optimize";

// Small deterministic PRNG (mulberry32) seeded from a string -- avoids a
// dependency, and guarantees the same fund selection + assumptions always
// render the same mock numbers.
function seededRandom(seed: string): () => number {
  let h = 1779033703 ^ seed.length;
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  let a = h >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function requestSeed(request: OptimizeRequest): string {
  return [
    request.funds.map((f) => f.proj_id).sort().join(","),
    request.goal,
    request.riskMeasure,
    request.targetAnnualVolatilityPct ?? "",
    request.robustOptimization,
    request.covarianceMethod
  ].join("|");
}

export function runMockOptimize(request: OptimizeRequest): OptimizeResult {
  const feasibility = evaluateFeasibility(request);
  if (feasibility.status !== "ok") {
    return {
      feasibility: feasibility.status,
      feasibilityMessage: feasibility.message,
      robustNote: null,
      optimalWeights: {},
      compareWeights: null,
      riskContributionPct: {},
      frontier: [],
      assetSummary: [],
      correlations: [],
      performanceSummary: [],
      rolling: [],
      blackLitterman: null
    };
  }

  const rand = seededRandom(requestSeed(request));
  const funds = request.funds;

  // Per-asset synthetic expected return / volatility, loosely bucketed by
  // policy_desc so equity-labeled funds read higher-return/higher-vol than
  // fixed-income-labeled ones -- plausible-looking, not computed. When
  // useHistoricalReturns is off, honor the user's own per-fund override
  // (Step 2's "Expected return per fund" table) instead of the synthetic
  // value -- otherwise that field would be pure decoration.
  const perAsset = funds.map((fund) => {
    const equityish = /ตราสารทุน|ผสม/.test(fund.policy_desc);
    const baseReturn = equityish ? 8 + rand() * 6 : 2 + rand() * 3;
    const baseVol = equityish ? 12 + rand() * 10 : 3 + rand() * 4;
    const expectedReturnPct = !request.useHistoricalReturns && request.expectedReturnOverrides[fund.proj_id] !== undefined
      ? request.expectedReturnOverrides[fund.proj_id]
      : baseReturn;
    return { fund, expectedReturnPct, volatilityPct: baseVol };
  });

  const optimalWeights = applyGroupMaxClamp(allocateWeights(perAsset, request, rand), request);
  const compareWeights = buildCompareWeights(perAsset, request.constraints.compareAgainst);
  const riskContributionPct = deriveRiskContribution(perAsset, optimalWeights);
  const frontier = buildFrontier(perAsset, rand);
  const assetSummary = buildAssetSummary(perAsset, request);
  const correlations = buildCorrelations(funds, rand);
  const performanceSummary = buildPerformanceSummary(optimalWeights, compareWeights, perAsset, request, rand);
  const rolling = buildRollingFolds(request, rand);
  const blackLitterman = request.goal === "black_litterman" && request.blackLitterman
    ? buildBlackLitterman(perAsset, request)
    : null;

  return {
    feasibility: "ok",
    feasibilityMessage: null,
    robustNote: request.robustOptimization
      ? "Monte Carlo resampling applied to the optimization inputs to mitigate estimation error and improve diversification (PortfolioVisualizer's own description of this toggle)."
      : null,
    optimalWeights,
    compareWeights,
    riskContributionPct,
    frontier,
    assetSummary,
    correlations,
    performanceSummary,
    rolling,
    blackLitterman
  };
}

function evaluateFeasibility(request: OptimizeRequest): { status: FeasibilityStatus; message: string | null } {
  if (request.funds.length < 2) {
    return { status: "insufficient_data", message: "Select at least 2 funds to run an optimization." };
  }
  const minHistory = Math.min(...request.funds.map((f) => f.nav_span_months ?? 0));
  const neededMonths = request.constraints.lookbackPeriodMonths;
  if (minHistory > 0 && minHistory < neededMonths) {
    return {
      status: "insufficient_data",
      message: `At least one selected fund has only ${minHistory} months of NAV history, less than the ${neededMonths}-month lookback period selected in Constraints. Shorten the lookback period or remove that fund.`
    };
  }
  // Sum of each fund's own minimum (per-fund override from Step 1, or the
  // constraints-level default for any fund without one) -- not just the
  // global default times fund count, now that bounds can differ per fund.
  const totalMinWeight = request.funds.reduce(
    (sum, fund) => sum + (request.fundBounds[fund.proj_id]?.minWeightPct ?? request.constraints.minWeightPct),
    0
  );
  if (totalMinWeight > 100) {
    return {
      status: "infeasible_constraints",
      message: `The selected funds' minimum weights add up to ${totalMinWeight.toFixed(1)}%, more than 100% total allocation. Lower one or more minimums (Step 1) or add more funds.`
    };
  }
  if (request.constraints.maxHoldings > 0 && request.constraints.maxHoldings < request.funds.length && totalMinWeight > 0) {
    return {
      status: "infeasible_constraints",
      message: `Max holdings (${request.constraints.maxHoldings}) is less than the number of selected funds (${request.funds.length}) while a minimum weight is also set -- the solver has no valid combination that satisfies both. Raise max holdings, remove the minimum weights, or deselect funds.`
    };
  }
  if (request.constraints.groupConstraintsEnabled) {
    for (const id of Object.keys(request.assetGroups) as (keyof typeof request.assetGroups)[]) {
      const group = request.assetGroups[id];
      const memberCount = request.funds.filter((fund) => request.fundGroups[fund.proj_id] === id).length;
      if (group.minWeightPct > 0 && memberCount === 0) {
        return {
          status: "infeasible_constraints",
          message: `Group ${id}${group.name ? ` (${group.name})` : ""} has a minimum weight of ${group.minWeightPct}% but no funds are assigned to it. Assign a fund to group ${id} in the Portfolio step, or clear its minimum.`
        };
      }
      if (group.minWeightPct > group.maxWeightPct) {
        return {
          status: "infeasible_constraints",
          message: `Group ${id}${group.name ? ` (${group.name})` : ""} has a minimum weight (${group.minWeightPct}%) greater than its maximum (${group.maxWeightPct}%).`
        };
      }
    }
  }
  return { status: "ok", message: null };
}

// Approximate group-level cap: if a group's total exceeds its Max %, scale
// that group's members down to hit it and spread the freed percentage
// across every fund outside the group, proportional to their existing
// weight. This does not re-check those funds' own max bounds while
// redistributing (a full simultaneous fund+group constrained solve is out
// of scope for a Phase 4 mock) -- Phase 5's real optimizer would enforce
// both simultaneously. Group minimums are only feasibility-checked
// upstream (evaluateFeasibility), not enforced here.
function applyGroupMaxClamp(weights: Record<string, number>, request: OptimizeRequest): Record<string, number> {
  if (!request.constraints.groupConstraintsEnabled) return weights;
  let result = { ...weights };
  for (const id of Object.keys(request.assetGroups) as (keyof typeof request.assetGroups)[]) {
    const group = request.assetGroups[id];
    const memberIds = request.funds.filter((fund) => request.fundGroups[fund.proj_id] === id).map((fund) => fund.proj_id);
    if (!memberIds.length) continue;
    const groupTotal = memberIds.reduce((sum, projId) => sum + (result[projId] ?? 0), 0);
    if (groupTotal <= group.maxWeightPct || groupTotal <= 0) continue;
    const scale = group.maxWeightPct / groupTotal;
    const freed = groupTotal - group.maxWeightPct;
    const outsideIds = Object.keys(result).filter((projId) => !memberIds.includes(projId));
    const outsideTotal = outsideIds.reduce((sum, projId) => sum + (result[projId] ?? 0), 0);
    const next: Record<string, number> = { ...result };
    for (const projId of memberIds) next[projId] = (result[projId] ?? 0) * scale;
    for (const projId of outsideIds) {
      const share = outsideTotal > 0 ? (result[projId] ?? 0) / outsideTotal : 1 / outsideIds.length;
      next[projId] = (result[projId] ?? 0) + freed * share;
    }
    result = next;
  }
  const rounded: Record<string, number> = {};
  for (const [id, w] of Object.entries(result)) rounded[id] = Number(w.toFixed(2));
  return rounded;
}

function allocateWeights(
  perAsset: { fund: SecFund; expectedReturnPct: number; volatilityPct: number }[],
  request: OptimizeRequest,
  rand: () => number
): Record<string, number> {
  // Objective-flavored raw scores: risk_parity/hrp lean toward inverse-vol,
  // return-seeking objectives lean toward return/vol (a crude Sharpe proxy).
  const scores = perAsset.map(({ fund, expectedReturnPct, volatilityPct }) => {
    let score: number;
    if (request.goal === "risk_parity" || request.goal === "hrp" || request.goal === "min_variance") {
      score = 1 / Math.max(volatilityPct, 0.5);
    } else {
      score = Math.max(expectedReturnPct / Math.max(volatilityPct, 0.5), 0.05);
    }
    // Robust optimization softens extreme scores toward equal-weight,
    // echoing PV's own description: resampling "improves diversification".
    if (request.robustOptimization) score = score * 0.6 + (1 / perAsset.length) * 0.4 * 10;
    return { projId: fund.proj_id, score: score * (0.9 + rand() * 0.2) };
  });
  const totalScore = scores.reduce((sum, s) => sum + s.score, 0);
  const raw: Record<string, number> = {};
  for (const s of scores) raw[s.projId] = (s.score / totalScore) * 100;

  // Per-fund bounds (Step 1 asset table) win over the constraints-level
  // default -- confirmed live against PV, whose Min./Max. Weight columns
  // live per-asset, not as one global pair.
  const bounds: Record<string, { min: number; max: number }> = {};
  for (const { fund } of perAsset) {
    const perFund = request.fundBounds[fund.proj_id];
    bounds[fund.proj_id] = {
      min: perFund?.minWeightPct ?? request.constraints.minWeightPct,
      max: perFund?.maxWeightPct ?? request.constraints.maxWeightPct
    };
  }
  return clampAndRenormalize(raw, bounds);
}

// Redistributes `raw` shares to sum to exactly 100% while respecting each
// id's [min, max] bound -- a plain "clamp then scale every value by
// 100/total" (the previous implementation) re-violates the bounds it just
// applied, because scaling up pushes already-at-max entries back over their
// cap. This is a standard bounded water-filling pass: repeatedly clamp,
// lock any entry that hit a bound at that bound, and redistribute the
// remainder proportionally among the still-free entries, until nothing
// new gets clamped (or bounds are numerically infeasible and the caller's
// evaluateFeasibility should have already rejected the request).
function clampAndRenormalize(raw: Record<string, number>, bounds: Record<string, { min: number; max: number }>): Record<string, number> {
  const ids = Object.keys(raw);
  const result: Record<string, number> = {};
  const locked = new Set<string>();

  for (let pass = 0; pass < ids.length + 1; pass++) {
    const freeIds = ids.filter((id) => !locked.has(id));
    if (freeIds.length === 0) break;

    const lockedTotal = [...locked].reduce((sum, id) => sum + result[id], 0);
    const remaining = 100 - lockedTotal;
    const freeRawTotal = freeIds.reduce((sum, id) => sum + raw[id], 0);

    let newlyLocked = false;
    for (const id of freeIds) {
      const bound = bounds[id] ?? { min: 0, max: 100 };
      const share = freeRawTotal > 0 ? (raw[id] / freeRawTotal) * remaining : remaining / freeIds.length;
      if (share <= bound.min) {
        result[id] = bound.min;
        locked.add(id);
        newlyLocked = true;
      } else if (share >= bound.max) {
        result[id] = bound.max;
        locked.add(id);
        newlyLocked = true;
      } else {
        result[id] = share;
      }
    }
    if (!newlyLocked) break;
  }

  const rounded: Record<string, number> = {};
  for (const id of ids) rounded[id] = Number((result[id] ?? 0).toFixed(2));
  return rounded;
}

function buildCompareWeights(
  perAsset: { fund: SecFund; expectedReturnPct: number; volatilityPct: number }[],
  compareAgainst: OptimizeRequest["constraints"]["compareAgainst"]
): Record<string, number> | null {
  if (compareAgainst === "none") return null;
  if (compareAgainst === "equal_weighted") {
    const weight = Number((100 / perAsset.length).toFixed(2));
    const result: Record<string, number> = {};
    for (const { fund } of perAsset) result[fund.proj_id] = weight;
    return result;
  }
  if (compareAgainst === "inverse_volatility") {
    const inv = perAsset.map(({ fund, volatilityPct }) => ({ id: fund.proj_id, w: 1 / Math.max(volatilityPct, 0.5) }));
    const total = inv.reduce((s, x) => s + x.w, 0);
    const result: Record<string, number> = {};
    for (const x of inv) result[x.id] = Number(((x.w / total) * 100).toFixed(2));
    return result;
  }
  // max_sharpe / risk_parity comparisons reuse the same shape as equal-weight
  // for this mock -- Phase 5 would compute each properly.
  const weight = Number((100 / perAsset.length).toFixed(2));
  const result: Record<string, number> = {};
  for (const { fund } of perAsset) result[fund.proj_id] = weight;
  return result;
}

function deriveRiskContribution(
  perAsset: { fund: SecFund; volatilityPct: number }[],
  weights: Record<string, number>
): Record<string, number> {
  const raw = perAsset.map(({ fund, volatilityPct }) => ({
    id: fund.proj_id,
    v: (weights[fund.proj_id] ?? 0) * volatilityPct
  }));
  const total = raw.reduce((s, x) => s + x.v, 0) || 1;
  const result: Record<string, number> = {};
  for (const x of raw) result[x.id] = Number(((x.v / total) * 100).toFixed(2));
  return result;
}

function buildFrontier(
  perAsset: { fund: SecFund; expectedReturnPct: number; volatilityPct: number }[],
  rand: () => number
): FrontierPoint[] {
  const minVol = Math.min(...perAsset.map((a) => a.volatilityPct)) * 0.85;
  const maxVol = Math.max(...perAsset.map((a) => a.volatilityPct)) * 1.05;
  const minRet = Math.min(...perAsset.map((a) => a.expectedReturnPct));
  const maxRet = Math.max(...perAsset.map((a) => a.expectedReturnPct));
  // A real efficient frontier is smooth and concave (diminishing return per
  // unit of extra risk) -- a small per-point jitter, seeded once rather than
  // per-point, keeps the mock looking plausible without a jagged sawtooth.
  const jitterSeed = (rand() - 0.5) * 0.4;
  const points: FrontierPoint[] = [];
  const steps = 24;
  for (let i = 0; i < steps; i++) {
    const t = i / (steps - 1);
    const vol = minVol + (maxVol - minVol) * t;
    const ret = minRet + (maxRet - minRet) * Math.sqrt(t) + jitterSeed * Math.sin(t * Math.PI);
    const sharpe = vol > 0 ? ret / vol : 0;
    const weights: Record<string, number> = {};
    for (const a of perAsset) weights[a.fund.proj_id] = Number((100 / perAsset.length).toFixed(2));
    points.push({ volatilityPct: Number(vol.toFixed(2)), expectedReturnPct: Number(ret.toFixed(2)), sharpe: Number(sharpe.toFixed(3)), weights });
  }
  return points;
}

function buildAssetSummary(
  perAsset: { fund: SecFund; expectedReturnPct: number; volatilityPct: number }[],
  request: OptimizeRequest
): AssetSummaryRow[] {
  return perAsset.map(({ fund, expectedReturnPct, volatilityPct }) => ({
    projId: fund.proj_id,
    displayName: fund.display_name,
    expectedReturnPct: Number(expectedReturnPct.toFixed(2)),
    volatilityPct: Number(volatilityPct.toFixed(2)),
    sharpe: Number((expectedReturnPct / Math.max(volatilityPct, 0.5)).toFixed(3)),
    minWeightPct: request.fundBounds[fund.proj_id]?.minWeightPct ?? request.constraints.minWeightPct,
    maxWeightPct: request.fundBounds[fund.proj_id]?.maxWeightPct ?? request.constraints.maxWeightPct
  }));
}

function buildCorrelations(funds: SecFund[], rand: () => number) {
  const result: { projId1: string; projId2: string; correlation: number }[] = [];
  for (let i = 0; i < funds.length; i++) {
    for (let j = i + 1; j < funds.length; j++) {
      const sameCategory = funds[i].policy_desc === funds[j].policy_desc;
      const base = sameCategory ? 0.55 : 0.15;
      const correlation = Math.max(-0.6, Math.min(0.95, base + (rand() - 0.5) * 0.5));
      result.push({ projId1: funds[i].proj_id, projId2: funds[j].proj_id, correlation: Number(correlation.toFixed(2)) });
    }
  }
  return result;
}

function buildPerformanceSummary(
  optimalWeights: Record<string, number>,
  compareWeights: Record<string, number> | null,
  perAsset: { fund: SecFund; expectedReturnPct: number; volatilityPct: number }[],
  request: OptimizeRequest,
  rand: () => number
): PerformanceSummaryColumn[] {
  function columnFor(weights: Record<string, number>, label: string): PerformanceSummaryColumn {
    const expectedReturn = perAsset.reduce((s, a) => s + (weights[a.fund.proj_id] ?? 0) / 100 * a.expectedReturnPct, 0);
    const stdDev = Math.sqrt(
      perAsset.reduce((s, a) => s + Math.pow(((weights[a.fund.proj_id] ?? 0) / 100) * a.volatilityPct, 2), 0)
    );
    const sharpe = stdDev > 0 ? (expectedReturn - request.constraints.riskFreeRatePct) / stdDev : 0;
    return {
      label,
      cagrPct: Number((expectedReturn - rand() * 0.8).toFixed(2)),
      expectedReturnPct: Number(expectedReturn.toFixed(2)),
      stdDevPct: Number(stdDev.toFixed(2)),
      bestYearPct: Number((expectedReturn + stdDev * (1.4 + rand())).toFixed(2)),
      worstYearPct: Number((expectedReturn - stdDev * (1.4 + rand())).toFixed(2)),
      maxDrawdownPct: Number((-(stdDev * (1.2 + rand()))).toFixed(2)),
      sharpeExAnte: Number(sharpe.toFixed(2)),
      sharpeExPost: Number((sharpe * (0.85 + rand() * 0.3)).toFixed(2)),
      sortino: Number((sharpe * (1.1 + rand() * 0.3)).toFixed(2))
    };
  }
  const columns = [columnFor(optimalWeights, "Optimized")];
  if (compareWeights) {
    const label = request.constraints.compareAgainst === "equal_weighted" ? "Equal Weighted"
      : request.constraints.compareAgainst === "inverse_volatility" ? "Inverse Volatility"
      : request.constraints.compareAgainst === "max_sharpe" ? "Max Sharpe Ratio Weights"
      : "Risk Parity Weighted";
    columns.push(columnFor(compareWeights, label));
  }
  return columns;
}

function buildRollingFolds(request: OptimizeRequest, rand: () => number): RollingFold[] {
  const foldCount = request.constraints.optimizationFrequency === "monthly" ? 12
    : request.constraints.optimizationFrequency === "quarterly" ? 8 : 5;
  const folds: RollingFold[] = [];
  for (let i = 0; i < foldCount; i++) {
    folds.push({
      periodLabel: `Fold ${i + 1}`,
      realizedReturnPct: Number((4 + rand() * 10 - 3).toFixed(2)),
      realizedVolatilityPct: Number((6 + rand() * 8).toFixed(2)),
      realizedSharpe: Number((rand() * 1.2 - 0.1).toFixed(2))
    });
  }
  return folds;
}

function buildBlackLitterman(
  perAsset: { fund: SecFund; expectedReturnPct: number; volatilityPct: number }[],
  request: OptimizeRequest
) {
  const equilibriumReturnPct: Record<string, number> = {};
  const adjustedReturnPct: Record<string, number> = {};
  const bl = request.blackLitterman!;
  for (const { fund, expectedReturnPct } of perAsset) {
    equilibriumReturnPct[fund.proj_id] = Number((expectedReturnPct * 0.8).toFixed(2));
    const view = bl.views.find((v) => v.assetProjId1 === fund.proj_id);
    const pull = view ? (view.adjustedPerformancePct - equilibriumReturnPct[fund.proj_id]) * (view.confidence / 100) : 0;
    adjustedReturnPct[fund.proj_id] = Number((equilibriumReturnPct[fund.proj_id] + pull).toFixed(2));
  }
  return { equilibriumReturnPct, adjustedReturnPct };
}
