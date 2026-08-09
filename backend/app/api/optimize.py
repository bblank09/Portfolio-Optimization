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
    except ValueError as exc:
        code_name = str(exc)
        code = getattr(ErrorCode, code_name, ErrorCode.INSUFFICIENT_NAV_HISTORY)
        raise AppHTTPException(status_code=422, detail=code_name.replace("_", " ").title(), code=code) from exc
    except RuntimeError as exc:
        code_name = str(exc)
        code = getattr(ErrorCode, code_name, ErrorCode.INTERNAL_ERROR)
        raise AppHTTPException(status_code=422, detail=code_name.replace("_", " ").title(), code=code) from exc
    except Exception:
        logger.exception("optimize request failed: funds=%s duration=%.3fs", proj_ids, time.monotonic() - started)
        raise
    logger.info("optimize request succeeded: duration=%.3fs", time.monotonic() - started)
    return result.model_dump(by_alias=True, mode="json")
