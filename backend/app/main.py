import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.app.api.backtests import router as backtests_router
from backend.app.api.data_status import router as data_status_router
from backend.app.api.funds import router as funds_router
from backend.app.core.config import settings
from backend.app.core.errors import AppHTTPException, app_http_exception_handler
from backend.app.core.limiter import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")

app = FastAPI(title="SEC Open Data Portfolio Backtester", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Starlette's own default for an uncaught exception returns a plain-text
    # body, not JSON -- any client code (including our own frontend) that
    # calls response.json() on an error would itself crash trying to parse it.
    # Log the real exception server-side; never let its message or type reach
    # the client (it could reveal internal file paths, stack frames, or data).
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "code": "INTERNAL_ERROR"})


app.add_exception_handler(AppHTTPException, app_http_exception_handler)
_allowed_origins = settings.allowed_origins_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    # Credentials + wildcard origin is invalid per the CORS spec (browsers
    # reject it); this API has no cookies/sessions anyway, so only allow
    # credentials when the deployer has configured specific origins.
    allow_credentials=_allowed_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(funds_router, prefix="/api/v1")
app.include_router(backtests_router, prefix="/api/v1")
app.include_router(data_status_router, prefix="/api/v1")
# Unversioned alias kept during the migration window -- the current frontend
# (and every existing client) still calls these paths directly. Drop this
# once all clients are confirmed to be on /api/v1.
app.include_router(funds_router, prefix="/api")
app.include_router(backtests_router, prefix="/api")
app.include_router(data_status_router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_source": "sec_open_data"}


# Production convenience: when a built frontend is present (Docker image, or
# `npm run build` run locally), serve it from the same FastAPI process/port so
# there is nothing extra to host or CORS-configure. In dev, the frontend runs
# under its own Vite server instead and frontend/dist never exists, so none of
# this registers -- `npm run dev` is completely unaffected.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
