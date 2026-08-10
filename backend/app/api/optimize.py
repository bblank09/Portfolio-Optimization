import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Request
from slowapi.util import get_remote_address

from backend.app.core.errors import AppHTTPException
from backend.app.core.limiter import limiter
from backend.app.domain.enums import ErrorCode
from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.service import run_optimize

router = APIRouter(prefix="/optimize", tags=["optimize"])
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
        # inputs.py and solvers.py both raise the bare ErrorCode name as the
        # message, so this lookup resolves exactly. INSUFFICIENT_NAV_HISTORY
        # stays the fallback: ValueErrors on this path all originate from
        # input/NAV validation.
        code_name = str(exc)
        code = getattr(ErrorCode, code_name, ErrorCode.INSUFFICIENT_NAV_HISTORY)
        raise AppHTTPException(status_code=422, detail=code_name.replace("_", " ").title(), code=code) from exc
    except RuntimeError as exc:
        code_name = str(exc)
        code = getattr(ErrorCode, code_name, ErrorCode.INTERNAL_ERROR)
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
    logger.info("optimize request succeeded: duration=%.3fs", time.monotonic() - started)
    return result.model_dump(by_alias=True, mode="json")
