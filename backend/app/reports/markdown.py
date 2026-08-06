from __future__ import annotations

from typing import Any, cast


def render_research_report(
    *,
    request: dict[str, Any],
    result: dict[str, Any],
    manifest: dict[str, Any],
    quality_issues: list[dict[str, Any]] | None = None,
) -> str:
    """Render a research-report markdown document from persisted production artifacts."""
    quality_issues = quality_issues or result.get("quality_issues", []) or []
    summary = result.get("summary", {})
    risk_metrics = ensure_rows(result.get("risk_metrics", {}).get("rows", []))
    diversification = ensure_rows(result.get("diversification", {}).get("rows", []))

    sections = [
        ("SEC Dataset Manifest", manifest_section(manifest)),
        ("Selected Funds", selected_funds_section(request)),
        ("Input Assumptions", input_assumptions_section(request)),
        ("NAV Alignment Method", nav_alignment_section()),
        ("Cashflow Method", cashflow_section(request)),
        ("Rebalancing Method", rebalancing_section(request)),
        ("Formula Reference", formula_reference_section()),
        ("Performance and Risk Results", summary_table(summary)),
        ("Benchmark Risk", rows_table(risk_metrics)),
        ("Drawdown Stress", drawdown_stress_section(summary)),
        ("Diversification Check", rows_table(diversification)),
        ("Data Quality Issues", quality_section(quality_issues)),
        ("Reproducibility", reproducibility_section(result)),
        ("Limitations", limitations_section()),
    ]
    title = "# Portfolio Backtesting Research Report\n\n"
    body = "\n\n".join(f"## {heading}\n\n{content}" for heading, content in sections)
    return title + body + "\n"


def manifest_section(manifest: dict[str, Any]) -> str:
    if not manifest:
        return "Manifest unavailable. Expected source: SEC Open Data cached NAV."
    rows = [[key, value] for key, value in sorted(flatten_manifest(manifest).items())]
    return rows_table([{"field": key, "value": value} for key, value in rows])


def selected_funds_section(request: dict[str, Any]) -> str:
    assets = request.get("assets", [])
    if not assets:
        return "No selected funds were recorded."
    rows = [
        {
            "proj_id": asset.get("proj_id"),
            "display_name": asset.get("display_name", ""),
            "weight": format_percent(asset.get("weight"), scale=1),
        }
        for asset in assets
    ]
    benchmark = request.get("benchmark_proj_id", "")
    return rows_table(rows) + f"\n\nBenchmark fund: `{benchmark}`."


def input_assumptions_section(request: dict[str, Any]) -> str:
    costs = request.get("costs", {})
    cashflow = request.get("cashflow", {})
    rows: list[dict[str, Any]] = [
        {"input": "Start date", "value": request.get("start_date")},
        {"input": "End date", "value": request.get("end_date")},
        {"input": "Initial capital", "value": format_money(request.get("initial_capital"))},
        {"input": "Risk-free rate", "value": format_percent(request.get("risk_free_rate_pct"), scale=1)},
        {"input": "Cashflow", "value": cashflow_description(cashflow)},
        {"input": "Rebalancing", "value": request.get("rebalancing", {}).get("mode", "unknown")},
        {"input": "Transaction cost", "value": f"{costs.get('transaction_bps', 0)} bps"},
        {"input": "Slippage", "value": f"{costs.get('slippage_bps', 0)} bps"},
        {"input": "Annual drag", "value": format_percent(costs.get("annual_drag_pct"), scale=1)},
        {"input": "Data source", "value": request.get("data", {}).get("source", "sec_open_data")},
        {"input": "Price field", "value": request.get("data", {}).get("price_field", "nav_per_unit")},
        {"input": "NAV granularity", "value": request.get("data", {}).get("frequency", "monthly")},
    ]
    return rows_table(rows)


def nav_alignment_section() -> str:
    return (
        "Daily SEC NAV observations are loaded from the normalized local cache, filtered to selected fund "
        "`proj_id` columns, then resampled and aligned across the complete cache at month-end. If the final "
        "cache resampling label falls after the latest observed NAV date, that final label is capped to the "
        "latest observed date. The engine then slices the aligned panel to the requested date range; an earlier "
        "requested end date does not independently create or cap a partial month-end row."
    )


