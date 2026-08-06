import json
from pathlib import Path

from fastapi import APIRouter

from backend.app.core.errors import AppHTTPException
from backend.app.domain.enums import ErrorCode

router = APIRouter(prefix="/data-status", tags=["data-status"])
MANIFEST_PATH = Path("data/sec/normalized/sec_data_manifest.json")


@router.get("")
def get_data_status() -> dict:
    if not MANIFEST_PATH.exists():
        raise AppHTTPException(
            status_code=503,
            detail="SEC NAV cache manifest is missing. Run scripts/sec_download_mvp.py.",
            code=ErrorCode.NAV_CACHE_MISSING,
        )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        "data_source": "sec_open_data",
        "nav_as_of": manifest["end"],
        "nav_start": manifest["start"],
        "fund_count": manifest["fund_count"],
    }
