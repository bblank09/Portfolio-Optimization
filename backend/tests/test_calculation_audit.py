"""End-to-end numerical audit of the backtest engine.

Every expected value in this module is derived by hand from the definition of the
metric, NOT by reading the implementation. A failure here means the engine
disagrees with the textbook formula.
"""

import math

import numpy as np
import pandas as pd
import pytest

from backend.app.domain.schemas import BacktestRequest
from backend.app.engine.backtest import run_backtest
from backend.app.engine.metrics import (
    annualized_return,
    annualized_volatility,
    beta_alpha,
    calmar_ratio,
    downside_deviation,
    historical_var,
    max_drawdown,
    rolling_correlation,
    sharpe_ratio,
    sortino_ratio,
    tracking_error,
)
from backend.app.engine.rebalancing import rebalance_due, rebalance_values
from backend.app.engine.returns import time_weighted_return

MONTHS = 12


def make_request(
    *,
    assets=None,
    start_date="2020-01-31",
    end_date="2020-04-30",
    initial_capital=1000.0,
    benchmark="FUND_A",
    rebalancing="none",
    cashflow=None,
    costs=None,
    risk_free_rate_pct=0.0,
    frequency="monthly",
):
    return BacktestRequest(
        assets=assets or [{"proj_id": "FUND_A", "display_name": "Fund A", "weight": 100}],
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        benchmark_proj_id=benchmark,
        risk_free_rate_pct=risk_free_rate_pct,
        cashflow=cashflow
        or {"enabled": False, "type": "contribution", "amount": 0, "frequency": "monthly", "timing": "end"},
        rebalancing=rebalancing if isinstance(rebalancing, dict) else {"mode": rebalancing},
        costs=costs or {"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
        data={"source": "sec_open_data", "price_field": "nav_per_unit", "frequency": frequency},
    )


def nav_frame(data, dates):
    return pd.DataFrame(data, index=pd.to_datetime(dates))


# ---------------------------------------------------------------------------
# Pure metric functions
# ---------------------------------------------------------------------------


def test_annualized_return_is_geometric_cagr():
    # Three monthly periods of exactly +10%. Total growth 1.1**3 over 3/12 years.
    returns = pd.Series([0.10, 0.10, 0.10])
    expected = (1.10**3) ** (MONTHS / 3) - 1
    assert annualized_return(returns, MONTHS) == pytest.approx(expected)


def test_annualized_return_of_flat_series_is_zero():
    assert annualized_return(pd.Series([0.0, 0.0, 0.0]), MONTHS) == pytest.approx(0.0)


def test_annualized_volatility_uses_sample_standard_deviation():
    # Realised volatility estimated from a sample uses the sample (n-1) standard
    # deviation -- the Excel STDEV / pandas .std() default, and the convention
    # every other statistic in this engine (cov, var) already follows.
    returns = pd.Series([0.10, -0.10, 0.10, -0.10])
    sample_std = returns.std(ddof=1)
    assert annualized_volatility(returns, MONTHS) == pytest.approx(float(sample_std * math.sqrt(MONTHS)))


def test_tracking_error_uses_sample_standard_deviation():
    portfolio = pd.Series([0.05, 0.01, -0.02, 0.04])
    benchmark = pd.Series([0.03, 0.02, -0.01, 0.01])
    active = portfolio - benchmark
    expected = float(active.std(ddof=1) * math.sqrt(MONTHS))
    assert tracking_error(portfolio, benchmark, MONTHS) == pytest.approx(expected)


def test_volatility_and_beta_share_one_dof_convention():
    # beta divides cov(p, b) by var(b); if vol used a different ddof than
    # cov/var, Sharpe and beta would be computed on inconsistent statistics.
    benchmark = pd.Series([0.03, -0.02, 0.04, -0.01, 0.02])
    vol = annualized_volatility(benchmark, MONTHS)
    implied_variance = (vol / math.sqrt(MONTHS)) ** 2
    assert implied_variance == pytest.approx(float(benchmark.var(ddof=1)))


def test_max_drawdown_is_worst_peak_to_trough():
    values = pd.Series([1000.0, 1200.0, 900.0, 1000.0])
    # Peak 1200 -> trough 900 = -25%.
    assert max_drawdown(values) == pytest.approx(-0.25)


def test_max_drawdown_of_monotonic_series_is_zero():
    assert max_drawdown(pd.Series([100.0, 110.0, 120.0])) == pytest.approx(0.0)


def test_sharpe_ratio_is_excess_cagr_over_annualised_volatility():
    returns = pd.Series([0.02, -0.01, 0.03, 0.00, 0.01])
    rf = 0.02
    expected = (annualized_return(returns, MONTHS) - rf) / annualized_volatility(returns, MONTHS)
    assert sharpe_ratio(returns, rf, MONTHS) == pytest.approx(expected)


def test_sharpe_ratio_is_none_when_volatility_is_zero():
    assert sharpe_ratio(pd.Series([0.01, 0.01, 0.01]), 0.0, MONTHS) is None


def test_downside_deviation_only_penalises_returns_below_the_mar():
    returns = pd.Series([0.10, -0.10, 0.10, -0.10])
    # squared downside = (0, .01, 0, .01); mean over ALL n observations = .005
    expected = math.sqrt(0.005) * math.sqrt(MONTHS)
    assert downside_deviation(returns, MONTHS) == pytest.approx(expected)


def test_sortino_ratio_divides_excess_cagr_by_downside_deviation():
    returns = pd.Series([0.05, -0.02, 0.03, -0.01])
    rf = 0.01
    expected = (annualized_return(returns, MONTHS) - rf) / downside_deviation(returns, MONTHS)
    assert sortino_ratio(returns, rf, MONTHS) == pytest.approx(expected)


def test_historical_var_is_the_loss_at_the_given_confidence_percentile():
    # 10 observations; 95% VaR is the loss such that only 5% of observed
    # months were worse -- the (1 - confidence) percentile of the return
    # distribution, reported as a positive loss magnitude.
    returns = pd.Series([-0.10, -0.05, 0.00, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08])
    # numpy's linear-interpolation 5th percentile of this series is -0.0775.
    assert historical_var(returns, confidence=0.95) == pytest.approx(0.0775)


def test_historical_var_at_99_confidence_is_more_severe_than_at_95():
    returns = pd.Series([-0.10, -0.05, 0.00, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08])
    assert historical_var(returns, confidence=0.99) > historical_var(returns, confidence=0.95)


def test_historical_var_of_an_all_positive_series_is_zero_not_negative():
    # A "loss" that is actually a gain is not a risk figure; VaR floors at 0.
    returns = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
    assert historical_var(returns, confidence=0.95) == pytest.approx(0.0)


def test_historical_var_is_none_with_too_few_observations():
    assert historical_var(pd.Series([0.01, 0.02]), confidence=0.95) is None


def test_calmar_ratio_is_cagr_over_the_absolute_max_drawdown():
    returns = pd.Series([0.10, -0.20, 0.15, 0.05])
    values = pd.Series([1000.0, 1100.0, 880.0, 1012.0, 1062.6])
    expected = annualized_return(returns, MONTHS) / abs(max_drawdown(values))
    assert calmar_ratio(returns, values, MONTHS) == pytest.approx(expected)


def test_calmar_ratio_is_none_when_the_portfolio_never_drew_down():
    returns = pd.Series([0.10, 0.10, 0.10])
    values = pd.Series([1000.0, 1100.0, 1210.0, 1331.0])
    assert calmar_ratio(returns, values, MONTHS) is None


def test_sortino_ratio_is_none_when_nothing_fell_below_the_mar():
    returns = pd.Series([0.01, 0.02, 0.03])
    assert sortino_ratio(returns, 0.0, MONTHS) is None


def test_sortino_exceeds_sharpe_when_the_downside_is_milder_than_total_dispersion():
    # One big up month inflates total dispersion but not downside dispersion,
    # so penalising only the downside must give the higher ratio.
    returns = pd.Series([0.20, -0.01, 0.01, -0.01, 0.01, 0.01])
    sharpe = sharpe_ratio(returns, 0.0, MONTHS)
    sortino = sortino_ratio(returns, 0.0, MONTHS)
    assert sortino is not None and sharpe is not None
    assert sortino > sharpe


def test_beta_of_a_series_against_itself_is_one():
    series = pd.Series([0.03, -0.02, 0.04, -0.01, 0.02])
    beta, _ = beta_alpha(series, series, 0.0, MONTHS)
    assert beta == pytest.approx(1.0)


def test_alpha_of_a_series_against_itself_is_zero():
    series = pd.Series([0.03, -0.02, 0.04, -0.01, 0.02])
    _, alpha = beta_alpha(series, series, 0.02, MONTHS)
    assert alpha == pytest.approx(0.0, abs=1e-12)


def test_time_weighted_return_compounds_period_returns():
    returns = pd.Series([0.10, -0.05, 0.20])
    assert time_weighted_return(returns) == pytest.approx(1.10 * 0.95 * 1.20 - 1)


# ---------------------------------------------------------------------------
# Rebalancing arithmetic
# ---------------------------------------------------------------------------


def test_rebalance_turnover_is_one_sided_traded_fraction():
    # 600/500 drifted from a 50/50 target on 1100 total -> target 550/550.
    values = pd.Series({"A": 600.0, "B": 500.0})
    weights = pd.Series({"A": 0.5, "B": 0.5})
    target, ratio, money = rebalance_values(values, weights)
    assert target.to_dict() == pytest.approx({"A": 550.0, "B": 550.0})
    assert money == pytest.approx(50.0)  # (|550-600| + |550-500|) / 2
    assert ratio == pytest.approx(50.0 / 1100.0)


def test_threshold_rebalance_fires_when_any_asset_drifts_past_the_band():
    # Target 50/50 on 1000 total; A at 580 is 58% -- 8 points of drift, past a 5pt band.
    values = pd.Series({"A": 580.0, "B": 420.0})
    weights = pd.Series({"A": 0.5, "B": 0.5})
    due = rebalance_due(
        pd.Timestamp("2020-02-29"), pd.Timestamp("2020-01-31"), "threshold",
        values=values, target_weights=weights, threshold_pct=5.0,
    )
    assert due is True


def test_threshold_rebalance_does_not_fire_within_the_band():
    values = pd.Series({"A": 520.0, "B": 480.0})  # 52/48, 2pt drift
    weights = pd.Series({"A": 0.5, "B": 0.5})
    due = rebalance_due(
        pd.Timestamp("2020-02-29"), pd.Timestamp("2020-01-31"), "threshold",
        values=values, target_weights=weights, threshold_pct=5.0,
    )
    assert due is False


def test_threshold_rebalance_at_exactly_the_band_edge_does_not_fire():
    values = pd.Series({"A": 550.0, "B": 450.0})  # exactly 5pt drift
    weights = pd.Series({"A": 0.5, "B": 0.5})
    due = rebalance_due(
        pd.Timestamp("2020-02-29"), pd.Timestamp("2020-01-31"), "threshold",
        values=values, target_weights=weights, threshold_pct=5.0,
    )
    assert due is False


def test_engine_rebalances_only_when_drift_crosses_the_configured_band():
    nav = nav_frame(
        {"FUND_A": [100.0, 100.0, 160.0], "FUND_B": [100.0, 100.0, 100.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "B", "weight": 50},
        ],
        end_date="2020-03-31",
        rebalancing={"mode": "threshold", "threshold_pct": 5.0},
    )
    result = run_backtest(request, nav)
    # Feb: FUND_A unchanged -> no drift, no rebalance.
    # Mar: FUND_A +60% -> 800/500 of 1300 = 61.5% vs 50% target, 11.5pt drift, past the band.
    assert result["summary"]["rebalance_count"] == 1
    assert result["rebalances"][0]["date"] == "2020-03-31"


def test_rebalance_of_an_on_target_portfolio_has_zero_turnover():
    values = pd.Series({"A": 500.0, "B": 500.0})
    weights = pd.Series({"A": 0.5, "B": 0.5})
    _, ratio, money = rebalance_values(values, weights)
    assert money == pytest.approx(0.0)
    assert ratio == pytest.approx(0.0)


def test_rebalance_preserves_total_portfolio_value():
    values = pd.Series({"A": 731.0, "B": 269.0})
    weights = pd.Series({"A": 0.3, "B": 0.7})
    target, _, _ = rebalance_values(values, weights)
    assert float(target.sum()) == pytest.approx(float(values.sum()))


# ---------------------------------------------------------------------------
# Engine: growth, no flows
# ---------------------------------------------------------------------------


def test_buy_and_hold_ending_value_compounds_nav_growth():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 121.0, 133.1]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"],
    )
    result = run_backtest(make_request(), nav)
    # 1000 * 1.1**3
    assert result["summary"]["ending_value"] == pytest.approx(1331.0)
    assert result["summary"]["twrr"] == pytest.approx(1.1**3 - 1)


