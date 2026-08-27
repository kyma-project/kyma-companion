# syntax=docker/dockerfile:1

# Build stage: Debian sid (unstable) for compiling C-extensions (gcc, libffi-dev).
# Python 3.14 comes from Debian sid natively.
# Garden Linux 2150.9.0 only ships Python 3.13, and its minimal package set
# lacks the -dev headers needed to build C-extensions -- so we compile in
# Debian and copy only the finished venv into the Garden Linux runtime.
FROM debian:sid AS builder
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3.14 python3.14-dev python3-pip gcc libffi-dev libssl-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY config ./config

RUN python3.14 -m pip install --no-cache-dir --break-system-packages "poetry>=2.1" \
  && poetry config virtualenvs.in-project true \
  && poetry config virtualenvs.options.always-copy true \
  && poetry install --only main --no-interaction --no-ansi \
  && python3.14 -m pip uninstall -y --break-system-packages poetry \
  && rm -rf ~/.config/pypoetry ~/.cache/pypoetry \
  && find /app/.venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
  && find /app/.venv -type f -name "*.pyc" -delete \
  && find /app/.venv -type f -name "*.pyo" -delete \
  && rm -rf /app/.venv/lib/python3.*/site-packages/pip* \
  && rm -rf /app/.venv/lib/python3.*/site-packages/setuptools* \
  && rm -rf /app/.venv/lib/python3.*/site-packages/wheel* \
  && rm -f /app/.venv/bin/pip* /app/.venv/bin/wheel /app/.venv/bin/easy_install*

# Runtime stage: clean Garden Linux with Python 3.14 from Debian sid.
FROM ghcr.io/gardenlinux/gardenlinux:2150.9.0
RUN echo "deb https://deb.debian.org/debian sid main" > /etc/apt/sources.list.d/sid.list \
  && printf 'Package: *\nPin: release a=unstable\nPin-Priority: -1\n\nPackage: python3.14 python3.14-minimal libpython3.14 libpython3.14-minimal libpython3.14-stdlib libdb5.3t64 media-types\nPin: release a=unstable\nPin-Priority: 900\n' > /etc/apt/preferences.d/sid-pin \
  && apt-get update \
  && apt-get install -y --no-install-recommends python3.14 libstdc++6 \
  && rm -rf /var/lib/apt/lists/* /var/cache/apt /usr/share/doc /usr/share/man \
  && rm -f /usr/bin/perl /usr/bin/perl5* /usr/bin/bashbug \
  && rm -rf /usr/lib/aarch64-linux-gnu/perl-base /usr/lib/aarch64-linux-gnu/perl5 \
  && rm -f /bin/bash /usr/bin/bash \
  && rm -f /usr/bin/openssl /usr/bin/c_rehash \
  && rm -f /usr/bin/apt /usr/bin/apt-get /usr/bin/apt-cache /usr/bin/apt-mark \
     /usr/bin/apt-cdrom /usr/bin/apt-config /usr/bin/apt-sortpkgs /usr/bin/apt-extracttemplates

WORKDIR /app

COPY --from=builder /app/.venv ./venv
COPY src ./src
COPY config ./config

RUN groupadd --gid 5678 appuser \
  && useradd --uid 5678 --gid appuser --shell /bin/sh --no-create-home appuser \
  && chown -R appuser:appuser /app

USER appuser

ENV PATH="/app/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
CMD ["python3.14", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
