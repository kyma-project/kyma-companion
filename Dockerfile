# Build stage: install dependencies
FROM ghcr.io/gardenlinux/gardenlinux:2150.1.0 AS builder
WORKDIR /app

# Copy necessary files for dependency installation
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY config ./config

# Install dependencies with Poetry and aggressively clean up
RUN apt update && apt install -y --no-install-recommends build-essential gcc python3.13 python3.13-dev python3.13-venv \
  && python3.13 -m venv ./venv \
  && ./venv/bin/pip install --no-cache-dir poetry>=2.1 \
  && ./venv/bin/poetry config virtualenvs.in-project true \
  && ./venv/bin/poetry install --only main --no-interaction --no-ansi \
  && cd /.venv && ../venv/bin/pip uninstall -y poetry pip setuptools wheel \
  && find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
  && find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
  && find . -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
  && find . -type f -name "*.pyc" -delete \
  && find . -type f -name "*.pyo" -delete \
  && rm -rf ./lib/python3.13/site-packages/pip* \
  && rm -rf ./lib/python3.13/site-packages/setuptools* \
  && rm -rf ./lib/python3.13/site-packages/wheel* \
  && find . -name "*.so" -exec strip --strip-debug {} + 2>/dev/null || true

# Runtime stage: fresh GardenLinux with only runtime files
FROM ghcr.io/gardenlinux/gardenlinux:2150.1.0
WORKDIR /app

# Install Python runtime (needed for venv symlinks)
RUN apt update && apt install -y --no-install-recommends python3.13 \
  && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder (Poetry creates .venv with in-project)
COPY --from=builder /app/.venv ./venv

# Copy application code
COPY src ./src
COPY config ./config

# Create non-root user and set ownership
RUN groupadd -g 5678 appuser \
  && useradd -u 5678 -g appuser -s /bin/sh appuser \
  && chown -R appuser:appuser /app

USER appuser

# Set PYTHONPATH so Python can find src modules
ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["./venv/bin/python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
