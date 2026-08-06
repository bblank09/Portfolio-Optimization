from typing import Any, cast

import numpy as np
import pandas as pd

from backend.app.domain.enums import AlignmentFrequency, CashflowTiming
from backend.app.domain.schemas import BacktestRequest
from backend.app.engine.cashflows import cashflow_due, signed_cashflow_amount
from backend.app.engine.metrics import (
    annualized_return,
    annualized_volatility,
    beta_alpha,
    calmar_ratio,
    correlation,
    drawdown_series,
    historical_var,
    information_ratio,
    max_drawdown,
    rolling_correlation,
    sharpe_ratio,
    sortino_ratio,
    tracking_error,
)
from backend.app.engine.rebalancing import rebalance_due, rebalance_values
from backend.app.engine.returns import (
    money_weighted_return,
    simple_returns,
    time_weighted_return,
    wealth_index,
)

PERIODS_PER_YEAR = 12
DAILY_PERIODS_PER_YEAR = 252


def run_backtest(request: BacktestRequest, nav: pd.DataFrame) -> dict[str, Any]:
    asset_ids = [asset.proj_id for asset in request.assets]
    required_columns = set(asset_ids + [request.benchmark_proj_id])
    missing = sorted(required_columns - set(nav.columns))
    if missing:
        raise ValueError(f"NAV panel is missing required proj_id columns: {missing}")

    panel = nav.loc[pd.Timestamp(request.start_date) : pd.Timestamp(request.end_date), list(required_columns)].sort_index()
    if panel.empty:
        raise ValueError("Backtest requires at least two complete NAV observations for selected assets.")

    # The benchmark is validated alongside the holdings: pct_change returns NaN
    # across a gap, so dropping those periods would splice the benchmark curve
    # back together and understate its growth, corrupting excess return, beta,
    # alpha, tracking error and the information ratio.
    selected_panel = panel[sorted(required_columns)]
    daily = request.data.frequency == AlignmentFrequency.daily
    periods_per_year = DAILY_PERIODS_PER_YEAR if daily else PERIODS_PER_YEAR
    if daily:
        # Weekends are not missing data -- only a gap on an actual business
        # day (a real closure or a hole in the cache) is incomplete.
        expected_index = pd.bdate_range(panel.index.min(), panel.index.max())
        observed_index = pd.DatetimeIndex(panel.index).normalize()
        incomplete_periods = {str(day.date()) for day in expected_index.difference(observed_index)}
        incomplete_periods.update(
            str(pd.Timestamp(index).date())
            for index in selected_panel.index[selected_panel.isna().any(axis=1)]
        )
    else:
        observed_periods = pd.PeriodIndex(panel.index, freq="M")
        expected_periods = pd.period_range(observed_periods.min(), observed_periods.max(), freq="M")
        incomplete_periods = {str(period) for period in expected_periods.difference(observed_periods.unique())}
        incomplete_periods.update(
            str(pd.Timestamp(index).to_period("M"))
            for index in selected_panel.index[selected_panel.isna().any(axis=1)]
        )
    if incomplete_periods:
        periods = ", ".join(sorted(incomplete_periods))
        raise ValueError(f"Backtest cannot calculate with incomplete NAV periods for the selected funds or benchmark: {periods}.")

    if len(panel) < 2:
        raise ValueError("Backtest requires at least two complete NAV observations for selected assets.")

    returns = cast(pd.DataFrame, simple_returns(panel[asset_ids]))
    benchmark_return_frame = cast(pd.DataFrame, simple_returns(panel[[request.benchmark_proj_id]]))
    benchmark_returns = benchmark_return_frame.iloc[:, 0]
    target_weights = pd.Series({asset.proj_id: asset.weight / 100 for asset in request.assets}, dtype=float)
    values = target_weights * request.initial_capital

    cost_rate = (request.costs.transaction_bps + request.costs.slippage_bps) / 10000
    annual_drag_period = request.costs.annual_drag_pct / 100 / periods_per_year
    portfolio_rows = [{"date": panel.index[0], "value": float(values.sum())}]
    cashflow_rows = []
    rebalance_rows = []
    previous_date = panel.index[0]
    total_contributed = request.initial_capital
    total_withdrawn = 0.0
    total_costs = 0.0
    performance_returns = []

    for position, current_date in enumerate(panel.index[1:], start=1):
        starting_value = float(values.sum())
        cashflow = signed_cashflow_amount(request) if cashflow_due(position, request) else 0.0

        if cashflow and request.cashflow.timing == CashflowTiming.beginning:
            applied_cashflow = apply_cashflow(values, target_weights, cashflow)
            cashflow = applied_cashflow
            if applied_cashflow > 0:
                total_contributed += applied_cashflow
            else:
                total_withdrawn += abs(applied_cashflow)
            cashflow_rows.append({"date": current_date, "amount": applied_cashflow, "position": position})

        period_returns = returns.loc[current_date]
        values = values * (1 + period_returns)
        if annual_drag_period:
            drag_cost = float(values.sum() * annual_drag_period)
            values = values * (1 - annual_drag_period)
            total_costs += drag_cost

        if cashflow and request.cashflow.timing == CashflowTiming.end:
            applied_cashflow = apply_cashflow(values, target_weights, cashflow)
            cashflow = applied_cashflow
            if applied_cashflow > 0:
                total_contributed += applied_cashflow
            else:
                total_withdrawn += abs(applied_cashflow)
            cashflow_rows.append({"date": current_date, "amount": applied_cashflow, "position": position})

        if rebalance_due(
            current_date,
            previous_date,
            request.rebalancing.mode,
            values=values,
            target_weights=target_weights,
            threshold_pct=request.rebalancing.threshold_pct,
        ):
            before = values.copy()
            values, turnover, money_turnover = rebalance_values(values, target_weights)
            cost = money_turnover * cost_rate
            if cost:
                values = values - values / values.sum() * cost
                total_costs += cost
            rebalance_rows.append(
                {
                    "date": current_date,
                    "turnover": turnover,
                    "cost": cost,
                    "before": before.to_dict(),
                    "after": values.to_dict(),
                }
            )

        ending_value = float(values.sum())
        # Remove external flows from the period return while retaining market and trading costs.
        if request.cashflow.timing == CashflowTiming.beginning:
            denominator = starting_value + cashflow
            period_performance = 0.0 if denominator == 0 else ending_value / denominator - 1
        else:
            period_performance = 0.0 if starting_value == 0 else (ending_value - cashflow) / starting_value - 1
        performance_returns.append({"date": current_date, "return": period_performance})

        portfolio_rows.append({"date": current_date, "value": float(values.sum())})
        previous_date = current_date

    portfolio_value = pd.Series(
        [row["value"] for row in portfolio_rows],
        index=pd.to_datetime([row["date"] for row in portfolio_rows]),
        name="portfolio",
    )
    portfolio_returns = pd.Series(
        [row["return"] for row in performance_returns],
        index=pd.to_datetime([row["date"] for row in performance_returns]),
        name="portfolio",
    )
    aligned_benchmark = benchmark_returns.reindex(portfolio_returns.index).dropna()
    aligned_portfolio = portfolio_returns.reindex(aligned_benchmark.index).dropna()
    benchmark_curve = pd.concat(
        [
            pd.Series([request.initial_capital], index=[panel.index[0]], name="benchmark"),
            wealth_index(benchmark_returns, request.initial_capital),
        ]
    )
    risk_free_rate = request.risk_free_rate_pct / 100
    beta, alpha = beta_alpha(aligned_portfolio, aligned_benchmark, risk_free_rate, periods_per_year)
    sharpe = sharpe_ratio(portfolio_returns, risk_free_rate, periods_per_year)
    info_ratio = information_ratio(aligned_portfolio, aligned_benchmark, periods_per_year)

    ending_value = float(portfolio_value.iloc[-1])
    irr = money_weighted_return(
        irr_cashflows(request.initial_capital, cashflow_rows, periods_per_year, len(panel) - 1, ending_value)
    )
    summary = {
        "ending_value": ending_value,
        "irr": irr,
        "twrr": time_weighted_return(portfolio_returns),
        "twrr_cagr": annualized_return(portfolio_returns, periods_per_year),
        "volatility": annualized_volatility(portfolio_returns, periods_per_year),
        "sharpe": sharpe,
        # Sortino penalises only downside dispersion; Calmar scales return by the
        # worst peak-to-trough loss. Both are reported next to Sharpe because a
        # single dispersion measure hides skew and tail depth.
        "sortino": sortino_ratio(portfolio_returns, risk_free_rate, periods_per_year),
        "calmar": calmar_ratio(portfolio_returns, portfolio_value, periods_per_year),
        "var_95": historical_var(portfolio_returns, confidence=0.95),
        "var_99": historical_var(portfolio_returns, confidence=0.99),
        "max_drawdown": max_drawdown(portfolio_value),
        "benchmark_excess_return": time_weighted_return(aligned_portfolio) - time_weighted_return(aligned_benchmark),
        "cashflow_count": len(cashflow_rows),
        "rebalance_count": len(rebalance_rows),
        "total_contributed": total_contributed,
        "total_withdrawn": total_withdrawn,
        "total_costs": total_costs,
    }
    risk_rows = [
        {"metric": "beta", "value": beta},
        {"metric": "alpha", "value": alpha},
        {"metric": "tracking_error", "value": tracking_error(aligned_portfolio, aligned_benchmark, periods_per_year)},
        {"metric": "information_ratio", "value": info_ratio},
        {"metric": "correlation", "value": correlation(aligned_portfolio, aligned_benchmark)},
    ]
    return {
        "data_source": "sec_open_data",
        "summary": summary,
        "equity_curve": series_points(portfolio_value),
        "benchmark_curve": series_points(benchmark_curve),
        "drawdown_curve": series_points(drawdown_series(portfolio_value)),
        "monthly_returns": {
            "title": "Monthly Returns",
            "rows": [
                    {"date": pd.Timestamp(cast(Any, idx)).date().isoformat(), "return": float(value)}
                    for idx, value in portfolio_returns.items()
                ],
        },
        "annual_returns": annual_return_table(portfolio_returns),
        "risk_metrics": {"title": "Benchmark Risk", "rows": risk_rows},
        "diversification": diversification_table(returns[asset_ids]),
        "rolling_correlation": [
            {"date": pd.Timestamp(row["date"]).date().isoformat(), "asset_a": row["asset_a"], "asset_b": row["asset_b"], "correlation": row["correlation"]}
            for row in rolling_correlation(returns[asset_ids], window=periods_per_year)
        ],
        "asset_metrics": asset_metrics_table(request, returns, values, periods_per_year),
        "cashflows": [{"date": pd.Timestamp(row["date"]).date().isoformat(), "amount": row["amount"]} for row in cashflow_rows],
        "rebalances": [
            {"date": pd.Timestamp(row["date"]).date().isoformat(), "turnover": row["turnover"], "cost": row["cost"]}
            for row in rebalance_rows
        ],
        "quality_issues": [],
    }


