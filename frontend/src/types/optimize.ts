// Request/response types for the real POST /api/optimize endpoint. These
// mirror backend/app/domain/optimize_schemas.py by hand -- there is no
// codegen, so keep both sides in sync manually when either changes (the
// backend's CamelModel base serializes its snake_case fields as the
// camelCase names used here). The field set itself follows
// docs/mock-ui-spec.md, which is sourced against riskfolio-lib docs and a
// live walkthrough of PortfolioVisualizer's optimize-portfolio /
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

export type CompareAgainst = "none" | "equal_weighted" | "max_sharpe" | "inverse_volatility" | "risk_parity" | "current";

// riskfolio-lib exposes alpha as an explicit parameter for CVaR/CDaR --
// a tail-risk measure without a stated confidence level isn't well-defined.
export type TailConfidence = 95 | 97.5 | 99;

export type DataFrequency = "daily" | "weekly" | "monthly";

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
  // Caps one-way turnover vs. the Step 1 "current" weights on every
  // rebalance -- without this a rolling optimizer that re-solves every
  // period will systematically overstate net-of-cost performance.
  // null = unconstrained.
  maxTurnoverPct: number | null;
  // Only meaningful when a benchmark is set (see OptimizeRequest.benchmarkProjId)
  // -- caps how far the optimized weights can drift from the benchmark's
  // own risk, distinct from targeting the benchmark's return. null = unconstrained.
  maxTrackingErrorPct: number | null;
  // "expanding" (default): each rolling-validation fold's training window
  // always starts at the earliest available observation and grows.
  // "trailing": each fold's training window is a fixed-length window of
  // lookbackPeriodMonths immediately preceding that fold's test period,
  // sliding forward each fold. Backend: rolling.build_fold_schedule.
  rollingWindowMode: "expanding" | "trailing";
}

export interface FundBound {
  // Can go negative only when constraints.longOnly is false -- a negative
  // minWeightPct represents a permitted short position for that fund.
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
  // The Step 1 "current" weight per fund (weightsOptional, so this can be
  // all-zero) -- the only source for the trade list's currentWeightPct and
  // the "current" CompareAgainst option.
  currentWeightPct: Record<string, number>;
  // Per-fund group assignment (Step 1), only meaningful when
  // constraints.groupConstraintsEnabled is true. "None" = ungrouped.
  fundGroups: Record<string, AssetGroupId | "None">;
  assetGroups: Record<AssetGroupId, AssetGroup>;
  timePeriod: TimePeriod;
  dataFrequency: DataFrequency;
  goal: ObjectiveGoal;
  riskMeasure: RiskMeasure;
  // Only meaningful when riskMeasure is cvar or cdar -- an unstated
  // confidence level makes a tail-risk measure undefined.
  tailConfidence: TailConfidence;
  targetAnnualVolatilityPct: number | null; // only used with max_return_target_vol
  // Only used with min_volatility -- pins that objective to a target return
  // instead of collapsing to the same unconstrained minimum as min_variance.
  targetAnnualReturnPct: number | null;
  robustOptimization: boolean; // PV's literal Monte Carlo resampling toggle -- the "robustness indicator"
  useHistoricalReturns: boolean;
  useHistoricalVolatility: boolean;
  useHistoricalCorrelations: boolean;
  // Only read when useHistoricalReturns is false -- reveals an "Expected
  // Return" column per asset in that case.
  expectedReturnOverrides: Record<string, number>;
  // Only read when useHistoricalVolatility is false -- reveals an
  // "Expected Volatility" column per asset.
  volatilityOverrides: Record<string, number>;
  // Only read when useHistoricalCorrelations is false -- reveals an
  // editable pairwise correlation matrix. Keyed "projIdA|projIdB" with
  // projIdA < projIdB (sorted) so lookups don't need to try both orders.
  correlationOverrides: Record<string, number>;
  returnMethod: ReturnEstimationMethod;
  covarianceMethod: CovarianceMethod;
  blackLitterman: BlackLittermanInputs | null; // present only when goal === "black_litterman"
  // A single fixed comparator (distinct from constraints.compareAgainst,
  // which is a computed weighting scheme) -- e.g. tracking a specific fund.
  // null = no benchmark set.
  benchmarkProjId: string | null;
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
  // These five are realized-performance fields computed from the actual
  // periodic return series, and the backend returns null when one is
  // genuinely undefined for the request (no complete calendar year in the
  // window, a degenerate zero-downside series) rather than fabricating a
  // number -- render them as "N/A", never as 0.
  bestYearPct: number | null;
  worstYearPct: number | null;
  maxDrawdownPct: number | null;
  sharpeExAnte: number;
  sharpeExPost: number | null;
  sortino: number | null;
}

