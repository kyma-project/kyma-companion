# syntax=docker/dockerfile:1

# Build stage: Alpine-based Python with build tools for compiling C-extensions.
# Alpine uses musl libc. Key runtime deps ship musl wheels: pydantic-core has
# musllinux wheels for both x86_64 and aarch64; hdbcli only has musllinux_1_2_x86_64.
# This image must therefore be built for linux/amd64 (the production target).
FROM python:3.13-alpine AS builder
WORKDIR /app

# Build tools needed only for C-extension wheels that lack a musl binary (none
# currently, but gcc/musl-dev cover the fallback path). git is excluded
# intentionally — fetcher uses tarball download instead.
RUN apk add --no-cache gcc musl-dev libffi-dev

COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY docs_sources.json ./

# Install into a venv with --copies so the interpreter is a real binary (not a
# symlink), making the venv self-contained in the runtime stage.
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

# Pre-create writable working dirs owned by the non-root uid.
# gid 0 + group-write follows the OpenShift arbitrary-uid idiom so the runtime
# user (10001) can write regardless of the uid assigned by the orchestrator.
RUN install -d -o 10001 -g 0 -m 0775 /writable/data /writable/tmp

# Runtime stage: plain Alpine — no shell package manager baggage beyond the
# minimal Alpine base. Much smaller CVE surface than any Debian variant.
# libstdc++ is required by hdbcli (pyhdbcli.abi3.so links against it).
FROM python:3.13-alpine
RUN apk add --no-cache libstdc++
WORKDIR /app

# CA certificates for HTTPS to GitHub (codeload), SAP AI Core, and HANA Cloud.
# Already present in the Alpine base image at this path; the COPY is a no-op
# safety net in case the base ever changes.
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

# Application virtual environment and source code.
COPY --from=builder /app/.venv ./venv
COPY src ./src
COPY docs_sources.json ./

# Writable working dirs, group-owned by gid 0 with group write (see builder note).
COPY --from=builder --chown=10001:0 /writable/data ./data
COPY --from=builder --chown=10001:0 /writable/tmp ./tmp

# Non-root numeric user (matches the prior image's uid).
USER 10001

ENV PATH="/app/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1

# The task (fetch/index/drop/tables) is supplied by the Job/CronJob manifest,
# e.g. ["python", "src/main.py", "fetch"]. No ENTRYPOINT/CMD, matching the
# prior image's contract.
