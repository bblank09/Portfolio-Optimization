import logging
import time

from fastapi import APIRouter, Request

from backend.app.core.errors import AppHTTPException
from backend.app.core.limiter import limiter
from backend.app.domain.enums import ErrorCode
from backend.app.domain.optimize_schemas import OptimizeRequest
from backend.app.optimizer.service import run_optimize

router = APIRouter(prefix="/optimize", tags=["optimize"])
logger = logging.getLogger("app.optimize")


@router.post("")
@limiter.limit("10/minute")
def create_optimization(request: Request, optimize_request: OptimizeRequest) -> dict:
    proj_ids = [fund.proj_id for fund in optimize_request.funds]
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