def cashflow_section(request: dict[str, Any]) -> str:
    cashflow = request.get("cashflow", {})
    if not cashflow.get("enabled"):
        return "Recurring cashflows are disabled for this run."
    return (
        f"Recurring `{cashflow.get('type')}` cashflows of {format_money(cashflow.get('amount'))} "
        f"are applied `{cashflow.get('frequency')}` at `{cashflow.get('timing')}` of period."
    )


def rebalancing_section(request: dict[str, Any]) -> str:
    rebalancing = request.get("rebalancing", {})
    mode = rebalancing.get("mode", "unknown")
    if mode == "none":
        return "Rebalancing is disabled; portfolio weights drift with SEC NAV returns."
    if mode == "threshold":
        threshold_pct = rebalancing.get("threshold_pct", "unknown")
        return (
            f"Portfolio holdings are rebalanced to target weights whenever any holding's weight drifts "
            f"more than `{threshold_pct}` percentage points from its target, checked each period."
        )
    return f"Portfolio holdings are rebalanced to target weights using `{mode}` schedule when the rebalance rule is due."


def formula_reference_section() -> str:
    rows = [
        {
            "formula": "simple_returns",
            "equation": "r_t = NAV_t / NAV_{t-1} - 1",
            "variables": "NAV_t = SEC NAV per unit at period t; r_t = period return",
            "used_for": "Fund returns, benchmark returns, monthly returns",
        },
        {
            "formula": "time_weighted_return",
            "equation": "TWRR = product_{t=1..n}(1 + r_t) - 1",
            "variables": "r_t = portfolio period return after return path construction; n = observed periods",
            "used_for": "Total portfolio return and benchmark excess return",
        },
        {
            "formula": "annualized_return",
            "equation": "R_ann = product_{t=1..n}(1 + r_t)^(m / n) - 1",
            "variables": "m = periods per year: 12 for month-end data, 252 for daily (business-day) data",
            "used_for": "TWRR CAGR, benchmark CAGR, CAPM alpha input",
        },
        {
            "formula": "money_weighted_return",
            "equation": "solve for r: sum_i(CF_i / (1 + r)^t_i) = 0",
            "variables": "CF_i = investor-perspective cashflow at nominal elapsed year t_i (initial outlay, each contribution/withdrawal, terminal value)",
            "used_for": "IRR (money-weighted return) -- diverges from TWRR CAGR when flow timing affects the investor's realised return",
        },
        {
            "formula": "annualized_volatility",
            "equation": "sigma_ann = std(r_t, ddof=1) * sqrt(m)",
            "variables": "std(..., ddof=1) = unbiased sample standard deviation, the same convention as the cov/var behind beta",
            "used_for": "Volatility and Sharpe denominator",
        },
        {
            "formula": "max_drawdown",
            "equation": "DD_t = V_t / max(V_0,...,V_t) - 1; MDD = min(DD_t)",
            "variables": "V_t = simulated portfolio value at period t",
            "used_for": "Maximum drawdown and repeat-drawdown stress scenario",
        },
        {
            "formula": "beta_alpha",
            "equation": "beta = cov(R_p, R_b) / var(R_b); alpha = R_p,ann - [R_f + beta * (R_b,ann - R_f)]",
            "variables": "R_p = portfolio returns; R_b = benchmark returns; R_f = annual risk-free rate",
            "used_for": "Benchmark Risk tab: beta and CAPM-style alpha",
        },
    ]
    return (
        rows_table(rows)
        + "\n\nAdditional report ratios: `Sharpe = (R_ann - R_f) / sigma_ann`, "
        "`Sortino = (R_ann - R_f) / sigma_down` where "
        "`sigma_down = sqrt(mean(min(r_t - MAR, 0)^2)) * sqrt(m)` with `MAR = 0`, "
        "`Calmar = R_ann / |MDD|`, "
        "`VaR_c = max(0, -percentile(r_t, (1 - c) * 100))` (historical, non-parametric), "
        "`tracking_error = std(R_p - R_b, ddof=1) * sqrt(m)`, and "
        "`information_ratio = (R_p,ann - R_b,ann) / tracking_error`.\n\n"
        "See `docs/formula-reference.md` for the expanded methodology notes."
    )


