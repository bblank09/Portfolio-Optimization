import pytest
from pydantic import ValidationError

from backend.app.domain.optimize_schemas import OptimizeRequest


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