def test_buy_and_hold_cagr_annualises_the_holding_period_return():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 121.0, 133.1]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"],
    )
    result = run_backtest(make_request(), nav)
    expected = (1.1**3) ** (MONTHS / 3) - 1
    assert result["summary"]["twrr_cagr"] == pytest.approx(expected)


def test_equity_curve_matches_hand_computed_portfolio_path():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 121.0, 133.1]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"],
    )
    result = run_backtest(make_request(), nav)
    assert [point["value"] for point in result["equity_curve"]] == pytest.approx(
        [1000.0, 1100.0, 1210.0, 1331.0]
    )


def test_two_asset_portfolio_value_is_the_weighted_sum():
    nav = nav_frame(
        {"FUND_A": [100.0, 120.0], "FUND_B": [50.0, 45.0]},
        ["2020-01-31", "2020-02-29"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 60},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 40},
        ],
        end_date="2020-02-29",
    )
    result = run_backtest(request, nav)
    # 600 * 1.2 + 400 * 0.9 = 720 + 360
    assert result["summary"]["ending_value"] == pytest.approx(1080.0)


def test_drawdown_curve_tracks_decline_from_running_peak():
    nav = nav_frame(
        {"FUND_A": [100.0, 120.0, 90.0, 100.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"],
    )
    result = run_backtest(make_request(), nav)
    assert [point["value"] for point in result["drawdown_curve"]] == pytest.approx(
        [0.0, 0.0, -0.25, -1 / 6]
    )
    assert result["summary"]["max_drawdown"] == pytest.approx(-0.25)


# ---------------------------------------------------------------------------
# Engine: cashflows must not leak into the time-weighted return
# ---------------------------------------------------------------------------


def test_end_of_period_contribution_is_excluded_from_the_period_return():
    # Market moves +10%; a 100 contribution lands after the move. TWR must be
    # exactly 10% -- the contribution is not performance.
    nav = nav_frame({"FUND_A": [100.0, 110.0]}, ["2020-01-31", "2020-02-29"])
    request = make_request(
        end_date="2020-02-29",
        cashflow={"enabled": True, "type": "contribution", "amount": 100, "frequency": "monthly", "timing": "end"},
    )
    result = run_backtest(request, nav)
    assert result["summary"]["twrr"] == pytest.approx(0.10)
    assert result["summary"]["ending_value"] == pytest.approx(1200.0)


def test_beginning_of_period_contribution_is_excluded_from_the_period_return():
    # 100 is contributed first (base becomes 1100), then the market adds 10%.
    nav = nav_frame({"FUND_A": [100.0, 110.0]}, ["2020-01-31", "2020-02-29"])
    request = make_request(
        end_date="2020-02-29",
        cashflow={
            "enabled": True,
            "type": "contribution",
            "amount": 100,
            "frequency": "monthly",
            "timing": "beginning",
        },
    )
    result = run_backtest(request, nav)
    assert result["summary"]["twrr"] == pytest.approx(0.10)
    assert result["summary"]["ending_value"] == pytest.approx(1210.0)


def test_end_of_period_withdrawal_is_excluded_from_the_period_return():
    nav = nav_frame({"FUND_A": [100.0, 110.0]}, ["2020-01-31", "2020-02-29"])
    request = make_request(
        end_date="2020-02-29",
        cashflow={"enabled": True, "type": "withdrawal", "amount": 100, "frequency": "monthly", "timing": "end"},
    )
    result = run_backtest(request, nav)
    assert result["summary"]["twrr"] == pytest.approx(0.10)
    assert result["summary"]["ending_value"] == pytest.approx(1000.0)


def test_contribution_totals_are_accumulated():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 121.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(
        end_date="2020-03-31",
        cashflow={"enabled": True, "type": "contribution", "amount": 100, "frequency": "monthly", "timing": "end"},
    )
    result = run_backtest(request, nav)
    assert result["summary"]["total_contributed"] == pytest.approx(1200.0)  # 1000 initial + 2 x 100
    assert result["summary"]["cashflow_count"] == 2


def test_withdrawal_is_capped_at_the_available_portfolio_value():
    nav = nav_frame({"FUND_A": [100.0, 100.0]}, ["2020-01-31", "2020-02-29"])
    request = make_request(
        end_date="2020-02-29",
        initial_capital=100.0,
        cashflow={"enabled": True, "type": "withdrawal", "amount": 500, "frequency": "monthly", "timing": "end"},
    )
    result = run_backtest(request, nav)
    assert result["summary"]["ending_value"] == pytest.approx(0.0)
    assert result["summary"]["total_withdrawn"] == pytest.approx(100.0)


def test_quarterly_cashflow_fires_every_third_period():
    dates = pd.date_range("2020-01-31", periods=7, freq="ME")
    nav = nav_frame({"FUND_A": [100.0] * 7}, dates)
    request = make_request(
        end_date="2020-07-31",
        cashflow={"enabled": True, "type": "contribution", "amount": 100, "frequency": "quarterly", "timing": "end"},
    )
    result = run_backtest(request, nav)
    assert result["summary"]["cashflow_count"] == 2  # periods 3 and 6


# ---------------------------------------------------------------------------
# Engine: costs
# ---------------------------------------------------------------------------


def test_transaction_cost_is_charged_on_traded_notional_only():
    nav = nav_frame(
        {"FUND_A": [100.0, 120.0], "FUND_B": [100.0, 100.0]},
        ["2020-01-31", "2020-02-29"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
        end_date="2020-02-29",
        rebalancing="monthly",
        costs={"transaction_bps": 100, "slippage_bps": 0, "annual_drag_pct": 0},
    )
    result = run_backtest(request, nav)
    # 600/500 -> total 1100, target 550/550, one-sided traded notional = 50.
    # 1% of 50 = 0.50 charged once.
    assert result["summary"]["total_costs"] == pytest.approx(0.50)
    assert result["summary"]["ending_value"] == pytest.approx(1099.50)


def test_annual_drag_is_charged_pro_rata_each_month():
    nav = nav_frame({"FUND_A": [100.0, 110.0]}, ["2020-01-31", "2020-02-29"])
    request = make_request(
        end_date="2020-02-29",
        costs={"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 12},
    )
    result = run_backtest(request, nav)
    # 1000 -> 1100 on market, then 1% monthly drag -> 1089.
    assert result["summary"]["ending_value"] == pytest.approx(1089.0)
    assert result["summary"]["total_costs"] == pytest.approx(11.0)


def test_costs_reduce_the_reported_period_return():
    nav = nav_frame({"FUND_A": [100.0, 110.0]}, ["2020-01-31", "2020-02-29"])
    request = make_request(
        end_date="2020-02-29",
        costs={"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 12},
    )
    result = run_backtest(request, nav)
    assert result["summary"]["twrr"] == pytest.approx(1089.0 / 1000.0 - 1)


def test_slippage_and_transaction_bps_are_additive():
    nav = nav_frame(
        {"FUND_A": [100.0, 120.0], "FUND_B": [100.0, 100.0]},
        ["2020-01-31", "2020-02-29"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
        end_date="2020-02-29",
        rebalancing="monthly",
        costs={"transaction_bps": 50, "slippage_bps": 50, "annual_drag_pct": 0},
    )
    result = run_backtest(request, nav)
    assert result["summary"]["total_costs"] == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# Engine: rebalancing schedule
# ---------------------------------------------------------------------------


def test_no_rebalancing_mode_produces_no_rebalance_events():
    nav = nav_frame(
        {"FUND_A": [100.0, 120.0], "FUND_B": [100.0, 90.0]},
        ["2020-01-31", "2020-02-29"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
        end_date="2020-02-29",
    )
    result = run_backtest(request, nav)
    assert result["summary"]["rebalance_count"] == 0


def test_annual_rebalancing_fires_once_per_calendar_year_boundary():
    dates = pd.date_range("2020-11-30", periods=5, freq="ME")  # Nov20..Mar21
    nav = nav_frame({"FUND_A": [100.0] * 5, "FUND_B": [100.0] * 5}, dates)
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
        start_date="2020-11-30",
        end_date="2021-03-31",
        rebalancing="annual",
    )
    result = run_backtest(request, nav)
    assert result["summary"]["rebalance_count"] == 1  # only the Dec->Jan crossing


def test_reported_turnover_is_a_fraction_not_a_money_amount():
    nav = nav_frame(
        {"FUND_A": [100.0, 120.0], "FUND_B": [100.0, 100.0]},
        ["2020-01-31", "2020-02-29"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
        end_date="2020-02-29",
        rebalancing="monthly",
    )
    result = run_backtest(request, nav)
    assert result["rebalances"][0]["turnover"] == pytest.approx(50.0 / 1100.0)
    assert 0.0 <= result["rebalances"][0]["turnover"] <= 1.0


def test_rebalancing_restores_target_weights():
    nav = nav_frame(
        {"FUND_A": [100.0, 120.0], "FUND_B": [100.0, 100.0]},
        ["2020-01-31", "2020-02-29"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
        end_date="2020-02-29",
        rebalancing="monthly",
    )
    result = run_backtest(request, nav)
    rows = {row["proj_id"]: row for row in result["asset_metrics"]["rows"]}
    assert rows["FUND_A"]["final_weight_pct"] == pytest.approx(50.0)
    assert rows["FUND_A"]["drift_pct"] == pytest.approx(0.0)


def test_drift_is_reported_when_rebalancing_is_off():
    nav = nav_frame(
        {"FUND_A": [100.0, 120.0], "FUND_B": [100.0, 100.0]},
        ["2020-01-31", "2020-02-29"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
        end_date="2020-02-29",
    )
    result = run_backtest(request, nav)
    rows = {row["proj_id"]: row for row in result["asset_metrics"]["rows"]}
    # 600 of 1100 = 54.5454...%
    assert rows["FUND_A"]["final_weight_pct"] == pytest.approx(600.0 / 1100.0 * 100)
    assert rows["FUND_A"]["drift_pct"] == pytest.approx(600.0 / 1100.0 * 100 - 50.0)


# ---------------------------------------------------------------------------
# Engine: benchmark comparison
# ---------------------------------------------------------------------------


def test_benchmark_curve_starts_at_initial_capital_and_tracks_benchmark_nav():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0], "FUND_B": [100.0, 200.0]},
        ["2020-01-31", "2020-02-29"],
    )
    request = make_request(end_date="2020-02-29", benchmark="FUND_B")
    result = run_backtest(request, nav)
    assert [point["value"] for point in result["benchmark_curve"]] == pytest.approx([1000.0, 2000.0])


def test_excess_return_is_portfolio_twr_minus_benchmark_twr():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0], "FUND_B": [100.0, 105.0]},
        ["2020-01-31", "2020-02-29"],
    )
    request = make_request(end_date="2020-02-29", benchmark="FUND_B")
    result = run_backtest(request, nav)
    assert result["summary"]["benchmark_excess_return"] == pytest.approx(0.10 - 0.05)


def test_portfolio_equal_to_benchmark_has_zero_excess_and_unit_beta():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 104.5, 120.0, 115.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30", "2020-05-31"],
    )
    request = make_request(end_date="2020-05-31", benchmark="FUND_A")
    result = run_backtest(request, nav)
    metrics = {row["metric"]: row["value"] for row in result["risk_metrics"]["rows"]}
    assert result["summary"]["benchmark_excess_return"] == pytest.approx(0.0, abs=1e-12)
    assert metrics["beta"] == pytest.approx(1.0)
    assert metrics["correlation"] == pytest.approx(1.0)
    assert metrics["tracking_error"] == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# Engine: tables
# ---------------------------------------------------------------------------


def test_monthly_returns_table_matches_the_period_returns():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 99.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    result = run_backtest(make_request(end_date="2020-03-31"), nav)
    assert [row["return"] for row in result["monthly_returns"]["rows"]] == pytest.approx([0.10, -0.10])


def test_annual_returns_compound_the_months_within_each_calendar_year():
    dates = ["2020-11-30", "2020-12-31", "2021-01-31", "2021-02-28"]
    nav = nav_frame({"FUND_A": [100.0, 110.0, 121.0, 108.9]}, dates)
    request = make_request(start_date="2020-11-30", end_date="2021-02-28")
    result = run_backtest(request, nav)
    rows = {row["year"]: row["return"] for row in result["annual_returns"]["rows"]}
    assert rows[2020] == pytest.approx(0.10)  # only Dec return falls in 2020
    assert rows[2021] == pytest.approx(1.10 * 0.90 - 1)


def test_asset_cagr_matches_that_assets_own_nav_growth():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 121.0, 133.1], "FUND_B": [100.0, 100.0, 100.0, 100.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
    )
    result = run_backtest(request, nav)
    rows = {row["proj_id"]: row for row in result["asset_metrics"]["rows"]}
    assert rows["FUND_A"]["cagr"] == pytest.approx((1.1**3) ** (MONTHS / 3) - 1)
    assert rows["FUND_B"]["cagr"] == pytest.approx(0.0)


def test_diversification_reports_one_row_per_unordered_asset_pair():
    nav = nav_frame(
        {
            "FUND_A": [100.0, 110.0, 121.0],
            "FUND_B": [100.0, 90.0, 81.0],
            "FUND_C": [100.0, 105.0, 110.25],
        },
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 34},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 33},
            {"proj_id": "FUND_C", "display_name": "Fund C", "weight": 33},
        ],
        end_date="2020-03-31",
    )
    result = run_backtest(request, nav)
    pairs = {(row["asset_a"], row["asset_b"]) for row in result["diversification"]["rows"]}
    assert pairs == {("FUND_A", "FUND_B"), ("FUND_A", "FUND_C"), ("FUND_B", "FUND_C")}


