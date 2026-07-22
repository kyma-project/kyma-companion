# syntax=docker/dockerfile:1

# Build stage: install dependencies on a Debian-12 glibc Python image whose
# interpreter and shared-library ABI match the distroless cc-debian12 runtime.
FROM python:3.13-slim-bookworm AS builder
WORKDIR /app

# Copy necessary files for dependency installation
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY docs_sources.json ./

# Install dependencies with Poetry and aggressively clean up. The venv is built
# with --copies so it carries a real python binary (not a symlink into
# /usr/local), which we relocate wholesale into the distroless runtime below.
RUN apt-get update && apt-get upgrade -y \
  && apt-get install -y --no-install-recommends build-essential gcc \
  && pip install --no-cache-dir "poetry>=2.1" \
  && poetry config virtualenvs.in-project true \
  && poetry config virtualenvs.options.always-copy true \
  && poetry install --only main --no-interaction --no-ansi \
  && pip uninstall -y poetry \
  && find /app/.venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
  && find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
  && find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
  && find /app/.venv -type f -name "*.pyc" -delete \
  && find /app/.venv -type f -name "*.pyo" -delete \
  && rm -rf /app/.venv/lib/python3.13/site-packages/pip* \
  && rm -rf /app/.venv/lib/python3.13/site-packages/setuptools* \
  && rm -rf /app/.venv/lib/python3.13/site-packages/wheel* \
  && find /app/.venv -name "*.so" -not -path "*.libs/*" -exec strip --strip-debug {} + 2>/dev/null || true

# Drop stdlib C-extensions the indexer never uses. Each removal orphans an OS
# shared library (sqlite3, ncurses, readline/tinfo, gdbm/db, bzip2, libuuid),
# so the ldd harvest below never pulls it into the runtime — eliminating the
# CVEs those libraries carry (e.g. sqlite CVE-2025-7458, ncurses CVE-2025-69720,
# the util-linux libuuid CVE cluster). The interpreter and every third-party
# dependency were verified to import without these. Kept: _ssl/_hashlib (TLS),
# _ctypes (cffi), zlib/binascii + _lzma (gzip/xz tarball handling). uuid still
# works via its pure-Python fallback once _uuid/libuuid are gone.
RUN set -eux; \
  DYNLOAD=/usr/local/lib/python3.13/lib-dynload; \
  for mod in _sqlite3 _tkinter _dbm _gdbm _curses _curses_panel readline _bz2 _uuid \
             _testcapi _testinternalcapi _testbuffer _testclinic _testclinic_limited \
             _testexternalinspection _testimportmultiple _testmultiphase _testsinglephase \
             _testlimitedcapi _ctypes_test _xxtestfuzz xxlimited xxlimited_35 xxsubtype; do \
    rm -f "$DYNLOAD"/${mod}.*.so; \
  done

# Stage the exact set of shared libraries the interpreter and its C-extensions
# need at runtime, so the distroless base (which ships only glibc + libstdc++)
# can load ssl, hashlib, ctypes, compression, etc. We resolve them via ldd over
# the interpreter and every remaining stdlib/site-package .so, then copy the
# real files into a self-contained sysroot preserving their absolute paths.
RUN set -eux; \
  mkdir -p /rootfs; \
  { \
    ldd /usr/local/bin/python3.13 || true; \
    find /usr/local/lib/python3.13/lib-dynload -name '*.so' -exec ldd {} \; 2>/dev/null || true; \
    find /app/.venv -name '*.so' -exec ldd {} \; 2>/dev/null || true; \
  } \
  | awk '/=>/ && $3 ~ /^\// {print $3} $1 ~ /^\/lib.*ld-linux/ {print $1}' \
  | sort -u \
  | grep -vE '^(/usr)?/lib/x86_64-linux-gnu/(libc|libm|libdl|libpthread|librt|libgcc_s|libstdc\+\+)\.so' \
  | while read -r lib; do \
      if [ -e "$lib" ]; then \
        mkdir -p "/rootfs$(dirname "$lib")"; \
        cp -aL "$lib" "/rootfs$lib"; \
      fi; \
    done

# Runtime stage: distroless C/C++ base (glibc + libstdc++, no shell, no apt,
# no perl/util-linux/coreutils). The :debug tag adds busybox so orchestrator
# manifests that invoke `sh -c "... && ..."` keep working unchanged.
FROM gcr.io/distroless/cc-debian12:debug
WORKDIR /app

# Python 3.13 interpreter, its standard library, and the shared C libraries its
# extensions link against — copied from the builder, no package manager needed.
COPY --from=builder /usr/local/bin/python3.13 /usr/local/bin/python3.13
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/lib/libpython3.13.so.1.0 /usr/local/lib/libpython3.13.so.1.0
COPY --from=builder /rootfs/ /

# CA certificates for HTTPS to GitHub (codeload), SAP AI Core, and HANA Cloud.
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

# Application virtual environment and code.
COPY --from=builder /app/.venv ./venv
COPY src ./src
COPY docs_sources.json ./

# Non-root numeric user (distroless has no useradd; uid matches the prior image).
USER 10001

ENV PATH="/app/venv/bin:/usr/local/bin:$PATH" \
    LD_LIBRARY_PATH="/usr/local/lib" \
    PYTHONDONTWRITEBYTECODE=1

# The task (fetch/index/drop/tables) is supplied by the Job/CronJob manifest,
# e.g. ["python", "src/main.py", "fetch"]. No ENTRYPOINT/CMD, matching the
# prior image's contract.
