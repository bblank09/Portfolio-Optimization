from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for every optimizer schema: JSON on the wire is camelCase
    (matching frontend/src/types/optimize.ts field-for-field, unchanged),
    Python attribute access stays idiomatic snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ObjectiveGoal(StrEnum):
    max_sharpe = "max_sharpe"
    min_volatility = "min_volatility"
    max_return_target_vol = "max_return_target_vol"
    min_variance = "min_variance"
    risk_parity = "risk_parity"
    black_litterman = "black_litterman"
    hrp = "hrp"


class RiskMeasure(StrEnum):
    std_dev = "std_dev"
    semi_variance = "semi_variance"
    cvar = "cvar"
    cdar = "cdar"


class ReturnEstimationMethod(StrEnum):
    historical_mean = "historical_mean"
    capm_implied = "capm_implied"
    black_litterman_posterior = "black_litterman_posterior"


class CovarianceMethod(StrEnum):
    sample = "sample"
    shrinkage = "shrinkage"
    ewma = "ewma"


class CompareAgainst(StrEnum):
    none = "none"
    equal_weighted = "equal_weighted"
    max_sharpe = "max_sharpe"
    inverse_volatility = "inverse_volatility"
    risk_parity = "risk_parity"
    current = "current"


class DataFrequency(StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class OptimizationFrequency(StrEnum):
    monthly = "monthly"
    quarterly = "quarterly"
    annually = "annually"


class RollingWindowMode(StrEnum):
    expanding = "expanding"
    trailing = "trailing"


class ViewType(StrEnum):
    absolute = "absolute"
    relative = "relative"


class OptimizeFund(CamelModel):
    proj_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


class FundBound(CamelModel):
    min_weight_pct: float = Field(ge=-100, le=100)
    max_weight_pct: float = Field(ge=0, le=100)


class AssetGroup(CamelModel):
    name: str = ""
    min_weight_pct: float = Field(default=0, ge=0, le=100)
    max_weight_pct: float = Field(default=100, ge=0, le=100)


class TimePeriod(CamelModel):
    start_date: str
    end_date: str


class BlackLittermanView(CamelModel):
    key: str
    asset_proj_id_1: str
    view_type: ViewType
    asset_proj_id_2: str | None = None
    adjusted_performance_pct: float
    confidence: int = Field(ge=0, le=100)


class BlackLittermanInputs(CamelModel):
    risk_aversion: float = Field(gt=0)
    tau: float = Field(gt=0, le=1)
    benchmark_expected_return_pct: float
    views: list[BlackLittermanView] = Field(default_factory=list)


class OptimizeConstraints(CamelModel):
    long_only: bool
    min_weight_pct: float
    max_weight_pct: float = Field(ge=0, le=100)
    group_constraints_enabled: bool
    max_holdings: int = Field(ge=1)
    lookback_period_months: int
    optimization_frequency: OptimizationFrequency
    rolling_window_mode: RollingWindowMode = RollingWindowMode.expanding
    risk_free_rate_pct: float
    compare_against: CompareAgainst
    max_turnover_pct: float | None = Field(default=None, ge=0)
    max_tracking_error_pct: float | None = Field(default=None, ge=0)


class OptimizeRequest(CamelModel):
    funds: list[OptimizeFund] = Field(min_length=2, max_length=30)
    fund_bounds: dict[str, FundBound] = Field(default_factory=dict)
    current_weight_pct: dict[str, float] = Field(default_factory=dict)
    fund_groups: dict[str, str] = Field(default_factory=dict)
    asset_groups: dict[str, AssetGroup]
    time_period: TimePeriod
    data_frequency: DataFrequency = DataFrequency.monthly
    goal: ObjectiveGoal
    risk_measure: RiskMeasure
    tail_confidence: float = Field(default=95, ge=50, le=99.9)
    target_annual_volatility_pct: float | None = None
    target_annual_return_pct: float | None = None
    robust_optimization: bool = False
    use_historical_returns: bool = True
    use_historical_volatility: bool = True
    use_historical_correlations: bool = True
    expected_return_overrides: dict[str, float] = Field(default_factory=dict)
    volatility_overrides: dict[str, float] = Field(default_factory=dict)
    correlation_overrides: dict[str, float] = Field(default_factory=dict)
    return_method: ReturnEstimationMethod = ReturnEstimationMethod.historical_mean
    covariance_method: CovarianceMethod = CovarianceMethod.sample
    black_litterman: BlackLittermanInputs | None = None
    benchmark_proj_id: str | None = None
    constraints: OptimizeConstraints

    @model_validator(mode="after")
    def validate_request(self):
        proj_ids = [fund.proj_id for fund in self.funds]
        duplicates = sorted({p for p in proj_ids if proj_ids.count(p) > 1})
        if duplicates:
            raise ValueError(f"duplicate fund proj_id values are not allowed: {duplicates}")
        if self.goal == ObjectiveGoal.black_litterman and self.black_litterman is None:
            raise ValueError("blackLitterman inputs are required when goal is black_litterman")
        return self


class TradeRow(CamelModel):
    proj_id: str
    display_name: str
    current_weight_pct: float
    optimal_weight_pct: float
    delta_pct: float
    action: str


class BindingConstraint(CamelModel):
    label: str
    detail: str


class FrontierPoint(CamelModel):
    volatility_pct: float
    expected_return_pct: float
    sharpe: float
    weights: dict[str, float]


class FrontierMarker(CamelModel):
    volatility_pct: float
    expected_return_pct: float
    label: str


class AssetSummaryRow(CamelModel):
    proj_id: str
    display_name: str
    expected_return_pct: float
    volatility_pct: float
    sharpe: float
    min_weight_pct: float
    max_weight_pct: float


class PerformanceSummaryColumn(CamelModel):
    """Realized-performance fields are ``float | None``: they are computed
    from the portfolio's actual periodic return series, and some of them are
    genuinely undefined for a given request (no complete calendar year in the
    window, a degenerate zero-downside series). Returning null there is the
    honest answer -- these five used to be fabricated from volatility
    (bestYear = ret + vol, sortino = sharpe, ...), which the design spec's
    "no synthetic numbers anywhere in the response" target state forbids."""

    label: str
    cagr_pct: float
    expected_return_pct: float
    std_dev_pct: float
    best_year_pct: float | None
    worst_year_pct: float | None
    max_drawdown_pct: float | None
    sharpe_ex_ante: float
    sharpe_ex_post: float | None
    sortino: float | None


class RollingFold(CamelModel):
    period_label: str
    realized_return_pct: float
    realized_volatility_pct: float
    realized_sharpe: float


class SelectedRiskMeasureResult(CamelModel):
    """``optimized_value`` is the realized value of ``measure`` itself for the
    solved weights (see optimizer/solvers.realized_risk) -- not, as it once
    was, portfolio standard deviation wearing the selected measure's label."""

    measure: RiskMeasure
    label: str
    optimized_value: float
    compared_value: float | None
    unit: str


class CorrelationPair(CamelModel):
    proj_id_1: str
    proj_id_2: str
    correlation: float


class BenchmarkComparison(CamelModel):
    proj_id: str
    display_name: str
    tracking_error_pct: float
    excess_return_pct: float


class BlackLittermanResult(CamelModel):
    equilibrium_return_pct: dict[str, float]
    adjusted_return_pct: dict[str, float]


class OptimizeResult(CamelModel):
    feasibility: str
    feasibility_message: str | None
    robust_note: str | None
    compare_note: str | None
    constraint_note: str | None
    optimal_weights: dict[str, float]
    compare_weights: dict[str, float] | None
    risk_contribution_pct: dict[str, float]
    frontier: list[FrontierPoint]
    asset_summary: list[AssetSummaryRow]
    correlations: list[CorrelationPair]
    performance_summary: list[PerformanceSummaryColumn]
    rolling: list[RollingFold]
    black_litterman: BlackLittermanResult | None
    monthly_returns_pct: list[float]
    selected_risk_measure: SelectedRiskMeasureResult
    benchmark_comparison: BenchmarkComparison | None
    trade_list: list[TradeRow]
    total_turnover_pct: float
    binding_constraints: list[BindingConstraint]
    optimal_point: FrontierMarker
    gmv_point: FrontierMarker | None
    tangency_point: FrontierMarker | None
    generated_at: str