# ---------------------------------------------------------------------------
# Internal consistency across the whole result payload
# ---------------------------------------------------------------------------


def test_equity_curve_endpoint_equals_reported_ending_value():
    nav = nav_frame(
        {"FUND_A": [100.0, 112.0, 103.0], "FUND_B": [50.0, 48.0, 55.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 70},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 30},
        ],
        end_date="2020-03-31",
        rebalancing="monthly",
        costs={"transaction_bps": 25, "slippage_bps": 10, "annual_drag_pct": 1.5},
    )
    result = run_backtest(request, nav)
    assert result["equity_curve"][-1]["value"] == pytest.approx(result["summary"]["ending_value"])


def test_twrr_compounds_the_reported_monthly_returns():
    nav = nav_frame(
        {"FUND_A": [100.0, 112.0, 103.0], "FUND_B": [50.0, 48.0, 55.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 70},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 30},
        ],
        end_date="2020-03-31",
        rebalancing="monthly",
    )
    result = run_backtest(request, nav)
    compounded = float(np.prod([1 + row["return"] for row in result["monthly_returns"]["rows"]]) - 1)
    assert result["summary"]["twrr"] == pytest.approx(compounded)


def test_without_flows_or_costs_twrr_reconciles_the_ending_value():
    nav = nav_frame(
        {"FUND_A": [100.0, 112.0, 103.0], "FUND_B": [50.0, 48.0, 55.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 70},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 30},
        ],
        end_date="2020-03-31",
    )
    result = run_backtest(request, nav)
    implied = 1000.0 * (1 + result["summary"]["twrr"])
    assert implied == pytest.approx(result["summary"]["ending_value"])