def summary_table(summary: dict[str, Any]) -> str:
    rows = [
        {"metric": "Ending value", "value": format_money(summary.get("ending_value"))},
        {"metric": "TWRR", "value": format_percent(summary.get("twrr"))},
        {"metric": "TWRR CAGR", "value": format_percent(summary.get("twrr_cagr"))},
        {"metric": "IRR (money-weighted)", "value": format_percent(summary.get("irr"))},
        {"metric": "Volatility", "value": format_percent(summary.get("volatility"))},
        {"metric": "Sharpe", "value": format_number(summary.get("sharpe"))},
        {"metric": "Sortino", "value": format_number(summary.get("sortino"))},
        {"metric": "Calmar", "value": format_number(summary.get("calmar"))},
        {"metric": "Value at Risk (95%)", "value": format_percent(summary.get("var_95"))},
        {"metric": "Value at Risk (99%)", "value": format_percent(summary.get("var_99"))},
        {"metric": "Maximum drawdown", "value": format_percent(summary.get("max_drawdown"))},
        {"metric": "Benchmark excess return", "value": format_percent(summary.get("benchmark_excess_return"))},
        {"metric": "Total contributed", "value": format_money(summary.get("total_contributed"))},
        {"metric": "Total withdrawn", "value": format_money(summary.get("total_withdrawn"))},
        {"metric": "Total costs", "value": format_money(summary.get("total_costs"))},
    ]
    return rows_table(rows)


def drawdown_stress_section(summary: dict[str, Any]) -> str:
    ending_value = float(summary.get("ending_value") or 0)
    shocks = [
        ("-10% shock", -0.10),
        ("-20% shock", -0.20),
        ("-35% shock", -0.35),
        ("Repeat max drawdown", float(summary.get("max_drawdown") or 0)),
    ]
    rows = [
        {"scenario": label, "impact": format_percent(shock), "value_after_stress": format_money(ending_value * (1 + shock))}
        for label, shock in shocks
    ]
    return rows_table(rows)


def quality_section(quality_issues: list[dict[str, Any]]) -> str:
    if not quality_issues:
        return "No blocking data quality issues were recorded for this run."
    return rows_table(quality_issues)


def reproducibility_section(result: dict[str, Any]) -> str:
    run_id = result.get("run_id", "<run_id>")
    return (
        f"The selected summary metrics can be rechecked from `data/runs/{run_id}/request.json`, "
        f"`data/runs/{run_id}/result.json`, and the current cached SEC NAV files under `data/sec/normalized/`. "
        "This verification does not restore the original cache snapshot, dependency versions, engine version, or report output.\n\n"
        f"Verification command: `python3 scripts/sec_verify_run_reproducibility.py {run_id}`"
    )


def limitations_section() -> str:
    return (
        "This is historical portfolio backtesting from SEC mutual-fund NAV data. It is not a forecast, "
        "investment recommendation, tax model, personal suitability assessment, or broker execution simulator. "
        "Corporate actions and dividend effects are reflected only to the extent they are embedded in SEC fund NAV."
    )


def ensure_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [cast(dict[str, Any], row) for row in value if isinstance(row, dict)]


def rows_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No rows."
    columns = list(rows[0].keys())
    header = "| " + " | ".join(str(column) for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(escape_markdown(format_value(row.get(column))) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def flatten_manifest(manifest: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for key, value in manifest.items():
        next_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            rows.update(flatten_manifest(value, next_key))
        elif isinstance(value, list):
            rows[next_key] = len(value)
        else:
            rows[next_key] = value
    return rows


def cashflow_description(cashflow: dict[str, Any]) -> str:
    if not cashflow.get("enabled"):
        return "Disabled"
    return f"{cashflow.get('type')} {format_money(cashflow.get('amount'))} {cashflow.get('frequency')} {cashflow.get('timing')}"


def format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return format_number(value)
    return str(value)


def format_number(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):,.6f}".rstrip("0").rstrip(".")


def format_money(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):,.2f}"


def format_percent(value: Any, *, scale: int = 100) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * scale:.4f}%"


def escape_markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
