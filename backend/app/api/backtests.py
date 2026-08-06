import json
import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from backend.app.core.errors import AppHTTPException
from backend.app.core.limiter import limiter
from backend.app.data.quality import align_nav_panel, validate_nav_panel
from backend.app.domain.enums import ErrorCode
from backend.app.domain.schemas import BacktestRequest
from backend.app.engine.backtest import run_backtest
from backend.app.reports.artifacts import write_research_report
from backend.app.sec.cache import load_nav_panel

router = APIRouter(prefix="/backtests", tags=["backtests"])
RUNS_DIR = Path("data/runs")
logger = logging.getLogger("app.backtests")


def min_complete_observations_for(frequency: str) -> int:
    """The `short_history` warning bar, in periods -- ~1 year regardless of grain."""
    return 252 if frequency == "daily" else 12


@router.post("")
@limiter.limit("10/minute")
def create_backtest(request: Request, backtest_request: BacktestRequest) -> dict[str, Any]:
    proj_ids = sorted({asset.proj_id for asset in backtest_request.assets} | {backtest_request.benchmark_proj_id})
    started = time.monotonic()
    logger.info(
        "backtest request: assets=%s benchmark=%s start=%s end=%s",
        proj_ids, backtest_request.benchmark_proj_id, backtest_request.start_date, backtest_request.end_date,
    )
    try:
        if backtest_request.data.source != "sec_open_data":
            raise AppHTTPException(
                status_code=400,
                detail="Production backtests only support SEC Open Data.",
                code=ErrorCode.UNSUPPORTED_DATA_SOURCE,
            )

        try:
            nav = align_nav_panel(load_nav_panel(proj_ids), frequency=backtest_request.data.frequency)
        except FileNotFoundError as exc:
            raise AppHTTPException(
                status_code=503,
                detail="SEC NAV cache is missing. Run scripts/sec_download_mvp.py.",
                code=ErrorCode.NAV_CACHE_MISSING,
            ) from exc

        selected_nav = nav.loc[pd.Timestamp(backtest_request.start_date) : pd.Timestamp(backtest_request.end_date), proj_ids]
        quality_issues = validate_nav_panel(
            selected_nav,
            as_of=pd.Timestamp(backtest_request.end_date),
            min_complete_observations=min_complete_observations_for(backtest_request.data.frequency),
        )
        try:
            result = run_backtest(backtest_request, nav)
        except ValueError as exc:
            raise AppHTTPException(
                status_code=422, detail=str(exc), code=ErrorCode.INSUFFICIENT_NAV_HISTORY
            ) from exc

        result["quality_issues"] = quality_issues
        result["run_id"] = make_run_id()
        result["created_at"] = utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
        result["data_source"] = "sec_open_data"
        persist_run(result["run_id"], backtest_request, result)
    except Exception:
        # Logged here (with the fund ids that caused it) in addition to
        # whatever the global exception handler does, because that handler
        # only sees the exception, not which request triggered it.
        logger.exception(
            "backtest request failed: assets=%s benchmark=%s duration=%.3fs",
            proj_ids, backtest_request.benchmark_proj_id, time.monotonic() - started,
        )
        raise

    logger.info(
        "backtest request succeeded: run_id=%s duration=%.3fs",
        result["run_id"], time.monotonic() - started,
    )
    return to_jsonable(result)


@router.get("/{run_id}")
def get_backtest(run_id: str) -> dict[str, Any]:
    # run_id is used to build a filesystem path -- reject anything that could
    # escape RUNS_DIR (path separators, ".."), rather than trusting a value
    # that arrives from a public URL query param.
    if run_id != Path(run_id).name or run_id in ("", ".", ".."):
        raise AppHTTPException(status_code=404, detail=f"Backtest run not found: {run_id}", code=ErrorCode.RUN_NOT_FOUND)

    run_dir = RUNS_DIR / run_id
    result_path = run_dir / "result.json"
    if not result_path.is_file():
        raise AppHTTPException(status_code=404, detail=f"Backtest run not found: {run_id}", code=ErrorCode.RUN_NOT_FOUND)

    result = json.loads(result_path.read_text(encoding="utf-8"))
    request_path = run_dir / "request.json"
    result["request"] = json.loads(request_path.read_text(encoding="utf-8")) if request_path.is_file() else None
    return result


@router.get("/{run_id}/report", response_class=PlainTextResponse)
def get_backtest_report(run_id: str) -> str:
    try:
        report_path = write_research_report(run_id)
    except FileNotFoundError as exc:
        raise AppHTTPException(
            status_code=404, detail=f"Backtest run not found: {run_id}", code=ErrorCode.RUN_NOT_FOUND
        ) from exc
    return report_path.read_text(encoding="utf-8")


def make_run_id() -> str:
    return f"run_{utc_now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"


def utc_now() -> datetime:
    return datetime.now(UTC)


def persist_run(run_id: str, request: BacktestRequest, result: dict[str, Any]) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "request.json").write_text(
        json.dumps(request.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(
        json.dumps(to_jsonable(result), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, "item"):
        return to_jsonable(value.item())
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return value
