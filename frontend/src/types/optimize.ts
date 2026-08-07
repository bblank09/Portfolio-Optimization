// Types for the Portfolio Optimization mock (Phase 4). No backend endpoint
// exists yet -- see lib/mockOptimize.ts for the deterministic mock that
// stands in for a real POST /api/optimize call. Field names/shapes here
// follow docs/mock-ui-spec.md, which is itself sourced against riskfolio-lib
// docs and a live walkthrough of PortfolioVisualizer's optimize-portfolio /
// efficient-frontier / rolling-optimization / black-litterman-model tools.

import type { SecFund } from "./backtest";

export type ObjectiveGoal =
  | "max_sharpe"
  | "min_volatility"
  | "max_return_target_vol"
  | "min_variance"
  | "risk_parity"
  | "black_litterman"
  | "hrp";

export type RiskMeasure = "std_dev" | "semi_variance" | "cvar" | "cdar";

export type ReturnEstimationMethod = "historical_mean" | "capm_implied" | "black_litterman_posterior";

export type CovarianceMethod = "sample" | "shrinkage" | "ewma";

export type CompareAgainst = "none" | "equal_weighted" | "max_sharpe" | "inverse_volatility" | "risk_parity";

export type ViewType = "absolute" | "relative";

// PV's own Step 2/3 confirmed live: confidence is a discrete 4-level
// dropdown (100/75/50/25), not a continuous slider -- see mock-ui-spec.md.
export type ViewConfidence = 100 | 75 | 50 | 25;

export interface BlackLittermanView {
  key: string;
  assetProjId1: string;
  viewType: ViewType;
  assetProjId2: string | null; // only used when viewType === "relative"
  adjustedPerformancePct: number; // Q
  confidence: ViewConfidence; // -> Omega, back-solved per Idzorek (2004)
}

export interface BlackLittermanInputs {
  riskAversion: number; // delta, default 2.5
  tau: number; // default 0.05
  benchmarkExpectedReturnPct: number; // whole-portfolio expected return feeding Pi
  views: BlackLittermanView[];
}

export interface OptimizeConstraints {
  longOnly: boolean;
  minWeightPct: number;
  maxWeightPct: number;
  groupConstraintsEnabled: boolean;
  maxHoldings: number;
  lookbackPeriodMonths: 12 | 24 | 36 | 48 | 60;
  optimizationFrequency: "monthly" | "quarterly" | "annually";
  riskFreeRatePct: number;
  compareAgainst: CompareAgainst;
}

export interface FundBound {
  minWeightPct: number;
  maxWeightPct: number;
}

// A-F fixed slots, matching PV's own Asset Groups table exactly (confirmed
// live: Group Constraints: Yes reveals 6 named groups, each with its own
// Min./Max. Weight).
export type AssetGroupId = "A" | "B" | "C" | "D" | "E" | "F";
export const ASSET_GROUP_IDS: AssetGroupId[] = ["A", "B", "C", "D", "E", "F"];

export interface AssetGroup {
  name: string; // blank = unnamed, matches PV's blank-by-default group names
  minWeightPct: number;
  maxWeightPct: number;
}

export interface TimePeriod {
  startDate: string; // ISO date -- more granular than PV's Start Year
  // dropdown, since the SEC NAV cache is already month-level; kept as
  // dates (matching the sibling backtester's own date fields) rather than
  // reproducing PV's year-only granularity.
  endDate: string;
}

