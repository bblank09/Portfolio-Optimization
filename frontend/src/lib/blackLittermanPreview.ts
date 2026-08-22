// Live client-side preview of Black-Litterman's market-equilibrium implied
// returns (Pi) -- shown in the Assumptions step's BL card WHILE the user
// adjusts risk aversion/tau, before running the optimization. BL views are
// meaningless without first seeing what the model already implies ("I
// think fund X will beat what the market/equilibrium implies"), so the UI
// needs this preview ahead of a full run, not only inside the eventual
// Results tab. This is a deterministic client-side estimate for display
// only -- the real equilibrium-return computation used by the optimizer
// itself lives server-side in backend/app/optimizer/black_litterman.py.
import type { OptimizeRequest } from "../types/optimize";

// Small deterministic PRNG (mulberry32) seeded from a string -- avoids a
// dependency, and guarantees the same fund selection + assumptions always
// render the same preview numbers.
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
    request.targetAnnualReturnPct ?? "",
    request.robustOptimization,
    request.covarianceMethod,
    request.benchmarkProjId ?? "",
    request.tailConfidence,
    request.dataFrequency,
    request.blackLitterman?.riskAversion ?? "",
    request.blackLitterman?.tau ?? "",
    request.blackLitterman?.benchmarkExpectedReturnPct ?? "",
    ...(request.blackLitterman?.views ?? []).flatMap((view) => [
      view.assetProjId1,
      view.assetProjId2 ?? "",
      view.viewType,
      view.adjustedPerformancePct,
      view.confidence
    ])
  ].join("|");
}

export function estimateEquilibriumReturns(request: OptimizeRequest): Record<string, number> {
  const rand = seededRandom(requestSeed(request));
  const result: Record<string, number> = {};
  for (const fund of request.funds) {
    const equityish = /ตราสารทุน|ผสม/.test(fund.policy_desc);
    const baseReturn = equityish ? 8 + rand() * 6 : 2 + rand() * 3;
    const expectedReturnPct = !request.useHistoricalReturns && request.expectedReturnOverrides[fund.proj_id] !== undefined
      ? request.expectedReturnOverrides[fund.proj_id]
      : baseReturn;
    result[fund.proj_id] = Number((expectedReturnPct * 0.8).toFixed(2));
  }
  return result;
}
