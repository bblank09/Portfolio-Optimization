from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Query

from backend.app.core.errors import AppHTTPException
from backend.app.data.quality import align_nav_panel, find_longest_complete_window
from backend.app.domain.enums import ErrorCode
from backend.app.domain.optimize_schemas import DataFrequency
from backend.app.sec.cache import load_nav_panel

router = APIRouter(prefix="/funds", tags=["funds"])
UNIVERSE_PATH = Path("data/sec/mvp_fund_universe.csv")


@router.get("")
def list_funds() -> dict:
    if not UNIVERSE_PATH.exists():
        raise AppHTTPException(
            status_code=503,
            detail="SEC fund universe cache is missing. Run scripts/sec_build_mvp_universe.py.",
            code=ErrorCode.FUND_UNIVERSE_CACHE_MISSING,
        )
    funds = pd.read_csv(UNIVERSE_PATH).fillna("")
    return {
        "data_source": "sec_open_data",
        "funds": funds.to_dict(orient="records"),
    }


@router.get("/testable-range")
def testable_range(
    proj_ids: str = Query(..., description="Comma-separated proj_ids"),
    frequency: DataFrequency = Query(DataFrequency.monthly, description="NAV alignment frequency"),  # noqa: B008
) -> dict:
    """The longest continuous date range where every given proj_id has a
    complete NAV observation at the requested frequency -- what the
    frontend's "Max" date range preset should actually use. A naive
    "latest nav_start .. earliest nav_end" intersection of each fund's own
    range can still contain a real gap (e.g. the 2024-06 to 2024-11 SEC-wide
    incident) that the optimizer would reject, so this uses the same
    align_nav_panel + completeness rules, not an approximation.
    """
    ids = [proj_id.strip() for proj_id in proj_ids.split(",") if proj_id.strip()]
    if not ids:
        return {"start": None, "end": None}
    panel = align_nav_panel(load_nav_panel(ids), frequency=frequency.value)
    if panel.empty or not set(ids).issubset(panel.columns):
        # A requested proj_id with zero cached NAV rows at all means no
        # window can ever satisfy "every given fund has data" -- same
        # empty result as any other unsatisfiable case, not a 500.
        return {"start": None, "end": None}
    completeness_freq = {"daily": "B", "weekly": "W-FRI", "monthly": "M"}[frequency.value]
    window = find_longest_complete_window(panel[ids], freq=completeness_freq)
    if window is None:
        return {"start": None, "end": None}
    return {"start": window[0], "end": window[1]}