def irr_cashflows(
    initial_capital: float,
    cashflow_rows: list[dict[str, Any]],
    periods_per_year: int,
    final_position: int,
    ending_value: float,
) -> list[tuple[float, float]]:
    """Build the investor-perspective cashflow series money_weighted_return expects.

    Time is nominal elapsed years (period position / periods_per_year), the same
    convention every other annualized figure in this engine uses -- not actual
    calendar days. NAV dates land on real month-end/business-day calendars, so
    "3 months" is not exactly 91.31 days; using calendar time would make IRR
    diverge from TWRR CAGR even with zero intermediate cashflows, when the two
    should agree exactly in that case. cashflow_rows carries the portfolio's
    sign (positive = contribution in, negative = withdrawal out); IRR needs the
    investor's sign, which is the opposite -- money the investor puts in is an
    outflow from their pocket, money they take out is an inflow.
    """
    events = [(0.0, -float(initial_capital))]
    events.extend((row["position"] / periods_per_year, -float(row["amount"])) for row in cashflow_rows)
    events.append((final_position / periods_per_year, float(ending_value)))
    return events


def apply_cashflow(values: pd.Series, target_weights: pd.Series, cashflow: float) -> float:
    if cashflow > 0:
        values += target_weights * cashflow
        return cashflow

    current_value = float(values.sum())
    withdrawal = min(abs(cashflow), current_value)
    if withdrawal and current_value:
        values -= values / current_value * withdrawal
    return -withdrawal


