import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.inputs import build_mu_sigma


def _request(**overrides) -> OptimizeRequest:
    base = {
        "funds": [
            {"projId": "A", "displayName": "Fund A"},
            {"projId": "B", "displayName": "Fund B"},
        ],
        "fundBounds": {},
        "currentWeightPct": {},
        "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2020-01-31", "endDate": "2020-06-30"},
        "dataFrequency": "monthly",
        "goal": "max_sharpe",
        "riskMeasure": "std_dev",
        "tailConfidence": 95,
        "targetAnnualVolatilityPct": None,
        "targetAnnualReturnPct": None,
        "robustOptimization": False,
        "useHistoricalReturns": True,
        "useHistoricalVolatility": True,
        "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {},
        "volatilityOverrides": {},
        "correlationOverrides": {},
        "returnMethod": "historical_mean",
        "covarianceMethod": "sample",
        "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": 20,
            "lookbackPeriodMonths": 6, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    }
    base.update(overrides)
    return OptimizeRequest.model_validate(base)


def _fake_returns_panel() -> pd.DataFrame:
    dates = pd.date_range("2020-01-31", periods=6, freq="ME")
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {"A": rng.normal(0.01, 0.03, size=6), "B": rng.normal(0.008, 0.02, size=6)},
        index=dates,
    )


def test_sample_covariance_is_symmetric_positive_semidefinite():
    request = _request()
    returns = _fake_returns_panel()
    mu, sigma = build_mu_sigma(request, returns)
    assert list(mu.index) == ["A", "B"]
    assert sigma.shape == (2, 2)
    np.testing.assert_allclose(sigma.values, sigma.values.T)
    eigenvalues = np.linalg.eigvalsh(sigma.values)
    assert (eigenvalues >= -1e-10).all()


def test_expected_return_override_replaces_historical_mean():
    request = _request(useHistoricalReturns=False, expectedReturnOverrides={"A": 15.0})
    returns = _fake_returns_panel()
    mu, _ = build_mu_sigma(request, returns)
    assert mu["A"] == pytest.approx(15.0)


def test_indefinite_correlation_overrides_raise():
    request = _request(
        useHistoricalCorrelations=False,
        correlationOverrides={"A|B": 0.99},  # fine alone, but combine with...
    )
    # A 3-asset impossible triangle: A-B=0.9, A-C=0.9, B-C=-0.9 is the
    # textbook non-PSD example. Reuse the 2-asset request's structure but
    # add a third fund so the impossible triangle is expressible.
    request.funds.append(type(request.funds[0])(projId="C", displayName="Fund C"))
    request.correlation_overrides = {"A|B": 0.9, "A|C": 0.9, "B|C": -0.9}
    returns = _fake_returns_panel()
    returns["C"] = returns["A"] * 0.5 + 0.001
    with pytest.raises(ValueError, match="INDEFINITE_CORRELATION_MATRIX"):
        build_mu_sigma(request, returns)


def _nav_frame(values_a: list[float], values_b: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2020-01-31", periods=len(values_a), freq="ME")
    return pd.DataFrame({"A": values_a, "B": values_b}, index=dates)


def test_mid_window_nav_gap_is_a_hard_error(monkeypatch):
    """CLAUDE.md landmine: a gap in the requested range is a hard error --
    never forward-filled, never interpolated. The old check only rejected a
    fund that was ENTIRELY NaN in the window, so a partial (mid-window) gap
    silently survived into the covariance estimate: align_nav_panel does not
    drop partial-NaN rows and pct_change().dropna(how="all") keeps rows that
    are only partly NaN."""
    from backend.app.optimizer import inputs as inputs_module

    panel = _nav_frame([10.0, 10.5, np.nan, 11.2, 11.5, 11.9], [20.0, 20.4, 20.9, 21.1, 21.6, 22.0])
    monkeypatch.setattr(inputs_module, "load_nav_panel", lambda proj_ids: panel)
    monkeypatch.setattr(inputs_module, "align_nav_panel", lambda nav, frequency: nav)

    with pytest.raises(ValueError, match="INSUFFICIENT_NAV_HISTORY"):
        inputs_module.build_returns_panel(_request())


def test_complete_window_builds_returns(monkeypatch):
    """The gap check must not reject a genuinely complete panel."""
    from backend.app.optimizer import inputs as inputs_module

    panel = _nav_frame([10.0, 10.5, 10.8, 11.2, 11.5, 11.9], [20.0, 20.4, 20.9, 21.1, 21.6, 22.0])
    monkeypatch.setattr(inputs_module, "load_nav_panel", lambda proj_ids: panel)
    monkeypatch.setattr(inputs_module, "align_nav_panel", lambda nav, frequency: nav)

    returns = inputs_module.build_returns_panel(_request())
    assert list(returns.columns) == ["A", "B"]
    assert len(returns) == 5
    assert not returns.isna().to_numpy().any()


def test_raise_convention_uses_bare_error_code_name(monkeypatch):
    """The API route resolves the error code via getattr(ErrorCode, str(exc)),
    so the message must BE the code name -- previously it was a human
    sentence that only reached the right code by falling through to the
    default."""
    from backend.app.domain.enums import ErrorCode
    from backend.app.optimizer import inputs as inputs_module

    panel = _nav_frame([10.0, np.nan, np.nan, np.nan, np.nan, np.nan], [20.0, 20.4, 20.9, 21.1, 21.6, 22.0])
    monkeypatch.setattr(inputs_module, "load_nav_panel", lambda proj_ids: panel)
    monkeypatch.setattr(inputs_module, "align_nav_panel", lambda nav, frequency: nav)

    with pytest.raises(ValueError) as excinfo:
        inputs_module.build_returns_panel(_request())
    assert getattr(ErrorCode, str(excinfo.value), None) is ErrorCode.INSUFFICIENT_NAV_HISTORY