def test_asset_final_weights_sum_to_one_hundred_percent():
    nav = nav_frame(
        {"FUND_A": [100.0, 112.0, 103.0], "FUND_B": [50.0, 48.0, 55.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 70},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 30},
        ],
        end_date="2020-03-31",
    )
    result = run_backtest(request, nav)
    total = sum(row["final_weight_pct"] for row in result["asset_metrics"]["rows"])
    assert total == pytest.approx(100.0)


def test_rebalance_costs_sum_to_reported_total_costs_when_drag_is_off():
    nav = nav_frame(
        {"FUND_A": [100.0, 112.0, 103.0], "FUND_B": [50.0, 48.0, 55.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 70},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 30},
        ],
        end_date="2020-03-31",
        rebalancing="monthly",
        costs={"transaction_bps": 25, "slippage_bps": 10, "annual_drag_pct": 0},
    )
    result = run_backtest(request, nav)
    assert sum(row["cost"] for row in result["rebalances"]) == pytest.approx(
        result["summary"]["total_costs"]
    )


def test_rolling_correlation_of_a_two_point_window_is_exactly_plus_or_minus_one():
    # Pearson correlation of exactly 2 points is always +-1 (or undefined if
    # either point pair is constant) -- a deterministic case perfect for a
    # hand-derived check rather than trusting the implementation's own math.
    asset_returns = pd.DataFrame(
        {
            "A": [0.01, 0.02, -0.01, 0.03],
            "B": [0.02, 0.01, -0.02, 0.01],
        }
    )
    rows = rolling_correlation(asset_returns, window=2)
    values = [row["correlation"] for row in rows]
    # window[0,1]: A rises, B falls -> -1. window[1,2] and window[2,3]: same
    # direction both times -> +1.
    assert values == pytest.approx([-1.0, 1.0, 1.0])
    assert {row["asset_a"] for row in rows} == {"A"}
    assert {row["asset_b"] for row in rows} == {"B"}


