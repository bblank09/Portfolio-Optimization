import pandas as pd
import pytest

from backend.app.domain.schemas import BacktestRequest
from backend.app.engine.backtest import run_backtest


def monthly_dca_request():
    return BacktestRequest(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
        start_date="2020-01-31",
        end_date="2020-04-30",
        initial_capital=1000,
        benchmark_proj_id="FUND_A",
        cashflow={"enabled": True, "type": "contribution", "amount": 100, "frequency": "monthly", "timing": "end"},
        rebalancing={"mode": "monthly"},
        costs={"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
        data={"source": "sec_open_data", "price_field": "nav_per_unit"},
    )


def backtest_request(
    *,
    timing="end",
    cashflow_enabled=True,
    cashflow_type="contribution",
    cashflow_amount=100,
    frequency="monthly",
    end_date="2020-03-31",
):
    return BacktestRequest(
        assets=[
            {"proj_id": "FUND_A", "display_name": "Fund A", "weight": 50},
            {"proj_id": "FUND_B", "display_name": "Fund B", "weight": 50},
        ],
        start_date="2020-01-31",
        end_date=end_date,
        initial_capital=1000,
        benchmark_proj_id="FUND_A",
        cashflow={
            "enabled": cashflow_enabled,
            "type": cashflow_type,
            "amount": cashflow_amount,
            "frequency": frequency,
            "timing": timing,
        },
        rebalancing={"mode": "none"},
        costs={"transaction_bps": 0, "slippage_bps": 0, "annual_drag_pct": 0},
        data={"source": "sec_open_data", "price_field": "nav_per_unit"},
    )


def test_sec_nav_backtest_with_monthly_dca():
    request = monthly_dca_request()
    nav = pd.DataFrame(
        {"FUND_A": [10, 11, 9.9, 12], "FUND_B": [20, 21, 18.9, 22]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31", "2020-04-30"]),
    )
    result = run_backtest(request, nav)
    assert result["data_source"] == "sec_open_data"
    assert result["summary"]["ending_value"] > 0
    assert result["summary"]["cashflow_count"] == 3
    assert result["summary"]["rebalance_count"] == 3
    assert len(result["equity_curve"]) == 4


def test_backtest_deducts_rebalance_costs():
    payload = monthly_dca_request().model_dump(mode="json")
    payload["costs"] = {"transaction_bps": 10, "slippage_bps": 0, "annual_drag_pct": 0}
    request = BacktestRequest(**payload)
    nav = pd.DataFrame(
        {"FUND_A": [10, 12, 12], "FUND_B": [20, 20, 22]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"]),
    )
    result = run_backtest(request, nav)
    assert result["summary"]["total_costs"] > 0


def test_contributions_do_not_create_investment_returns_on_flat_nav():
    request = backtest_request()
    nav = pd.DataFrame(
        {"FUND_A": [10, 10, 10], "FUND_B": [20, 20, 20]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"]),
    )

    result = run_backtest(request, nav)

    assert result["summary"]["twrr"] == pytest.approx(0)
    assert result["summary"]["twrr_cagr"] == pytest.approx(0)
    assert result["summary"]["sharpe"] is None
    assert result["summary"]["benchmark_excess_return"] == pytest.approx(0)
    assert [row["return"] for row in result["monthly_returns"]["rows"]] == pytest.approx([0, 0])


def test_withdrawals_do_not_distort_performance_or_relative_metrics():
    nav = pd.DataFrame(
        {"FUND_A": [10, 12, 10.8], "FUND_B": [20, 21, 21.525]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"]),
    )

    without_cashflows = run_backtest(backtest_request(cashflow_enabled=False), nav)
    with_withdrawals = run_backtest(backtest_request(cashflow_type="withdrawal"), nav)

    for metric in ("twrr", "twrr_cagr", "sharpe", "benchmark_excess_return"):
        assert with_withdrawals["summary"][metric] == pytest.approx(without_cashflows["summary"][metric])
    for withdrawal_metric, baseline_metric in zip(
        with_withdrawals["risk_metrics"]["rows"], without_cashflows["risk_metrics"]["rows"], strict=True
    ):
        assert withdrawal_metric["metric"] == baseline_metric["metric"]
        assert withdrawal_metric["value"] == pytest.approx(baseline_metric["value"])


def test_capped_withdrawal_does_not_create_investment_returns_on_flat_nav():
    request = backtest_request(cashflow_type="withdrawal", cashflow_amount=2000)
    nav = pd.DataFrame(
        {"FUND_A": [10, 10, 10], "FUND_B": [20, 20, 20]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"]),
    )

    result = run_backtest(request, nav)

    assert result["summary"]["total_withdrawn"] == pytest.approx(1000)
    assert result["cashflows"][0]["amount"] == pytest.approx(-1000)
    assert result["summary"]["twrr"] == pytest.approx(0)
    assert result["summary"]["twrr_cagr"] == pytest.approx(0)
    assert result["summary"]["sharpe"] is None
    assert result["summary"]["benchmark_excess_return"] == pytest.approx(0)
    risk_metrics = {row["metric"]: row["value"] for row in result["risk_metrics"]["rows"]}
    assert risk_metrics["beta"] == pytest.approx(0)
    assert risk_metrics["alpha"] == pytest.approx(0)
    assert risk_metrics["tracking_error"] == pytest.approx(0)
    assert risk_metrics["information_ratio"] is None
    assert pd.isna(risk_metrics["correlation"])


def test_cashflow_timing_changes_ending_value_on_non_flat_nav():
    nav = pd.DataFrame(
        {"FUND_A": [10, 11, 11], "FUND_B": [20, 22, 22]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"]),
    )

    beginning = run_backtest(backtest_request(timing="beginning"), nav)
    ending = run_backtest(backtest_request(timing="end"), nav)

    assert beginning["summary"]["ending_value"] > ending["summary"]["ending_value"]
    assert beginning["summary"]["twrr"] == pytest.approx(0.1)
    assert ending["summary"]["twrr"] == pytest.approx(0.1)
    assert beginning["equity_curve"][-1]["value"] != pytest.approx(ending["equity_curve"][-1]["value"])


def test_benchmark_curve_uses_same_initial_anchor_as_equity_curve():
    request = backtest_request(cashflow_enabled=False)
    nav = pd.DataFrame(
        {"FUND_A": [10, 11, 12], "FUND_B": [20, 21, 22]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"]),
    )

    result = run_backtest(request, nav)

    assert result["equity_curve"][0]["date"] == result["benchmark_curve"][0]["date"]
    assert result["equity_curve"][0]["value"] == result["benchmark_curve"][0]["value"] == 1000
    assert result["summary"]["twrr"] == pytest.approx(0.15)


def test_near_100_percent_weights_preserve_capital_and_cashflow_accounting():
    payload = backtest_request().model_dump(mode="json")
    payload["assets"][1]["weight"] = 49.995
    request = BacktestRequest(**payload)
    nav = pd.DataFrame(
        {"FUND_A": [10, 10, 10], "FUND_B": [20, 20, 20]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"]),
    )

    result = run_backtest(request, nav)

    assert result["equity_curve"][0]["value"] == pytest.approx(1000)
    assert result["summary"]["total_contributed"] == pytest.approx(1200)
    assert result["summary"]["ending_value"] == pytest.approx(1200)


def test_missing_benchmark_nav_periods_do_not_become_comparisons():
    # Dropping the gap would splice 10 -> 11 -> 13 -> 14 into a curve that grew
    # 18.46% when the benchmark actually grew 40%, so every benchmark-relative
    # number would be measured against a series that never existed. Refuse the
    # run instead, exactly as an incomplete holding is refused.
    request = backtest_request(cashflow_enabled=False, end_date="2020-05-31")
    nav = pd.DataFrame(
        {
            "FUND_A": [10, 10, 10, 10, 10],
            "FUND_B": [20, 20, 20, 20, 20],
            "BENCHMARK": [10, 11, None, 13, 14],
        },
        index=pd.date_range("2020-01-31", periods=5, freq="ME"),
    )
    payload = request.model_dump(mode="json")
    payload["benchmark_proj_id"] = "BENCHMARK"

    with pytest.raises(ValueError, match="2020-03"):
        run_backtest(BacktestRequest(**payload), nav)


def test_complete_benchmark_outside_the_holdings_is_compared_in_full():
    request = backtest_request(cashflow_enabled=False, end_date="2020-03-31")
    nav = pd.DataFrame(
        {
            "FUND_A": [10, 10, 10],
            "FUND_B": [20, 20, 20],
            "BENCHMARK": [10, 11, 12.1],
        },
        index=pd.date_range("2020-01-31", periods=3, freq="ME"),
    )
    payload = request.model_dump(mode="json")
    payload["benchmark_proj_id"] = "BENCHMARK"

    result = run_backtest(BacktestRequest(**payload), nav)

    # Flat portfolio against a benchmark that compounded 10% twice.
    assert [point["value"] for point in result["benchmark_curve"]] == pytest.approx(
        [1000.0, 1100.0, 1210.0]
    )
    assert result["summary"]["benchmark_excess_return"] == pytest.approx(-(1.1**2 - 1))


@pytest.mark.parametrize(
    "nav",
    [
        pd.DataFrame(
            {"FUND_A": [10, None, 10], "FUND_B": [20, 20, 20]},
            index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"]),
        ),
        pd.DataFrame(
            {"FUND_A": [10, 10], "FUND_B": [20, 20]},
            index=pd.to_datetime(["2020-01-31", "2020-03-31"]),
        ),
    ],
    ids=["missing-selected-nav", "absent-calendar-month"],
)
def test_incomplete_selected_asset_months_are_rejected(nav):
    with pytest.raises(ValueError, match="incomplete NAV periods for the selected funds or benchmark: 2020-02"):
        run_backtest(backtest_request(), nav)


def test_asset_metrics_report_real_final_weight_and_drift_no_rebalancing():
    request = backtest_request(cashflow_enabled=False)
    payload = request.model_dump(mode="json")
    payload["rebalancing"] = {"mode": "none"}
    request = BacktestRequest(**payload)
    # FUND_A doubles, FUND_B is flat, so with no rebalancing the 50/50 target
    # must drift toward FUND_A: final value = [1000, 500], total 1500.
    nav = pd.DataFrame(
        {"FUND_A": [10, 20, 20], "FUND_B": [20, 20, 20]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"]),
    )

    result = run_backtest(request, nav)

    rows = {row["proj_id"]: row for row in result["asset_metrics"]["rows"]}
    assert rows["FUND_A"]["target_weight_pct"] == pytest.approx(50)
    assert rows["FUND_A"]["final_weight_pct"] == pytest.approx(1000 / 1500 * 100)
    assert rows["FUND_A"]["drift_pct"] == pytest.approx(1000 / 1500 * 100 - 50)
    assert rows["FUND_B"]["final_weight_pct"] == pytest.approx(500 / 1500 * 100)
    assert rows["FUND_B"]["drift_pct"] == pytest.approx(500 / 1500 * 100 - 50)
    # FUND_A's own CAGR must differ from FUND_B's — these are per-asset, not the portfolio figure.
    assert rows["FUND_A"]["cagr"] != pytest.approx(rows["FUND_B"]["cagr"])


def test_rebalance_turnover_is_a_fraction_of_portfolio_value_not_raw_money():
    payload = backtest_request(cashflow_enabled=False, end_date="2020-02-29").model_dump(mode="json")
    payload["rebalancing"] = {"mode": "monthly"}
    request = BacktestRequest(**payload)
    nav = pd.DataFrame(
        {"FUND_A": [10, 12], "FUND_B": [20, 20]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29"]),
    )

    result = run_backtest(request, nav)

    # values drift to [600, 500] (total 1100) before rebalancing back to [550, 550];
    # one-way money turnover is 50, so the ratio must be 50/1100, not the raw 50.
    assert result["rebalances"][0]["turnover"] == pytest.approx(50 / 1100)
    assert result["rebalances"][0]["turnover"] < 1


@pytest.mark.parametrize(
    ("frequency", "periods", "expected_positions"),
    [
        ("quarterly", 7, [3, 6]),
        ("annual", 13, [12]),
    ],
)
def test_cashflow_frequency_uses_expected_period_schedule(frequency, periods, expected_positions):
    dates = pd.date_range("2020-01-31", periods=periods, freq="ME")
    nav = pd.DataFrame({"FUND_A": 10.0, "FUND_B": 20.0}, index=dates)
    request = backtest_request(
        frequency=frequency,
        end_date=dates[-1].date().isoformat(),
    )

    result = run_backtest(request, nav)

    assert result["summary"]["cashflow_count"] == len(expected_positions)
    assert [row["date"] for row in result["cashflows"]] == [
        dates[position].date().isoformat() for position in expected_positions
    ]