export interface RollingFold {
  periodLabel: string;
  realizedReturnPct: number;
  realizedVolatilityPct: number;
  realizedSharpe: number;
}

export type FeasibilityStatus = "ok" | "non_convergence" | "infeasible_constraints" | "insufficient_data";

// The single most actionable output for a real user: "what do I actually
// do" -- current holdings (from Step 1's own weight column) vs. the
// optimized target, and the resulting one-way turnover.
export interface TradeRow {
  projId: string;
  displayName: string;
  currentWeightPct: number;
  optimalWeightPct: number;
  deltaPct: number; // optimalWeightPct - currentWeightPct
  action: "buy" | "sell" | "hold";
}

// Which constraint(s) are actually pinning the solution -- distinct from
// merely listing the constraints set in Assumptions, this says which ones
// are load-bearing for this particular result.
export interface BindingConstraint {
  label: string;
  detail: string;
}

export interface FrontierMarker {
  volatilityPct: number;
  expectedReturnPct: number;
  label: string;
}

export interface SelectedRiskMeasureResult {
  measure: RiskMeasure;
  label: string;
  optimizedValue: number;
  comparedValue: number | null;
  unit: "pct" | "ratio"; // most risk measures here are %, a couple (e.g. some tail ratios) could differ later
}

export interface OptimizeResult {
  runId: string;
  createdAt: string;
  dataSource: "sec_open_data";
  feasibility: FeasibilityStatus;
  feasibilityMessage: string | null;
  // Rolling out-of-sample validation caveats (e.g. folds dropped for
  // insufficient training history) -- NOT related to robustOptimization
  // (see robustOptimizationNote below for that).
  robustNote: string | null;
  // Set when constraints.compareAgainst produced a comparison portfolio --
  // caveats about how that comparison was computed.
  compareNote: string | null;
  // Set when a portfolio constraint (e.g. maxHoldings) could only be
  // approximately honored -- explains what was trimmed and why.
  constraintNote: string | null;
  // Set when request.robustOptimization is true -- states how many Monte
  // Carlo resamples succeeded, or explains a fallback to the single-shot
  // solve when fewer than half succeeded.
  robustOptimizationNote: string | null;
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
  // Frequency of monthlyReturnsPct. The legacy field name is retained for
  // persisted-run compatibility, but the UI must not label daily/weekly
  // observations as monthly.
  returnFrequency?: DataFrequency;
  // The actual risk measure the user picked in Assumptions (Std Dev, CVaR,
  // CDaR, Semi-Variance), computed for this result -- previously the
  // Performance tab always showed generic Std Dev/Max Drawdown regardless
  // of which risk measure was selected.
  selectedRiskMeasure: SelectedRiskMeasureResult;
  // Set only when request.benchmarkProjId is a fund in the shortlist.
  benchmarkComparison: { projId: string; displayName: string; trackingErrorPct: number; excessReturnPct: number } | null;
  // Current (Step 1) weights vs. optimal, and the resulting turnover --
  // empty when no fund in the shortlist has a nonzero Step 1 weight.
  tradeList: TradeRow[];
  totalTurnoverPct: number;
  bindingConstraints: BindingConstraint[];
  // Marks on the efficient frontier chart: this run's own optimal point,
  // the global-minimum-variance point, and the max-Sharpe (tangency) point.
  optimalPoint: FrontierMarker;
  gmvPoint: FrontierMarker | null;
  tangencyPoint: FrontierMarker | null;
  generatedAt: string; // ISO timestamp, for the Report tab's run metadata line
}

// Persisted runs keep the complete optimizer configuration, but only need
// the fund identity fields to hydrate the current SEC fund catalog on load.
// The live catalog supplies the remaining metadata used by the UI. These
// fields use the optimizer API's camelCase aliases, unlike the live SEC fund
// catalog's snake_case fields.
export interface SavedOptimizeFund {
  projId: string;
  displayName: string;
}

export type SavedOptimizeRequest = Omit<OptimizeRequest, "funds"> & {
  funds: SavedOptimizeFund[];
};

export interface OptimizeRunResult extends OptimizeResult {
  request: SavedOptimizeRequest;
}