def test_rolling_correlation_emits_one_series_per_unordered_asset_pair():
    asset_returns = pd.DataFrame(
        {
            "A": [0.01, 0.02, -0.01, 0.03],
            "B": [0.02, 0.01, -0.02, 0.01],
            "C": [0.01, 0.02, -0.01, 0.03],
        }
    )
    rows = rolling_correlation(asset_returns, window=2)
    pairs = {(row["asset_a"], row["asset_b"]) for row in rows}
    assert pairs == {("A", "B"), ("A", "C"), ("B", "C")}


def test_rolling_correlation_against_a_constant_series_is_none_not_nan():
    asset_returns = pd.DataFrame({"A": [0.01, 0.02, 0.03], "B": [0.01, 0.01, 0.01]})
    rows = rolling_correlation(asset_returns, window=2)
    assert all(row["correlation"] is None for row in rows)


def test_engine_exposes_rolling_correlation_for_a_multi_asset_portfolio():
    # A rolling 12-month correlation needs at least 13 monthly NAV points (12
    # return observations) before the first window is even full.
    dates = pd.date_range("2020-01-31", periods=14, freq="ME")
    a_values = [100.0]
    b_values = [100.0]
    for step in range(1, 14):
        a_values.append(a_values[-1] * (1.02 if step % 2 else 0.99))
        b_values.append(b_values[-1] * (0.98 if step % 2 else 1.01))
    nav = nav_frame({"FUND_A": a_values, "FUND_B": b_values}, dates)
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "B", "weight": 50},
        ],
        end_date=str(dates[-1].date()),
    )
    result = run_backtest(request, nav)
    assert result["rolling_correlation"], "expected at least one rolling-correlation row"
    assert {row["asset_a"] for row in result["rolling_correlation"]} == {"FUND_A"}
    assert {row["asset_b"] for row in result["rolling_correlation"]} == {"FUND_B"}


