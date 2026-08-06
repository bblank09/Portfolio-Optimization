from backend.app.reports.markdown import render_research_report


def test_report_mentions_sec_open_data_and_limitations():
    report = render_research_report(
        request={"assets": [{"proj_id": "FUND_A", "weight": 100}]},
        result={"summary": {"ending_value": 1200, "twrr_cagr": 0.1, "max_drawdown": -0.2}},
        manifest={"source": "SEC Open Data", "nav_rows": 1000},
        quality_issues=[],
    )
    assert "SEC Open Data" in report
    assert "Formula Reference" in report
    assert "Limitations" in report
    assert "mock" not in report.lower()


def test_report_documents_current_reproducibility_command_and_scope():
    report = render_research_report(
        request={"assets": [{"proj_id": "FUND_A", "weight": 100}]},
        result={"run_id": "saved-run", "summary": {}},
        manifest={"source": "SEC Open Data"},
        quality_issues=[],
    )

    assert "python3 scripts/sec_verify_run_reproducibility.py saved-run" in report
    assert "does not restore the original cache snapshot" in report
    assert "resampled and aligned across the complete cache" in report
    assert "does not independently create or cap a partial month-end row" in report


def test_report_formula_reference_contains_real_equations():
    report = render_research_report(
        request={"assets": [{"proj_id": "FUND_A", "weight": 100}]},
        result={"summary": {"ending_value": 1200, "twrr_cagr": 0.1, "max_drawdown": -0.2}},
        manifest={"source": "SEC Open Data", "nav_rows": 1000},
        quality_issues=[],
    )
    expected_terms = [
        "simple_returns",
        "NAV_t / NAV_{t-1} - 1",
        "time_weighted_return",
        "product_{t=1..n}(1 + r_t) - 1",
        "annualized_return",
        "^(m / n) - 1",
        "annualized_volatility",
        "std(r_t, ddof=1) * sqrt(m)",
        "max_drawdown",
        "DD_t = V_t / max(V_0,...,V_t) - 1",
        "beta_alpha",
        "beta = cov(R_p, R_b) / var(R_b)",
        "alpha = R_p,ann - [R_f + beta * (R_b,ann - R_f)]",
    ]
    for term in expected_terms:
        assert term in report
