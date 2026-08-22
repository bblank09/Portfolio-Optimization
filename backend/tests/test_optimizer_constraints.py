import numpy as np
import pandas as pd
import pytest

from backend.app.optimizer.constraints import (
    enforce_portfolio_constraints,
    turnover_pct,
)
from backend.tests.test_optimizer_inputs import _request


def _returns() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "A": [0.01, 0.04, -0.01, 0.03, 0.02],
            "B": [0.01, 0.01, 0.01, 0.01, 0.01],
        },
        index=pd.date_range("2020-01-31", periods=5, freq="ME"),
    )


def test_turnover_cap_is_enforced_by_adjusting_weights():
    request = _request(goal="min_variance")
    request.current_weight_pct = {"A": 100.0, "B": 0.0}
    request.constraints.max_turnover_pct = 10.0

    weights = enforce_portfolio_constraints(request, {"A": 0.0, "B": 100.0}, _returns())

    assert sum(weights.values()) == pytest.approx(100.0, abs=1e-4)
    assert turnover_pct(request, weights) <= 10.0 + 1e-4
    assert weights["A"] >= 89.9


def test_tracking_error_cap_is_enforced_against_benchmark_series():
    request = _request(goal="min_variance")
    request.benchmark_proj_id = "B"
    request.constraints.max_tracking_error_pct = 0.01
    returns = _returns()

    weights = enforce_portfolio_constraints(request, {"A": 100.0, "B": 0.0}, returns, returns["B"])

    active = returns["A"] * (weights["A"] / 100) + returns["B"] * (weights["B"] / 100) - returns["B"]
    tracking_error_pct = float(active.std(ddof=1) * np.sqrt(12) * 100)
    assert tracking_error_pct <= 0.01 + 1e-4


def test_infeasible_turnover_cap_returns_coded_error():
    request = _request(goal="min_variance")
    request.current_weight_pct = {"A": 0.0, "B": 0.0}
    request.constraints.max_turnover_pct = 1.0

    with pytest.raises(ValueError, match="INFEASIBLE_CONSTRAINTS"):
        enforce_portfolio_constraints(request, {"A": 50.0, "B": 50.0}, _returns())
