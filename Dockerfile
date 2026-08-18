# syntax=docker/dockerfile:1

# Build stage: Alpine-based Python with build tools for compiling C-extensions.
# Alpine uses musl libc. Key runtime deps ship musl wheels: pydantic-core has
# musllinux wheels for x86_64 and aarch64; hdbcli only has musllinux_1_2_x86_64.
# This image must therefore be built for linux/amd64 (the production target).
FROM python:3.13-alpine AS builder
WORKDIR /app

# gcc + musl-dev + libffi-dev cover C-extension fallback builds (cryptography,
# aiohttp). git is excluded — not needed by the Companion at runtime.
RUN apk add --no-cache gcc musl-dev libffi-dev

COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY config ./config

# Install into a venv with --copies so the interpreter is a real binary (not a
# symlink), making the venv fully self-contained in the runtime stage.
RUN pip install --no-cache-dir "poetry>=2.1" \
  && poetry config virtualenvs.in-project true \
  && poetry config virtualenvs.options.always-copy true \
  && poetry install --only main --no-interaction --no-ansi \
  && pip uninstall -y poetry \
  && find /app/.venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
  && find /app/.venv -type f -name "*.pyc" -delete \
  && find /app/.venv -type f -name "*.pyo" -delete \
  && rm -rf /app/.venv/lib/python3.13/site-packages/pip* \
  && rm -rf /app/.venv/lib/python3.13/site-packages/setuptools* \
  && rm -rf /app/.venv/lib/python3.13/site-packages/wheel*

# Runtime stage: plain Alpine — no shell package manager baggage beyond the
# minimal Alpine base. Much smaller CVE surface than any Debian variant.
# libstdc++ is required by hdbcli (pyhdbcli.abi3.so links against it).
FROM python:3.13-alpine
RUN apk add --no-cache libstdc++ \
  && rm -rf /usr/local/lib/python3.13/site-packages/pip* \
  && rm -rf /usr/local/lib/python3.13/site-packages/setuptools* \
  && rm -rf /usr/local/lib/python3.13/site-packages/wheel* \
  && rm -rf /usr/local/lib/python3.13/ensurepip
WORKDIR /app

COPY --from=builder /app/.venv ./venv
COPY src ./src
COPY config ./config

# Non-root user matching the prior image's uid/gid.
RUN addgroup -g 5678 appuser \
  && adduser -u 5678 -G appuser -s /bin/sh -D appuser \
  && chown -R appuser:appuser /app

USER appuser

ENV PATH="/app/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
