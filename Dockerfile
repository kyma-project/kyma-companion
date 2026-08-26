# Build stage: install dependencies
FROM ghcr.io/gardenlinux/gardenlinux:2150.9.0 AS builder
WORKDIR /app

# Copy necessary files for dependency installation
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY config ./config

# Install dependencies with Poetry and aggressively clean up.
# Also create the non-root user here — bare-python has no shell or useradd.
RUN apt-get update && apt-get upgrade -y \
  && apt-get install -y --no-install-recommends build-essential gcc python3.13 python3.13-dev python3.13-venv \
  && python3.13 -m venv ./venv \
  && ./venv/bin/pip install --no-cache-dir "poetry>=2.1" \
  && ./venv/bin/poetry config virtualenvs.in-project true \
  && ./venv/bin/poetry config virtualenvs.options.always-copy true \
  && ./venv/bin/poetry install --only main --no-interaction --no-ansi \
  && cd /app/.venv && ../venv/bin/pip uninstall -y poetry pip setuptools wheel \
  && find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
  && find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
  && find . -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
  && find . -type f -name "*.pyc" -delete \
  && find . -type f -name "*.pyo" -delete \
  && rm -rf ./lib/python3.*/site-packages/pip* \
  && rm -rf ./lib/python3.*/site-packages/setuptools* \
  && rm -rf ./lib/python3.*/site-packages/wheel* \
  && rm -f ./bin/pip* ./bin/wheel ./bin/easy_install* \
  && find . -name "*.so" -exec strip --strip-debug {} + 2>/dev/null || true \
  && groupadd -g 5678 appuser \
  && useradd -u 5678 -g appuser -s /bin/sh appuser

# Runtime stage: bare-python contains only the Python interpreter and its
# dynamically linked .so chain — no shell utilities or apt packages that
# generate CVE findings. No RUN is possible here; user is created in builder.
FROM ghcr.io/gardenlinux/gardenlinux/bare-python:2150.9.0
WORKDIR /app

# Bring passwd/group from builder so the runtime image knows about appuser.
COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group

# bare-python only includes Python's own ldd chain. C-extension packages
# (pydantic-core, hdbcli, cryptography) also need libgcc_s and libstdc++.
# libdl/libpthread/librt are glibc stubs required by some .so files.
COPY --from=builder /usr/lib/aarch64-linux-gnu/libgcc_s.so.1 /usr/lib/aarch64-linux-gnu/libgcc_s.so.1
COPY --from=builder /usr/lib/aarch64-linux-gnu/libstdc++.so.6 /usr/lib/aarch64-linux-gnu/libstdc++.so.6
COPY --from=builder /usr/lib/aarch64-linux-gnu/libdl.so.2 /usr/lib/aarch64-linux-gnu/libdl.so.2
COPY --from=builder /usr/lib/aarch64-linux-gnu/libpthread.so.0 /usr/lib/aarch64-linux-gnu/libpthread.so.0
COPY --from=builder /usr/lib/aarch64-linux-gnu/librt.so.1 /usr/lib/aarch64-linux-gnu/librt.so.1

# Copy virtual environment and application code with correct ownership.
COPY --from=builder --chown=5678:5678 /app/.venv ./venv
COPY --chown=5678:5678 src ./src
COPY --chown=5678:5678 config ./config

USER 5678

ENV PATH="/app/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
