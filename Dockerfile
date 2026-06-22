# ── Stage 1: Build React frontend ────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python / FastAPI runtime ────────────────────────
FROM python:3.11-slim

WORKDIR /app

# curl is needed for the HEALTHCHECK below
RUN apt-get update -qq && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy built React assets into the static folder FastAPI serves
COPY --from=frontend-builder /frontend/dist/ ./static/

EXPOSE 8000

# Gunicorn manages the single uvicorn worker so it auto-restarts on crash.
# NOTE: --workers 1 is intentional — active_sessions is in-process memory.
# To scale beyond 1 worker you must move sessions to Redis or a DB store.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "1", "-b", "0.0.0.0:8000", "--timeout", "120", "--graceful-timeout", "30", "--access-logfile", "-"]
