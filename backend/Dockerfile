# ── Multi-stage Dockerfile (Easypanel convention) ─────────────────────────
# Stage 1: Builder — install dependencies
# Stage 2: Runtime — minimal Python with only what's needed to run

# ── Builder stage ─────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency declaration and install into a virtual environment
COPY pyproject.toml ./
RUN python -m venv /venv && \
    /venv/bin/pip install --no-cache-dir .

# ── Runtime stage ─────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"

# Copy application code
COPY app/ ./app/

# Expose the application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
