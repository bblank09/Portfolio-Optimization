import pytest
from pydantic import ValidationError

from backend.app.domain.optimize_schemas import OptimizeRequest, OptimizeResult

MINIMAL_REQUEST_JSON = {
    "funds": [
        {"projId": "M0209_2548", "displayName": "K-SET50"},
        {"projId": "M0155_2547", "displayName": "M-S50"},
    ],
    "fundBounds": {},
    "currentWeightPct": {},
    "fundGroups": {},
    "assetGroups": {
        letter: {"name": "", "minWeightPct": 0, "maxWeightPct": 100}
        for letter in "ABCDEF"
    },
    "timePeriod": {"startDate": "2020-01-31", "endDate": "2024-06-30"},
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
        "longOnly": True,
        "minWeightPct": 0,
        "maxWeightPct": 100,
        "groupConstraintsEnabled": False,
        "maxHoldings": 20,
        "lookbackPeriodMonths": 36,
        "optimizationFrequency": "quarterly",
        "riskFreeRatePct": 1.5,
        "compareAgainst": "equal_weighted",
        "maxTurnoverPct": None,
        "maxTrackingErrorPct": None,
    },
}


def test_minimal_request_parses_from_camel_case_json():
    request = OptimizeRequest.model_validate(MINIMAL_REQUEST_JSON)
    assert len(request.funds) == 2
    assert request.funds[0].proj_id == "M0209_2548"
    assert request.goal == "max_sharpe"


def test_round_trips_back_to_camel_case_json():
    request = OptimizeRequest.model_validate(MINIMAL_REQUEST_JSON)
    dumped = request.model_dump(by_alias=True, mode="json")
    assert "fundBounds" in dumped
    assert "fund_bounds" not in dumped


def test_fewer_than_two_funds_rejected():
    bad = {**MINIMAL_REQUEST_JSON, "funds": [MINIMAL_REQUEST_JSON["funds"][0]]}
    with pytest.raises(ValidationError):
        OptimizeRequest.model_validate(bad)


def test_duplicate_proj_id_rejected():
    bad = {**MINIMAL_REQUEST_JSON, "funds": [MINIMAL_REQUEST_JSON["funds"][0], MINIMAL_REQUEST_JSON["funds"][0]]}
    with pytest.raises(ValidationError):
        OptimizeRequest.model_validate(bad)


def test_black_litterman_goal_requires_black_litterman_inputs():
    bad = {**MINIMAL_REQUEST_JSON, "goal": "black_litterman", "blackLitterman": None}
    with pytest.raises(ValidationError):
        OptimizeRequest.model_validate(bad)


def _valid_optimize_result_payload() -> dict:
    """Return a minimal but structurally valid OptimizeResult payload in camelCase JSON format."""
    return {
        "feasibility": "optimal",
        "feasibilityMessage": None,
        "robustNote": None,
        "optimalWeights": {"M0209_2548": 0.5, "M0155_2547": 0.5},
        "compareWeights": None,
        "riskContributionPct": {"M0209_2548": 0.5, "M0155_2547": 0.5},
        "frontier": [],
        "assetSummary": [],
        "correlations": [],
        "performanceSummary": [],
        "rolling": [],
        "blackLitterman": None,
        "monthlyReturnsPct": [],
        "selectedRiskMeasure": {
            "measure": "std_dev",
            "label": "Volatility",
            "optimizedValue": 0.15,
            "comparedValue": None,
            "unit": "annual %",
        },
        "benchmarkComparison": None,
        "tradeList": [],
        "totalTurnoverPct": 0.0,
        "bindingConstraints": [],
        "optimalPoint": {
            "volatilityPct": 0.15,
            "expectedReturnPct": 0.08,
            "label": "optimal",
        },
        "gmvPoint": None,
        "tangencyPoint": None,
        "generatedAt": "2024-01-01T00:00:00",
    }


def test_optimize_result_accepts_compare_note():
    payload = _valid_optimize_result_payload()
    payload["compareNote"] = "max_sharpe comparison could not converge"
    payload["constraintNote"] = None
    payload["robustOptimizationNote"] = None
    result = OptimizeResult.model_validate(payload)
    assert result.compare_note == "max_sharpe comparison could not converge"

    payload["compareNote"] = None
    result = OptimizeResult.model_validate(payload)
    assert result.compare_note is None


def test_optimize_result_accepts_constraint_note():
    payload = _valid_optimize_result_payload()
    payload["compareNote"] = None
    payload["constraintNote"] = "Trimmed 2 fund(s) to satisfy the 3-holding cap."
    payload["robustOptimizationNote"] = None
    result = OptimizeResult.model_validate(payload)
    assert result.constraint_note == "Trimmed 2 fund(s) to satisfy the 3-holding cap."

    payload["constraintNote"] = None
    result = OptimizeResult.model_validate(payload)
    assert result.constraint_note is None


def test_optimize_result_accepts_robust_optimization_note():
    payload = _valid_optimize_result_payload()
    payload["compareNote"] = None
    payload["constraintNote"] = None
    payload["robustOptimizationNote"] = "Robust optimization: averaged 487 of 500 resamples."
    result = OptimizeResult.model_validate(payload)
    assert result.robust_optimization_note == "Robust optimization: averaged 487 of 500 resamples."

    payload["robustOptimizationNote"] = None
    result = OptimizeResult.model_validate(payload)
    assert result.robust_optimization_note is None


def test_rolling_window_mode_defaults_to_expanding():
    payload = MINIMAL_REQUEST_JSON
    request = OptimizeRequest.model_validate(payload)
    assert request.constraints.rolling_window_mode.value == "expanding"


def test_rolling_window_mode_accepts_trailing():
    payload = {**MINIMAL_REQUEST_JSON, "constraints": {**MINIMAL_REQUEST_JSON["constraints"], "rollingWindowMode": "trailing"}}
    request = OptimizeRequest.model_validate(payload)
    assert request.constraints.rolling_window_mode.value == "trailing"