export interface OptimizeRequest {
  funds: SecFund[]; // the Step 1 shortlist
  // Per-fund weight bounds set directly in the Step 1 asset table --
  // confirmed live against PortfolioVisualizer's optimize-portfolio tool
  // (Min./Max. Weight columns live there, not in a separate constraints
  // step). Falls back to constraints.minWeightPct/maxWeightPct for any
  // fund without an entry here.
  fundBounds: Record<string, FundBound>;
  // Per-fund group assignment (Step 1), only meaningful when
  // constraints.groupConstraintsEnabled is true. "None" = ungrouped.
  fundGroups: Record<string, AssetGroupId | "None">;
  assetGroups: Record<AssetGroupId, AssetGroup>;
  timePeriod: TimePeriod;
  goal: ObjectiveGoal;
  riskMeasure: RiskMeasure;
  targetAnnualVolatilityPct: number | null; // only used with max_return_target_vol
  robustOptimization: boolean; // PV's literal Monte Carlo resampling toggle -- the "robustness indicator"
  useHistoricalReturns: boolean;
  useHistoricalVolatility: boolean;
  useHistoricalCorrelations: boolean;
  // Only read when useHistoricalReturns is false -- confirmed live: PV
  // reveals an "Expected Return" column per asset in that case.
  expectedReturnOverrides: Record<string, number>;
  returnMethod: ReturnEstimationMethod;
  covarianceMethod: CovarianceMethod;
  blackLitterman: BlackLittermanInputs | null; // present only when goal === "black_litterman"
  constraints: OptimizeConstraints;
}

export interface FrontierPoint {
  volatilityPct: number;
  expectedReturnPct: number;
  sharpe: number;
  weights: Record<string, number>; // proj_id -> weight pct
}

export interface AssetSummaryRow {
  projId: string;
  displayName: string;
  expectedReturnPct: number;
  volatilityPct: number;
  sharpe: number;
  minWeightPct: number;
  maxWeightPct: number;
}

export interface PerformanceSummaryColumn {
  label: string; // "Optimized" or the compare-against label
  cagrPct: number;
  expectedReturnPct: number;
  stdDevPct: number;
  bestYearPct: number;
  worstYearPct: number;
  maxDrawdownPct: number;
  sharpeExAnte: number;
  sharpeExPost: number;
  sortino: number;
}

export interface RollingFold {
  periodLabel: string;
  realizedReturnPct: number;
  realizedVolatilityPct: number;
  realizedSharpe: number;
}

export type FeasibilityStatus = "ok" | "non_convergence" | "infeasible_constraints" | "insufficient_data";

export interface SelectedRiskMeasureResult {
  measure: RiskMeasure;
  label: string;
  optimizedValue: number;
  comparedValue: number | null;
  unit: "pct" | "ratio"; // most risk measures here are %, a couple (e.g. some tail ratios) could differ later
}

export interface OptimizeResult {
  feasibility: FeasibilityStatus;
  feasibilityMessage: string | null;
  robustNote: string | null; // set when request.robustOptimization is true
  optimalWeights: Record<string, number>; // proj_id -> weight pct
  compareWeights: Record<string, number> | null; // proj_id -> weight pct, per constraints.compareAgainst
  riskContributionPct: Record<string, number>; // proj_id -> % of total portfolio risk
  frontier: FrontierPoint[];
  assetSummary: AssetSummaryRow[];
  correlations: { projId1: string; projId2: string; correlation: number }[];
  performanceSummary: PerformanceSummaryColumn[]; // [optimized, compared] when a comparison is set
  rolling: RollingFold[];
  blackLitterman: { equilibriumReturnPct: Record<string, number>; adjustedReturnPct: Record<string, number> } | null;
  // Monthly return series for the optimized portfolio, for a return
  // distribution histogram -- riskfolio-lib's own jupyter_report() ships a
  // returns histogram alongside weights/risk-contribution charts.
  monthlyReturnsPct: number[];
  // The actual risk measure the user picked in Assumptions (Std Dev, CVaR,
  // CDaR, Semi-Variance), computed for this result -- previously the
  // Performance tab always showed generic Std Dev/Max Drawdown regardless
  // of which risk measure was selected.
  selectedRiskMeasure: SelectedRiskMeasureResult;
  generatedAt: string; // ISO timestamp, for the Report tab's run metadata line
}
