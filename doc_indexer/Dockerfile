# Build stage: install dependencies
FROM python:3.13-slim-bookworm AS builder
WORKDIR /app

# Copy necessary files for dependency installation
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY docs_sources.json ./

# Install dependencies with Poetry and aggressively clean up
RUN apt-get update && apt-get upgrade -y \
  && apt-get install -y --no-install-recommends build-essential gcc git \
  && python -m venv ./venv \
  && ./venv/bin/pip install --no-cache-dir poetry>=2.1 \
  && ./venv/bin/poetry config virtualenvs.in-project true \
  && ./venv/bin/poetry install --only main --no-interaction --no-ansi \
  && cd /app/.venv && ../venv/bin/pip uninstall -y poetry pip setuptools wheel \
  && find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
  && find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
  && find . -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
  && find . -type f -name "*.pyc" -delete \
  && find . -type f -name "*.pyo" -delete \
  && rm -rf ./lib/python3.13/site-packages/pip* \
  && rm -rf ./lib/python3.13/site-packages/setuptools* \
  && rm -rf ./lib/python3.13/site-packages/wheel* \
  && find . -name "*.so" -not -path "*.libs/*" -exec strip --strip-debug {} + 2>/dev/null || true

# Runtime stage: fresh slim image with only runtime files
FROM python:3.13-slim-bookworm
WORKDIR /app

# Install git (needed by the fetch task) and CA certificates for outbound HTTPS
RUN apt-get update && apt-get upgrade -y \
  && apt-get install -y --no-install-recommends git ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder (Poetry creates .venv with in-project)
COPY --from=builder /app/.venv ./venv

# Copy application code
COPY src ./src
COPY docs_sources.json ./

# Create non-root user, application directories, and set ownership
RUN useradd -u 10001 --create-home --shell /bin/bash appuser \
  && mkdir -p data \
  && chown -R appuser:appuser /app

# Set PATH to use venv
ENV PATH="/app/venv/bin:$PATH"

USER appuser
