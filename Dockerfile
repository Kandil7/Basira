# ── Build stage ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for document processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies only (no source yet for better caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# ── Production stage ───────────────────────────────────────────────────
FROM python:3.11-slim AS production

# Security: run as non-root
RUN groupadd -r basira && useradd -r -g basira -d /app -s /sbin/nologin basira

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only production source code
COPY src/ src/

# Set ownership
RUN chown -R basira:basira /app

USER basira

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Production command with multiple workers
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--loop", "uvloop", "--http", "httptools"]

# ── Development stage ──────────────────────────────────────────────────
FROM builder AS development

# Install dev dependencies
RUN pip install --no-cache-dir -e ".[dev]"

COPY src/ src/
COPY tests/ tests/

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
