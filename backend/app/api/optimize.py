import json
import logging
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from slowapi.util import get_remote_address

from backend.app.core.errors import AppHTTPException
from backend.app.core.limiter import limiter
from backend.app.domain.enums import ErrorCode
from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.service import run_optimize

router = APIRouter(prefix="/optimize", tags=["optimize"])
RUNS_DIR = Path("data/runs")
logger = logging.getLogger("app.optimize")

# A second, independent rate limit specific to robustOptimization=true
# requests, on top of the route's existing blanket @limiter.limit
# ("10/minute", below). 500 bootstrap resamples measured at 6.7-7.4s
# wall-clock against the real NAV cache (Phase 5 sub-project 5's design
# spec/plan) -- several seconds per request, several times more expensive
# than a normal request, so it gets its own, stricter cap. In-process
# (not shared across workers) is acceptable for this project's
# single-process docker-compose deployment (see CLAUDE.md).
_ROBUST_OPTIMIZATION_RATE_LIMIT = 2
_ROBUST_OPTIMIZATION_RATE_WINDOW_SECONDS = 60
_robust_optimization_request_times: dict[str, list[float]] = defaultdict(list)


def _check_robust_optimization_rate_limit(client_key: str) -> None:
    now = time.monotonic()
    window_start = now - _ROBUST_OPTIMIZATION_RATE_WINDOW_SECONDS
    recent = [t for t in _robust_optimization_request_times[client_key] if t > window_start]
    if len(recent) >= _ROBUST_OPTIMIZATION_RATE_LIMIT:
        raise AppHTTPException(
            status_code=429,
            detail="Too many robust-optimization requests. Please wait before retrying.",
            code=ErrorCode.RATE_LIMITED,
        )
    recent.append(now)
    _robust_optimization_request_times[client_key] = recent


@router.post("")
@limiter.limit("10/minute")
def create_optimization(request: Request, optimize_request: OptimizeRequest) -> dict:
    proj_ids = [fund.proj_id for fund in optimize_request.funds]
    if optimize_request.robust_optimization:
        _check_robust_optimization_rate_limit(get_remote_address(request))
    started = time.monotonic()
    logger.info("optimize request: funds=%s goal=%s", proj_ids, optimize_request.goal.value)
    try:
        result = run_optimize(optimize_request)
    except FileNotFoundError as exc:
        # Same handling as the sibling /api/backtests route: a missing parquet
        # NAV cache is an operator problem, not a bad request.
        logger.exception("optimize request failed: NAV cache missing funds=%s", proj_ids)
        raise AppHTTPException(
            status_code=503,
            detail="SEC NAV cache is missing. Run scripts/sec_download_mvp.py.",
            code=ErrorCode.NAV_CACHE_MISSING,
        ) from exc
    except ValueError as exc:
        # inputs.py and solvers.py raise known ErrorCode names as messages.
        # An unknown ValueError is an implementation/solver failure, not
        # evidence of missing NAV history, so do not misclassify it as a 422.
        code_name = str(exc)
        code = getattr(ErrorCode, code_name, None)
        if code is None:
            logger.exception("optimize request raised an unknown ValueError: funds=%s", proj_ids)
            raise AppHTTPException(
                status_code=500,
                detail="Optimization failed unexpectedly.",
                code=ErrorCode.INTERNAL_ERROR,
            ) from exc
        raise AppHTTPException(status_code=422, detail=code_name.replace("_", " ").title(), code=code) from exc
    except RuntimeError as exc:
        code_name = str(exc)
        code = getattr(ErrorCode, code_name, None)
        if code is None:
            logger.exception("optimize request raised an unknown RuntimeError: funds=%s", proj_ids)
            raise AppHTTPException(
                status_code=500,
                detail="Optimization failed unexpectedly.",
                code=ErrorCode.INTERNAL_ERROR,
            ) from exc
        raise AppHTTPException(status_code=422, detail=code_name.replace("_", " ").title(), code=code) from exc
    except AppHTTPException:
        # Already a coded response (e.g. raised from deeper in run_optimize in
        # the future) — let it pass through instead of flattening it into a
        # generic 500 below.
        raise
    except Exception as exc:
        # riskfolio-lib's internals raise bare KeyError/NameError/IndexError
        # on unsupported parameter combinations. Translate anything unexpected
        # into a coded 500 rather than letting a raw exception escape.
        logger.exception("optimize request failed: funds=%s duration=%.3fs", proj_ids, time.monotonic() - started)
        raise AppHTTPException(
            status_code=500,
            detail="Optimization failed unexpectedly.",
            code=ErrorCode.INTERNAL_ERROR,
        ) from exc
    run_id = make_run_id()
    created_at = utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
    result_payload = result.model_dump(by_alias=True, mode="json")
    result_payload.update({
        "runId": run_id,
        "createdAt": created_at,
        "dataSource": "sec_open_data",
    })
    persist_run(run_id, optimize_request, result_payload)
    logger.info("optimize request succeeded: run_id=%s duration=%.3fs", run_id, time.monotonic() - started)
    return result_payload


@router.get("/{run_id}")
def get_optimization(run_id: str) -> dict[str, Any]:
    # run_id is used to build a filesystem path -- reject anything that could
    # escape RUNS_DIR (path separators, ".."), rather than trusting a value
    # that arrives from a public URL.
    if run_id != Path(run_id).name or run_id in ("", ".", ".."):
        raise AppHTTPException(status_code=404, detail=f"Optimization run not found: {run_id}", code=ErrorCode.RUN_NOT_FOUND)

    run_dir = RUNS_DIR / run_id
    result_path = run_dir / "result.json"
    if not result_path.is_file():
        raise AppHTTPException(status_code=404, detail=f"Optimization run not found: {run_id}", code=ErrorCode.RUN_NOT_FOUND)

    result = json.loads(result_path.read_text(encoding="utf-8"))
    request_path = run_dir / "request.json"
    if not request_path.is_file():
        logger.error("optimization run is missing its request.json: run_id=%s", run_id)
        raise AppHTTPException(
            status_code=500,
            detail="Optimization run is incomplete.",
            code=ErrorCode.INTERNAL_ERROR,
        )
    result["request"] = json.loads(request_path.read_text(encoding="utf-8"))
    return result


def make_run_id() -> str:
    # Share URLs are bearer links: anyone who has the URL can read the saved
    # result. Keep the human-readable timestamp, but retain the full UUID so
    # the unpredictable portion is 128 bits rather than an enumerable 32-bit
    # suffix.
    return f"run_{utc_now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(UTC)


def persist_run(run_id: str, request: OptimizeRequest, result: dict[str, Any]) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "request.json").write_text(
        json.dumps(request.model_dump(by_alias=True, mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