def series_points(series: pd.Series) -> list[dict[str, float | str]]:
    return [{"date": pd.Timestamp(cast(Any, index)).date().isoformat(), "value": float(value)} for index, value in series.dropna().items()]


def annual_return_table(returns: pd.Series) -> dict[str, Any]:
    yearly_values: dict[int, list[float]] = {}
    for index, value in returns.dropna().items():
        year = pd.Timestamp(cast(Any, index)).year
        yearly_values.setdefault(year, []).append(float(value))
    rows = [
        {"year": year, "return": float(np.prod([1.0 + period_return for period_return in values]) - 1.0)}
        for year, values in sorted(yearly_values.items())
    ]
    return {"title": "Annual Returns", "rows": rows}


def asset_metrics_table(request: BacktestRequest, returns: pd.DataFrame, final_values: pd.Series, periods_per_year: int = PERIODS_PER_YEAR) -> dict[str, Any]:
    ending_total = float(final_values.sum())
    rows = []
    for asset in request.assets:
        asset_returns = returns[asset.proj_id]
        final_value = float(final_values[asset.proj_id])
        final_weight_pct = (final_value / ending_total * 100) if ending_total else 0.0
        rows.append(
            {
                "proj_id": asset.proj_id,
                "fund": asset.display_name,
                "target_weight_pct": asset.weight,
                "final_weight_pct": final_weight_pct,
                "drift_pct": final_weight_pct - asset.weight,
                "cagr": annualized_return(asset_returns, periods_per_year),
                "volatility": annualized_volatility(asset_returns, periods_per_year),
            }
        )
    return {"title": "Asset Risk and Allocation", "rows": rows}


def diversification_table(asset_returns: pd.DataFrame) -> dict[str, Any]:
    corr = asset_returns.corr()
    rows = []
    for left in corr.index:
        for right in corr.columns:
            if left < right:
                pair = float(corr.loc[left, right])
                # Undefined against a zero-variance asset; report null, not NaN.
                rows.append(
                    {
                        "asset_a": left,
                        "asset_b": right,
                        "correlation": pair if np.isfinite(pair) else None,
                    }
                )
    return {"title": "Diversification Check", "rows": rows}