def test_irr_equals_cagr_when_there_are_no_intermediate_cashflows():
    # With only an initial outlay and a terminal value, money-weighted return
    # (IRR) and time-weighted return must agree exactly -- there is no
    # intermediate flow for the two measures to disagree about.
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 121.0, 133.1]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"],
    )
    result = run_backtest(make_request(), nav)
    assert result["summary"]["irr"] == pytest.approx(result["summary"]["twrr_cagr"], abs=1e-6)


def test_irr_penalises_a_contribution_made_right_before_a_downturn():
    # A lump sum invested at t=0 that grows steadily has one IRR. Adding a
    # large contribution right before a loss must pull the money-weighted
    # return down more than the time-weighted return, because more capital was
    # exposed to the loss -- that is the entire reason IRR and TWRR diverge.
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 88.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(
        end_date="2020-03-31",
        cashflow={"enabled": True, "type": "contribution", "amount": 5000, "frequency": "monthly", "timing": "end"},
    )
    result = run_backtest(request, nav)
    assert result["summary"]["irr"] < result["summary"]["twrr_cagr"]


def test_irr_is_none_when_it_cannot_be_solved():
    # All-positive cashflows (huge contribution keeps growing, nothing ever
    # comes back out relative to what went in) can leave no rate in range
    # solving NPV = 0; money_weighted_return already returns None for that
    # rather than raising, and the engine must not crash on it.
    from backend.app.engine.returns import money_weighted_return

    assert money_weighted_return([(0.0, 100.0), (1.0, 100.0)]) is None


