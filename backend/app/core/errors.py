from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from backend.app.domain.enums import ErrorCode


class AppHTTPException(HTTPException):
    """HTTPException that carries a stable `code` alongside the existing
    human-readable `detail`, so responses stay backward-compatible with any
    client that only reads `detail` (e.g. the current frontend)."""

    def __init__(self, status_code: int, detail: str, code: ErrorCode) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


async def app_http_exception_handler(request: Request, exc: AppHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code.value})
