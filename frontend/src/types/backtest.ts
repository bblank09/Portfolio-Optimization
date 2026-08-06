export type Frequency = "monthly" | "quarterly" | "annual";
export type CashflowType = "contribution" | "withdrawal";
export type CashflowTiming = "beginning" | "end";
export type RebalanceMode = "none" | "monthly" | "quarterly" | "annual" | "threshold";

export interface SecFundAllocation {
  proj_id: string;
  display_name: string;
  weight: number;
}

export interface DataStatus {
  nav_as_of: string;
  nav_start: string;
  fund_count: number;
}

export interface SecFund {
  proj_id: string;
  unique_id: string;
  fund_class_name: string;
  class_abbr_name: string;
  display_name: string;
  search_term: string;
  amc_name_th: string;
  amc_name_en: string;
  policy_desc: string;
  // Real per-fund NAV coverage (scripts/sec_annotate_universe_coverage.py).
  // nav_completeness < 1 means the fund reports NAV less often than
  // monthly somewhere in its history (e.g. quarterly after launch) --
  // distinct from just having a short nav_start..nav_end span.
  nav_start: string | null;
  nav_end: string | null;
  nav_months: number | null;
  nav_span_months: number | null;
  nav_completeness: number | null;
  nav_gap_count: number | null;
  nav_largest_gap_start: string | null;
  nav_largest_gap_end: string | null;
}

export interface CashflowRule {
  enabled: boolean;
  type: CashflowType;
  amount: number;
  frequency: Frequency;
  timing: CashflowTiming;
}

export interface RebalanceRule {
  mode: RebalanceMode;
  threshold_pct: number;
}

export interface CostAssumptions {
  transaction_bps: number;
  slippage_bps: number;
  annual_drag_pct: number;
}

export interface DataAssumptions {
  source: "sec_open_data";
  price_field: "nav_per_unit";
  frequency: "monthly" | "daily";
}

export interface BacktestRequest {
  assets: SecFundAllocation[];
  start_date: string;
  end_date: string;
  initial_capital: number;
  benchmark_proj_id: string;
  risk_free_rate_pct: number;
  cashflow: CashflowRule;
  rebalancing: RebalanceRule;
  costs: CostAssumptions;
  data: DataAssumptions;
}

export interface MetricSummary {
  ending_value: number;
  irr: number | null;
  twrr_cagr: number;
  volatility: number;
  sharpe: number | null;
  sortino: number | null;
  calmar: number | null;
  var_95: number | null;
  var_99: number | null;
  max_drawdown: number;
  benchmark_excess_return: number | null;
}

export interface TimeSeriesPoint {
  date: string;
  value: number;
}

export interface TableSection {
  title: string;
  rows: Record<string, unknown>[];
}

export interface QualityIssue {
  code: string;
  message: string;
  severity: "info" | "warning" | "error";
}

export interface BacktestResult {
  run_id: string;
  created_at: string;
  data_source: "sec_open_data";
  request: BacktestRequest;
  summary: MetricSummary & {
    twrr: number;
    cashflow_count: number;
    rebalance_count: number;
    total_contributed: number;
    total_withdrawn: number;
    total_costs: number;
  };
  equity_curve: TimeSeriesPoint[];
  benchmark_curve: TimeSeriesPoint[];
  drawdown_curve: TimeSeriesPoint[];
  cashflows: { date: string; amount: number }[];
  rebalances: { date: string; turnover: number; cost: number }[];
  monthly_returns: TableSection;
  annual_returns: TableSection;
  risk_metrics: TableSection;
  diversification: TableSection;
  rolling_correlation: { date: string; asset_a: string; asset_b: string; correlation: number | null }[];
  asset_metrics: TableSection;
  quality_issues: QualityIssue[];
}