def test_summary_reports_var_95_and_var_99():
    nav = nav_frame(
        {"FUND_A": [100.0, 95.0, 110.0, 90.0, 120.0, 105.0, 130.0, 100.0]},
        [
            "2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30",
            "2020-05-31", "2020-06-30", "2020-07-31", "2020-08-31",
        ],
    )
    result = run_backtest(make_request(end_date="2020-08-31"), nav)
    returns = pd.Series([row["return"] for row in result["monthly_returns"]["rows"]])
    assert result["summary"]["var_95"] == pytest.approx(historical_var(returns, confidence=0.95))
    assert result["summary"]["var_99"] == pytest.approx(historical_var(returns, confidence=0.99))
    assert result["summary"]["var_99"] >= result["summary"]["var_95"]


def test_summary_reports_sortino_and_calmar_alongside_sharpe():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 88.0, 101.2, 106.26]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30", "2020-05-31"],
    )
    result = run_backtest(make_request(end_date="2020-05-31"), nav)
    returns = pd.Series([row["return"] for row in result["monthly_returns"]["rows"]])
    values = pd.Series([point["value"] for point in result["equity_curve"]])

    assert result["summary"]["sortino"] == pytest.approx(
        sortino_ratio(returns, 0.0, MONTHS)
    )
    assert result["summary"]["calmar"] == pytest.approx(
        calmar_ratio(returns, values, MONTHS)
    )


def test_sortino_uses_the_requested_risk_free_rate():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 88.0, 101.2, 106.26]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30", "2020-05-31"],
    )
    without_rf = run_backtest(make_request(end_date="2020-05-31"), nav)
    with_rf = run_backtest(make_request(end_date="2020-05-31", risk_free_rate_pct=5), nav)
    assert with_rf["summary"]["sortino"] < without_rf["summary"]["sortino"]


def test_flat_portfolio_reports_no_calmar_rather_than_dividing_by_zero():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 121.0, 133.1]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"],
    )
    result = run_backtest(make_request(), nav)
    assert result["summary"]["calmar"] is None


def test_zero_volatility_portfolio_reports_no_sharpe_rather_than_infinity():
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 121.0, 133.1]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"],
    )
    result = run_backtest(make_request(), nav)
    assert result["summary"]["sharpe"] is None


