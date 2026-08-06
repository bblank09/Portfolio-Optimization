from datetime import date
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .enums import (
    AlignmentFrequency,
    CashflowTiming,
    CashflowType,
    DataSource,
    Frequency,
    PriceField,
    RebalanceMode,
)


class SecFundAllocation(BaseModel):
    proj_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    weight: float = Field(ge=0, le=100)


class CashflowRule(BaseModel):
    enabled: bool
    type: CashflowType = CashflowType.contribution
    amount: float = Field(ge=0)
    frequency: Frequency = Frequency.monthly
    timing: CashflowTiming = CashflowTiming.end


class RebalanceRule(BaseModel):
    mode: RebalanceMode = RebalanceMode.annual
    threshold_pct: float = Field(default=5.0, gt=0)


class CostAssumptions(BaseModel):
    transaction_bps: float = Field(ge=0)
    slippage_bps: float = Field(ge=0)
    annual_drag_pct: float = Field(ge=0)


class DataAssumptions(BaseModel):
    source: DataSource = DataSource.sec_open_data
    price_field: PriceField = PriceField.nav_per_unit
    frequency: AlignmentFrequency = AlignmentFrequency.monthly


class BacktestRequest(BaseModel):
    assets: list[SecFundAllocation] = Field(min_length=1, max_length=20)
    start_date: date
    end_date: date
    initial_capital: float = Field(gt=0)
    benchmark_proj_id: str = Field(min_length=1)
    risk_free_rate_pct: float = Field(default=0.0, ge=0)
    cashflow: CashflowRule
    rebalancing: RebalanceRule
    costs: CostAssumptions
    data: DataAssumptions

    @model_validator(mode="after")
    def validate_request(self):
        asset_ids = [asset.proj_id for asset in self.assets]
        duplicate_ids = sorted({proj_id for proj_id in asset_ids if asset_ids.count(proj_id) > 1})
        if duplicate_ids:
            raise ValueError(f"duplicate asset proj_id values are not allowed: {duplicate_ids}")

        total = sum(asset.weight for asset in self.assets)
        if abs(total - 100) > 0.01:
            raise ValueError(f"weights must sum to 100, got {total:.4f}")
        scale = 100 / total
        for asset in self.assets:
            asset.weight *= scale
        self.assets[-1].weight += 100 - sum(asset.weight for asset in self.assets)

        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.cashflow.enabled and self.cashflow.amount <= 0:
            raise ValueError("cashflow amount must be greater than zero when cashflow is enabled")
        return self


class MetricSummary(BaseModel):
    ending_value: float
    irr: float | None = None
    twrr_cagr: float
    volatility: float
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    var_95: float | None = None
    var_99: float | None = None
    max_drawdown: float
    benchmark_excess_return: float | None = None


class TimeSeriesPoint(BaseModel):
    date: date
    value: float


class TableSection(BaseModel):
    title: str
    rows: list[dict[str, Any]]


class QualityIssue(BaseModel):
    code: str
    message: str
    severity: str = "warning"


class BacktestResult(BaseModel):
    request: BacktestRequest
    summary: MetricSummary
    equity_curve: list[TimeSeriesPoint]
    benchmark_curve: list[TimeSeriesPoint]
    drawdown_curve: list[TimeSeriesPoint]
    monthly_returns: TableSection
    annual_returns: TableSection
    risk_metrics: TableSection
    diversification: TableSection
    asset_metrics: TableSection
    quality_issues: list[QualityIssue]
