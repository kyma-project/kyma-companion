# Build stage: install dependencies
FROM ghcr.io/gardenlinux/gardenlinux:2150.0.0 AS builder
WORKDIR /app

# Copy only necessary files for dependency installation
COPY pyproject.toml poetry.lock ./

# Install Poetry and dependencies (removed dist-upgrade to save ~50-100MB)
RUN apt update && apt install -y build-essential gcc python3.13 python3.13-dev python3.13-venv \
  && python3.13 -m venv ./venv \
  && ./venv/bin/pip install --no-cache-dir poetry>=2.1 \
  && ./venv/bin/poetry config virtualenvs.create false \
  && ./venv/bin/poetry install --only main --no-interaction --no-ansi \
  && ./venv/bin/pip uninstall -y poetry \
  && find ./venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
  && find ./venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
  && find ./venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
  && find ./venv -type f -name "*.pyc" -delete \
  && find ./venv -type f -name "*.pyo" -delete

# Runtime stage: fresh GardenLinux with only runtime files
FROM ghcr.io/gardenlinux/gardenlinux:2150.0.0
WORKDIR /app

# Copy virtual environment from builder (includes Python!)
COPY --from=builder /app/venv ./venv

# Copy application code
COPY src ./src
COPY config ./config

# Create non-root user and set ownership
RUN groupadd -g 5678 appuser \
  && useradd -u 5678 -g appuser -s /bin/sh appuser \
  && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
CMD ["./venv/bin/python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
