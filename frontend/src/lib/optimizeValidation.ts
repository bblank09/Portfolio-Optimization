import type { OptimizeRequest } from "../types/optimize";

function isFiniteNumber(value: number): boolean {
  return Number.isFinite(value);
}

function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

/**
 * Validate the request before the user can start an expensive optimization.
 * The API remains the source of truth; this mirrors the checks that are easy
 * to explain inline so malformed requests fail at the form rather than after
 * a loading overlay has already started.
 */
export function validateOptimizeRequest(request: OptimizeRequest): string[] {
  const errors: string[] = [];
  const selectedIds = new Set(request.funds.map((fund) => fund.proj_id));

  if (request.funds.length < 2) errors.push("Select at least 2 funds.");
  if (request.goal === "black_litterman" && request.returnMethod !== "black_litterman_posterior") {
    errors.push("Black-Litterman objective requires the Black-Litterman posterior return method.");
  }
  if (request.goal !== "black_litterman" && request.returnMethod === "black_litterman_posterior") {
    errors.push("Black-Litterman posterior returns require the Black-Litterman objective.");
  }
  if (!isIsoDate(request.timePeriod.startDate) || !isIsoDate(request.timePeriod.endDate)) {
    errors.push("Enter valid start and end dates.");
  } else if (request.timePeriod.startDate > request.timePeriod.endDate) {
    errors.push("Start date must be on or before end date.");
  }

  const constraints = request.constraints;
  if (!isFiniteNumber(constraints.minWeightPct) || !isFiniteNumber(constraints.maxWeightPct)) {
    errors.push("Global weight bounds must be finite numbers.");
  } else if (constraints.minWeightPct > constraints.maxWeightPct) {
    errors.push("Global minimum weight cannot exceed the maximum weight.");
  }
  if (constraints.longOnly && constraints.minWeightPct < 0) {
    errors.push("Long-only optimization cannot use a negative minimum weight.");
  }
  if (!Number.isInteger(constraints.maxHoldings) || constraints.maxHoldings < 1) {
    errors.push("Maximum holdings must be at least 1.");
  }
  if (!Number.isInteger(constraints.lookbackPeriodMonths) || constraints.lookbackPeriodMonths < 1) {
    errors.push("Lookback period must be at least 1 month.");
  }
  if (constraints.maxTurnoverPct !== null && (!isFiniteNumber(constraints.maxTurnoverPct) || constraints.maxTurnoverPct < 0)) {
    errors.push("Maximum turnover must be a non-negative finite number.");
  }
  if (constraints.maxTrackingErrorPct !== null && (!isFiniteNumber(constraints.maxTrackingErrorPct) || constraints.maxTrackingErrorPct < 0)) {
    errors.push("Maximum tracking error must be a non-negative finite number.");
  }
  if (constraints.maxTrackingErrorPct !== null && !request.benchmarkProjId) {
    errors.push("Choose a benchmark before setting a tracking-error cap.");
  }

  for (const [projId, bound] of Object.entries(request.fundBounds)) {
    if (!isFiniteNumber(bound.minWeightPct) || !isFiniteNumber(bound.maxWeightPct)) {
      errors.push(`Weight bounds for ${projId} must be finite numbers.`);
    } else if (bound.minWeightPct > bound.maxWeightPct) {
      errors.push(`Minimum weight cannot exceed maximum weight for ${projId}.`);
    }
    if (constraints.longOnly && bound.minWeightPct < 0) {
      errors.push(`Long-only optimization cannot use a negative minimum weight for ${projId}.`);
    }
  }

  if (constraints.groupConstraintsEnabled) {
    for (const [groupId, group] of Object.entries(request.assetGroups)) {
      if (!isFiniteNumber(group.minWeightPct) || !isFiniteNumber(group.maxWeightPct)) {
        errors.push(`Asset group ${groupId} bounds must be finite numbers.`);
      } else if (group.minWeightPct > group.maxWeightPct) {
        errors.push(`Minimum weight cannot exceed maximum weight for asset group ${groupId}.`);
      }
    }
  }

  for (const [projId, value] of Object.entries(request.currentWeightPct)) {
    if (!isFiniteNumber(value)) errors.push(`Current weight for ${projId} must be finite.`);
  }
  for (const [projId, value] of Object.entries(request.expectedReturnOverrides)) {
    if (!isFiniteNumber(value)) errors.push(`Expected return for ${projId} must be finite.`);
  }
  for (const [projId, value] of Object.entries(request.volatilityOverrides)) {
    if (!isFiniteNumber(value) || value < 0) errors.push(`Expected volatility for ${projId} must be a non-negative finite number.`);
  }
  for (const [key, value] of Object.entries(request.correlationOverrides)) {
    const [asset1, asset2, extra] = key.split("|");
    if (extra || !asset1 || !asset2 || asset1 === asset2 || !selectedIds.has(asset1) || !selectedIds.has(asset2)) {
      errors.push(`Correlation override ${key} must name two distinct selected funds.`);
    }
    if (!isFiniteNumber(value) || value < -1 || value > 1) {
      errors.push(`Correlation override ${key} must be between -1 and 1.`);
    }
  }

  if (request.benchmarkProjId && !selectedIds.has(request.benchmarkProjId)) {
    errors.push("Benchmark must be one of the selected funds.");
  }

  if (request.blackLitterman) {
    const bl = request.blackLitterman;
    if (!isFiniteNumber(bl.riskAversion) || bl.riskAversion <= 0) errors.push("Black-Litterman risk aversion must be positive.");
    if (!isFiniteNumber(bl.tau) || bl.tau <= 0) errors.push("Black-Litterman tau must be positive.");
    if (!isFiniteNumber(bl.benchmarkExpectedReturnPct)) errors.push("Black-Litterman benchmark return must be finite.");
    for (const view of bl.views) {
      if (!selectedIds.has(view.assetProjId1)) errors.push("Each Black-Litterman view must use a selected fund as asset 1.");
      if (view.viewType === "relative" && (!view.assetProjId2 || !selectedIds.has(view.assetProjId2) || view.assetProjId2 === view.assetProjId1)) {
        errors.push("Each relative Black-Litterman view must use a different selected fund as asset 2.");
      }
      if (!isFiniteNumber(view.adjustedPerformancePct) || !isFiniteNumber(view.confidence)) {
        errors.push("Black-Litterman view values must be finite numbers.");
      }
    }
  }

  return [...new Set(errors)];
}
