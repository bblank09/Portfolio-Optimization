# syntax=docker/dockerfile:1

# ---- frontend build stage ----
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- backend runtime ----
FROM python:3.12-slim AS runtime
WORKDIR /app

# pandas/scipy/pyarrow need a C toolchain to build if a wheel is missing for
# the target platform; keep it lean but present.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY backend/ ./backend/
RUN pip install --no-cache-dir .

# The SEC NAV cache and persisted run artifacts live under data/ -- ship
# whatever is baked into the image (e.g. a pre-downloaded cache) but expect
# a volume mount over this path in production so it survives redeploys.
COPY data/ ./data/

COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8000
ENV PORT=8000

# No curl in the slim base image -- Python is already there via the app
# itself, so use it instead of adding another package just for this check.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8000\")}/api/health', timeout=3)" || exit 1

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