def test_a_gap_in_the_benchmark_is_rejected_rather_than_silently_collapsed():
    # pct_change yields NaN across a gap, so dropping those periods would splice
    # the benchmark curve back together and understate its growth: 100 -> 120 is
    # +20%, but a collapsed curve reports only +9.57%. Every benchmark-relative
    # number (excess return, alpha, beta, tracking error, information ratio)
    # would then be computed against a series that never existed.
    nav = nav_frame(
        {
            "FUND_A": [100.0, 110.0, 121.0, 133.1, 146.41],
            "FUND_B": [100.0, 105.0, float("nan"), 115.0, 120.0],
        },
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30", "2020-05-31"],
    )
    request = make_request(end_date="2020-05-31", benchmark="FUND_B")
    with pytest.raises(ValueError, match="2020-03"):
        run_backtest(request, nav)


def test_a_complete_benchmark_outside_the_selected_assets_still_runs():
    nav = nav_frame(
        {
            "FUND_A": [100.0, 110.0, 121.0],
            "FUND_B": [100.0, 105.0, 110.25],
        },
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(end_date="2020-03-31", benchmark="FUND_B")
    result = run_backtest(request, nav)
    assert [point["value"] for point in result["benchmark_curve"]] == pytest.approx(
        [1000.0, 1050.0, 1102.5]
    )
    assert result["summary"]["benchmark_excess_return"] == pytest.approx(
        (1.1**2 - 1) - (1.05**2 - 1)
    )


def test_correlation_against_a_constant_series_is_undefined_not_nan():
    # Correlation divides by each series' standard deviation; against a
    # zero-variance series it is 0/0. That is undefined, so report None rather
    # than leaking a NaN float into the payload.
    from backend.app.engine.metrics import correlation

    varying = pd.Series([0.03, -0.02, 0.04, -0.01])
    constant = pd.Series([0.01, 0.01, 0.01, 0.01])
    assert correlation(varying, constant) is None


def test_engine_never_emits_non_finite_numbers():
    # Two assets whose returns are each constant -> every correlation is 0/0.
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 121.0], "FUND_B": [100.0, 90.0, 81.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    request = make_request(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
        end_date="2020-03-31",
    )
    result = run_backtest(request, nav)

    offenders = []

    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for position, value in enumerate(node):
                walk(value, f"{path}[{position}]")
        elif isinstance(node, float) and not math.isfinite(node):
            offenders.append((path, node))

    walk(result)
    assert offenders == []


def test_daily_frequency_does_not_flag_weekends_as_missing_data():
    # Business days only, Mon 2024-01-01 (a holiday in most calendars, but this
    # test only cares about weekday vs weekend, not public holidays) through
    # Fri 2024-01-05, skipping the following Sat/Sun entirely -- this must not
    # raise "incomplete NAV periods" the way a genuine weekday gap would.
    dates = pd.bdate_range("2024-01-01", "2024-01-05")
    nav = nav_frame({"FUND_A": [100.0, 101.0, 102.0, 101.5, 103.0]}, dates)
    result = run_backtest(make_request(start_date="2024-01-01", end_date="2024-01-05", frequency="daily"), nav)
    assert result["summary"]["ending_value"] == pytest.approx(1000.0 * 103.0 / 100.0)


def test_daily_frequency_still_flags_a_genuine_weekday_gap():
    # A business day (Wed 2024-01-03) is missing entirely from the panel --
    # this is a real data gap, not a weekend, and must still be rejected.
    dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-04", "2024-01-05"])
    nav = nav_frame({"FUND_A": [100.0, 101.0, 102.0, 103.0]}, dates)
    with pytest.raises(ValueError, match="2024-01-03"):
        run_backtest(make_request(start_date="2024-01-01", end_date="2024-01-05", frequency="daily"), nav)


def test_daily_frequency_annualizes_with_252_periods_per_year():
    dates = pd.bdate_range("2024-01-01", periods=6)
    nav = nav_frame({"FUND_A": [100.0, 101.0, 100.5, 101.5, 102.0, 101.0]}, dates)
    result = run_backtest(make_request(start_date=str(dates[0].date()), end_date=str(dates[-1].date()), frequency="daily"), nav)
    returns = pd.Series([row["return"] for row in result["monthly_returns"]["rows"]])
    assert result["summary"]["twrr_cagr"] == pytest.approx(annualized_return(returns, 252))
    assert result["summary"]["volatility"] == pytest.approx(annualized_volatility(returns, 252))


def test_monthly_frequency_is_unaffected_by_the_daily_option():
    # Default behavior must be byte-for-byte the same as before this feature.
    nav = nav_frame(
        {"FUND_A": [100.0, 110.0, 121.0, 133.1]},
        ["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"],
    )
    result = run_backtest(make_request(), nav)
    assert result["summary"]["ending_value"] == pytest.approx(1331.0)
    assert result["summary"]["twrr_cagr"] == pytest.approx((1.1**3) ** (12 / 3) - 1)


def test_flat_market_produces_zero_return_and_zero_drawdown():
    nav = nav_frame(
        {"FUND_A": [100.0, 100.0, 100.0]},
        ["2020-01-31", "2020-02-29", "2020-03-31"],
    )
    result = run_backtest(make_request(end_date="2020-03-31"), nav)
    assert result["summary"]["twrr"] == pytest.approx(0.0)
    assert result["summary"]["twrr_cagr"] == pytest.approx(0.0)
    assert result["summary"]["max_drawdown"] == pytest.approx(0.0)
    assert result["summary"]["ending_value"] == pytest.approx(1000.0)
