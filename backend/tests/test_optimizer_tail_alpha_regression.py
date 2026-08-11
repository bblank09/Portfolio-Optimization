"""Regression tests for the CVaR/CDaR tail-confidence wiring.

Found by the Phase 4 manual-verification pass (docs/manual-verification-2026-08-11.md,
Finding A): ``solvers._build_portfolio`` never set ``port.alpha``, so every
CVaR/CDaR *solve* silently ran at riskfolio-lib's own constructor default
(``self.alpha = 0.05``, i.e. a 95% tail) no matter what ``request.tailConfidence``
said.  Only the POST-solve reporting (``realized_risk`` /
``risk_contribution_pct``, which pass ``_tail_alpha(request)`` explicitly)
honored the requested confidence, so a 99% CVaR request got 99%-labelled
reporting on top of a 95%-solved portfolio.

The bug is invisible at ``tailConfidence == 95`` (which coincides with the
accidental default) and silently wrong at 97.5% / 99% -- both offered in the UI.
"""

import numpy as np
import pandas as pd
import pytest

from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.solvers import solve_mean_variance


def _request(risk_measure: str, tail_confidence: float) -> OptimizeRequest:
    return OptimizeRequest.model_validate({
        "funds": [{"projId": "A", "displayName": "A"}, {"projId": "B", "displayName": "B"}],
        "fundBounds": {}, "currentWeightPct": {}, "fundGroups": {},
        "assetGroups": {L: {"name": "", "minWeightPct": 0, "maxWeightPct": 100} for L in "ABCDEF"},
        "timePeriod": {"startDate": "2015-01-31", "endDate": "2024-12-31"},
        "dataFrequency": "monthly", "goal": "min_volatility", "riskMeasure": risk_measure,
        "tailConfidence": tail_confidence, "targetAnnualVolatilityPct": None,
        "targetAnnualReturnPct": None,
        "robustOptimization": False, "useHistoricalReturns": True,
        "useHistoricalVolatility": True, "useHistoricalCorrelations": True,
        "expectedReturnOverrides": {}, "volatilityOverrides": {}, "correlationOverrides": {},
        "returnMethod": "historical_mean", "covarianceMethod": "sample", "blackLitterman": None,
        "benchmarkProjId": None,
        "constraints": {
            "longOnly": True, "minWeightPct": 0, "maxWeightPct": 100,
            "groupConstraintsEnabled": False, "maxHoldings": 20,
            "lookbackPeriodMonths": 12, "optimizationFrequency": "quarterly",
            "riskFreeRatePct": 1.5, "compareAgainst": "none",
            "maxTurnoverPct": None, "maxTrackingErrorPct": None,
        },
    })


def _tail_asymmetric_returns() -> pd.DataFrame:
    """Two assets whose tail ranking deliberately FLIPS between 5% and 1%.

    Same body distribution for both.  ``A`` gets two catastrophic months, deep
    enough to sit inside the worst 1% of 240 observations.  ``B`` gets twelve
    moderately bad months -- inside the worst 5%, but never inside the worst 1%.

    So at a 95% tail (alpha = 0.05) B is the riskier asset (its twelve bad
    months fill the averaged tail), while at a 99% tail (alpha = 0.01) only A's
    two catastrophes survive the cut and A becomes the riskier one.  A solver
    that actually honors ``alpha`` must therefore return substantially
    DIFFERENT portfolios for the two confidences; one that ignores it returns
    identical weights.
    """
    n = 240
    dates = pd.date_range("2005-01-31", periods=n, freq="ME")
    rng = np.random.default_rng(11)
    a = rng.normal(0.004, 0.010, size=n)
    b = rng.normal(0.004, 0.010, size=n)
    a[10] = -0.40
    a[150] = -0.38
    for idx in range(5, n, 20):
        b[idx] = -0.09
    return pd.DataFrame({"A": a, "B": b}, index=dates)


def _solve(risk_measure: str, tail_confidence: float) -> dict[str, float]:
    request = _request(risk_measure, tail_confidence)
    returns = _tail_asymmetric_returns()
    mu = returns.mean() * 100 * 12
    sigma = (returns * 100).cov() * 12
    return solve_mean_variance(request, mu, sigma, returns)


def test_cvar_solve_honors_tail_confidence():
    """A 99% CVaR solve must not return the same portfolio as a 95% CVaR solve.

    Before the fix both calls produced byte-identical weights because
    ``port.alpha`` was never assigned and riskfolio-lib's 0.05 default was used
    for both.
    """
    at_95 = _solve("cvar", 95)
    at_99 = _solve("cvar", 99)
    assert abs(at_99["B"] - at_95["B"]) > 1.0, (
        f"CVaR weights identical across tail confidences -- alpha is not wired "
        f"into the solve: 95% -> {at_95}, 99% -> {at_99}"
    )
    # Direction check, per the fixture's construction: at the 1% tail only A's
    # two catastrophes count, so the 99% portfolio must hold MORE of B than the
    # 95% one (whose tail is dominated by B's twelve moderately bad months).
    assert at_99["B"] > at_95["B"] + 25.0


def test_cdar_solve_honors_tail_confidence():
    at_95 = _solve("cdar", 95)
    at_99 = _solve("cdar", 99)
    assert abs(at_99["B"] - at_95["B"]) > 1.0, (
        f"CDaR weights identical across tail confidences -- alpha is not wired "
        f"into the solve: 95% -> {at_95}, 99% -> {at_99}"
    )


# Captured by running _solve("cvar", 95) against the UNFIXED solvers.py.
PRE_FIX_CVAR_95 = {"A": 79.29521800642769, "B": 20.704781993572308}


def test_default_tail_confidence_is_unchanged_by_the_alpha_wiring():
    """Regression guard for the DEFAULT case.

    ``tailConfidence = 95`` maps to ``alpha = 0.05``, which is exactly the
    riskfolio-lib default the solver was accidentally using before the fix, so
    wiring ``port.alpha`` must leave the 95% solve bit-for-bit where it was.
    The pre-fix 95% CVaR solution is pinned here as literal numbers captured
    from the unfixed code.
    """
    at_95 = _solve("cvar", 95)
    assert at_95["A"] == pytest.approx(PRE_FIX_CVAR_95["A"], abs=1e-6)
    assert at_95["B"] == pytest.approx(PRE_FIX_CVAR_95["B"], abs=1e-6)
