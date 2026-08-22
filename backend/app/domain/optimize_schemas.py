import re
from datetime import date
from enum import StrEnum
from math import isfinite

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

    @model_validator(mode="after")
    def validate_order(self):
        if not isfinite(self.min_weight_pct) or not isfinite(self.max_weight_pct):
            raise ValueError("fund bounds must be finite numbers")
        if self.min_weight_pct > self.max_weight_pct:
            raise ValueError("fund bound minWeightPct cannot exceed maxWeightPct")
        return self


class AssetGroup(CamelModel):
    name: str = ""
    min_weight_pct: float = Field(default=0, ge=0, le=100)
    max_weight_pct: float = Field(default=100, ge=0, le=100)

    @model_validator(mode="after")
    def validate_order(self):
        if not isfinite(self.min_weight_pct) or not isfinite(self.max_weight_pct):
            raise ValueError("asset group bounds must be finite numbers")
        if self.min_weight_pct > self.max_weight_pct:
            raise ValueError("asset group minWeightPct cannot exceed maxWeightPct")
        return self


class TimePeriod(CamelModel):
    start_date: str
    end_date: str

    @model_validator(mode="after")
    def validate_dates(self):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.start_date) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.end_date):
            raise ValueError("timePeriod dates must use ISO YYYY-MM-DD format")
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
        except ValueError as exc:
            raise ValueError("timePeriod dates must use ISO YYYY-MM-DD format") from exc
        if start > end:
            raise ValueError("timePeriod startDate cannot be after endDate")
        return self


class BlackLittermanView(CamelModel):
    key: str
    asset_proj_id_1: str
    view_type: ViewType
    asset_proj_id_2: str | None = None
    adjusted_performance_pct: float
    confidence: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_numbers(self):
        if not isfinite(self.adjusted_performance_pct):
            raise ValueError("Black-Litterman view performance must be finite")
        return self


class BlackLittermanInputs(CamelModel):
    risk_aversion: float = Field(gt=0)
    tau: float = Field(gt=0, le=1)
    benchmark_expected_return_pct: float
    views: list[BlackLittermanView] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_numbers(self):
        if not isfinite(self.risk_aversion) or not isfinite(self.tau) or not isfinite(self.benchmark_expected_return_pct):
            raise ValueError("Black-Litterman inputs must be finite numbers")
        return self


class OptimizeConstraints(CamelModel):
    long_only: bool
    min_weight_pct: float = Field(ge=-100, le=100)
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

    @model_validator(mode="after")
    def validate_order(self):
        numeric_fields = (
            self.min_weight_pct,
            self.max_weight_pct,
            self.risk_free_rate_pct,
            self.max_turnover_pct,
            self.max_tracking_error_pct,
        )
        if any(value is not None and not isfinite(value) for value in numeric_fields):
            raise ValueError("optimization constraints must be finite numbers")
        if self.min_weight_pct > self.max_weight_pct:
            raise ValueError("default minWeightPct cannot exceed maxWeightPct")
        if self.long_only and self.min_weight_pct < 0:
            raise ValueError("long-only constraints cannot have a negative minimum weight")
        if self.lookback_period_months < 1:
            raise ValueError("lookbackPeriodMonths must be positive")
        return self


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
        proj_id_set = set(proj_ids)
        duplicates = sorted({p for p in proj_ids if proj_ids.count(p) > 1})
        if duplicates:
            raise ValueError(f"duplicate fund proj_id values are not allowed: {duplicates}")
        if self.goal == ObjectiveGoal.black_litterman and self.black_litterman is None:
            raise ValueError("blackLitterman inputs are required when goal is black_litterman")
        if self.goal == ObjectiveGoal.black_litterman and self.return_method != ReturnEstimationMethod.black_litterman_posterior:
            raise ValueError("black_litterman goal requires returnMethod=black_litterman_posterior")
        if self.goal != ObjectiveGoal.black_litterman and self.return_method == ReturnEstimationMethod.black_litterman_posterior:
            raise ValueError("returnMethod=black_litterman_posterior requires goal=black_litterman")
        if self.benchmark_proj_id is None and self.constraints.max_tracking_error_pct is not None:
            raise ValueError("maxTrackingErrorPct requires benchmarkProjId")
        if self.benchmark_proj_id is not None and self.benchmark_proj_id not in proj_id_set:
            raise ValueError("benchmarkProjId must reference a selected fund")
        if self.constraints.long_only:
            negative_current = [proj_id for proj_id, weight in self.current_weight_pct.items() if weight < 0]
            negative_bounds = [
                proj_id for proj_id, bound in self.fund_bounds.items() if bound.min_weight_pct < 0
            ]
            if negative_current or negative_bounds:
                raise ValueError("long-only constraints cannot contain negative current weights or fund bounds")

        for field_name, values in (
            ("currentWeightPct", self.current_weight_pct),
            ("expectedReturnOverrides", self.expected_return_overrides),
            ("volatilityOverrides", self.volatility_overrides),
        ):
            if any(not isfinite(value) for value in values.values()):
                raise ValueError(f"{field_name} values must be finite numbers")

        scalar_values = (
            ("tailConfidence", self.tail_confidence),
            ("targetAnnualVolatilityPct", self.target_annual_volatility_pct),
            ("targetAnnualReturnPct", self.target_annual_return_pct),
        )
        if any(value is not None and not isfinite(value) for _, value in scalar_values):
            raise ValueError("optimization scalar inputs must be finite numbers")

        for key, correlation in self.correlation_overrides.items():
            parts = key.split("|")
            if len(parts) != 2 or not all(parts) or parts[0] == parts[1]:
                raise ValueError("correlationOverrides keys must be distinct proj_id pairs separated by '|'")
            if parts[0] not in proj_id_set or parts[1] not in proj_id_set:
                raise ValueError("correlationOverrides may reference selected funds only")
            if not isfinite(correlation) or not -1 <= correlation <= 1:
                raise ValueError("correlationOverrides values must be finite and between -1 and 1")

        if self.black_litterman is not None:
            for view in self.black_litterman.views:
                if view.asset_proj_id_1 not in proj_id_set:
                    raise ValueError("Black-Litterman views may reference selected funds only")
                if view.view_type == ViewType.relative:
                    if view.asset_proj_id_2 is None or view.asset_proj_id_2 not in proj_id_set:
                        raise ValueError("relative Black-Litterman views require a selected second asset")
                    if view.asset_proj_id_1 == view.asset_proj_id_2:
                        raise ValueError("relative Black-Litterman views require two distinct assets")
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
    robust_optimization_note: str | None
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
    # Kept beside the legacy monthly_returns_pct field so clients can label
    # daily/weekly optimization results honestly without breaking persisted
    # result payloads created before this field existed.
    return_frequency: DataFrequency = DataFrequency.monthly
    selected_risk_measure: SelectedRiskMeasureResult
    benchmark_comparison: BenchmarkComparison | None
    trade_list: list[TradeRow]
    total_turnover_pct: float
    binding_constraints: list[BindingConstraint]
    optimal_point: FrontierMarker
    gmv_point: FrontierMarker | None
    tangency_point: FrontierMarker | None
    generated_at: str
