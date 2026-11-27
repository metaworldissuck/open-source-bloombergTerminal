# Stage 1: Build optimized React + TypeScript + Tailwind SPA
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production FastAPI + DuckDB + Polars + WebSocket Unified Runtime
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    OPENTERM_DATA_DIR=/app/data

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/backend/
COPY backend/app /app/backend/app
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "/app/backend[adapters]"

RUN mkdir -p /app/data/parquet

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -sf http://127.0.0.1:${PORT}/v1/health || exit 1

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
