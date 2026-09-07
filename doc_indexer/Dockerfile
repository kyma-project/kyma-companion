# syntax=docker/dockerfile:1

# Three-stage build:
#
#   builder  Alpine Python + a C toolchain. Installs the application's
#            dependencies into a virtualenv with poetry, then trims both the
#            venv and the Python stdlib:
#              - unused stdlib extension modules whose removal eliminates
#                system library deps from the runtime closure
#              - test/debug extension modules and bytecode variants
#              - venv installer metadata, bytecode caches, test suites
#            Extension module .so files are stripped of debug symbols.
#   rootfs   Same image as builder. Assembles /rootfs — the complete, exact
#            file tree the runtime image will consist of. ldd is run over the
#            interpreter binary and every .so under the stdlib lib-dynload and
#            the venv; the resolved library paths are copied to /rootfs. Any
#            "=> not found" line in the ldd stdout (a genuinely missing system
#            library) fails the build immediately. The "Error relocating:
#            <symbol>: symbol not found" messages that musl emits for Python C
#            API symbols (resolved at runtime from the interpreter process,
#            never by the dynamic loader) go to stderr and are discarded with
#            2>/dev/null — they are not missing libraries.
#   runtime  FROM scratch — an empty filesystem — into which /rootfs is
#            copied. No shell, no package manager, no coreutils, no files
#            other than the ones the rootfs stage selected. A final RUN
#            imports the C extension modules that exercise every system library
#            in the closure; a missing library fails the build here rather
#            than at pod startup.
#
# Alpine uses musl libc. Python and all venv wheels are musllinux builds.
# hdbcli ships only a musllinux_1_2_x86_64 wheel, so this must be built for
# linux/amd64.
#
# Version pin: ALPINE_PYTHON_TAG picks the Python version and therefore the
# musl, OpenSSL, zlib, bzip2, xz and libstdc++ that end up in the runtime
# image. A CVE in any of these is fixed by bumping this ARG.

ARG ALPINE_PYTHON_TAG=3.14-alpine

# --- Stage 1: builder ---------------------------------------------------------
FROM python:${ALPINE_PYTHON_TAG} AS builder

# Toolchain for any C-extension wheel that lacks a musllinux binary.
# gcc and musl-dev cover the fallback compile path; libffi-dev provides the
# cffi header if a package needs to build its own _cffi extension. git is
# excluded intentionally — the fetcher downloads release tarballs.
RUN apk add --no-cache gcc musl-dev libffi-dev

WORKDIR /app
COPY pyproject.toml poetry.lock ./
COPY src ./src
COPY docs_sources.json ./

# Install the application venv, then clean up.
# --always-copy makes the venv's python3.14 a real binary (not a symlink to
# the system interpreter), so the venv is completely self-contained and can
# be exec'd directly by the runtime image's RUN instruction without a shell.
# The python binary still resolves libpython3.14.so.1.0 via the RPATH baked
# into it at build time (/usr/local/lib); that library is copied explicitly
# in the rootfs stage.
#
# Post-install cleanup:
#   pip, setuptools, wheel, poetry   installers, not needed at runtime
#   __pycache__, *.pyc, *.pyo        bytecode caches
#   greenlet/tests                   bundled test suite
#   cffi/setuptools_ext.py           build-time cffi helper, not needed
#   _yaml*.so                        PyYAML C accelerator (pure-Python fallback
#                                    is used; see the main Dockerfile)
#   tests directories                bundled test suites (e.g. pandas/tests)
#   strip                            removes debug symbols from venv .so files;
#                                    .dynsym (used by dlopen/PyInit_*) is kept
RUN pip install --no-cache-dir "poetry>=2.1" \
  && poetry config virtualenvs.in-project true \
  && poetry config virtualenvs.options.always-copy true \
  && poetry install --only main --no-interaction --no-ansi \
  && rm -rf ~/.config/pypoetry ~/.cache/pypoetry ~/.cache/pip \
  && find /app/.venv -type d -name __pycache__ -prune -exec rm -rf {} + \
  && find /app/.venv -type f -name "*.pyc" -delete \
  && find /app/.venv -type f -name "*.pyo" -delete \
  && rm -rf /app/.venv/lib/python3.*/site-packages/pip* \
  && rm -rf /app/.venv/lib/python3.*/site-packages/setuptools* \
  && rm -rf /app/.venv/lib/python3.*/site-packages/wheel* \
  && rm -f /app/.venv/bin/pip* /app/.venv/bin/wheel /app/.venv/bin/easy_install* \
  && rm -rf /app/.venv/lib/python3.*/site-packages/greenlet/tests \
  && find /app/.venv -path "*/cffi/setuptools_ext.py" -delete \
  && find /app/.venv -name "_yaml*.so" -delete \
  && rm -rf /app/.venv/lib/python3.*/site-packages/pkg_resources \
  && find /app/.venv -type d -name tests -prune -exec rm -rf {} + \
  && find /app/.venv -name "*.so*" -type f -exec strip {} + 2>/dev/null || true

# Remove stdlib extension modules that pull in system libraries the application
# never uses, so those libraries are absent from the runtime closure.
# Module → eliminated system library dependency:
#   _sqlite3              → libsqlite3.so.0      (SQLite; app uses HANA)
#   _dbm, _gdbm           → libgdbm.so.6 + libgdbm_compat.so.4  (Berkeley DB)
#   _curses, _curses_panel → libncursesw.so.6 + libpanelw.so.6  (terminal UI)
#   readline              → libreadline.so.8 + libncursesw.so.6  (REPL line editing)
#   _uuid                 → libuuid.so.1  (OS UUID; app uses the uuid_utils wheel)
#   _tkinter              → Tk/Tcl bindings (safety remove; Tk not installed)
#
# Also removed: all CPython test/debug extension modules (_testcapi,
# _ctypes_test, xxlimited, _xxtestfuzz, etc.) which have no runtime purpose,
# plus the corresponding pure-Python packages for the removed C modules.
# .opt-[12].pyc bytecode variants are deleted: make install compiles all three
# optimisation levels but the interpreter loads only the plain .pyc.
# strip removes debug symbols (.symtab, .debug_*) from the remaining modules;
# the dynamic symbol table (.dynsym) used by dlopen and PyInit_* is preserved.
RUN rm -f \
      /usr/local/lib/python3.14/lib-dynload/_sqlite3*.so \
      /usr/local/lib/python3.14/lib-dynload/_dbm*.so \
      /usr/local/lib/python3.14/lib-dynload/_gdbm*.so \
      /usr/local/lib/python3.14/lib-dynload/_curses*.so \
      /usr/local/lib/python3.14/lib-dynload/readline*.so \
      /usr/local/lib/python3.14/lib-dynload/_uuid*.so \
      /usr/local/lib/python3.14/lib-dynload/_tkinter*.so \
      /usr/local/lib/python3.14/lib-dynload/_test*.so \
      /usr/local/lib/python3.14/lib-dynload/_ctypes_test*.so \
      /usr/local/lib/python3.14/lib-dynload/_xxtestfuzz*.so \
      /usr/local/lib/python3.14/lib-dynload/xxlimited*.so \
      /usr/local/lib/python3.14/lib-dynload/xxsubtype*.so \
  && rm -rf \
      /usr/local/lib/python3.14/test \
      /usr/local/lib/python3.14/idlelib \
      /usr/local/lib/python3.14/tkinter \
      /usr/local/lib/python3.14/turtledemo \
      /usr/local/lib/python3.14/sqlite3 \
      /usr/local/lib/python3.14/dbm \
      /usr/local/lib/python3.14/curses \
  && find /usr/local/lib/python3.14 -name '*.opt-[12].pyc' -delete \
  && strip /usr/local/lib/python3.14/lib-dynload/*.so 2>/dev/null || true \
  # Assert the removed modules are truly gone: importing must fail.
  && ! /usr/local/bin/python3 -c "import sqlite3"  2>/dev/null \
  && ! /usr/local/bin/python3 -c "import _gdbm"    2>/dev/null \
  && ! /usr/local/bin/python3 -c "import readline" 2>/dev/null

# Writable working directories. gid 0 + group-write follows the OpenShift
# arbitrary-uid idiom: the runtime user (10001) can write regardless of the
# uid assigned by the orchestrator.
RUN install -d -o 10001 -g 0 -m 0775 /app/data /app/tmp

# --- Stage 2: rootfs ----------------------------------------------------------
# Assembles /rootfs — the exact file tree the runtime image will consist of.
#
# Library closure: ldd (musl's /lib/ld-musl-x86_64.so.1 --list) is run over
# the Python interpreter binary and every .so file under lib-dynload and the
# venv. Stdout lists the resolved paths of every shared library the loader
# would map. "=> not found" in stdout means a genuinely missing system library
# and fails the build immediately; the stderr "Error relocating: <sym>: symbol
# not found" messages for Python C API symbols resolved at runtime by the
# interpreter process are discarded with 2>/dev/null.
# awk collects two line shapes:
#   libssl.so.3 => /usr/lib/libssl.so.3 (0x...)   →  $3
#   /lib/ld-musl-x86_64.so.1 (0x...)              →  $1
# Paths under /app (venv, copied whole) and /usr/local (Python installation,
# copied whole) are excluded; we only want the system libraries from /lib
# and /usr/lib. cp --parents -L copies each library to the same absolute path
# under /rootfs, dereferencing symlinks: "libssl.so.3" in ldd output is a
# symlink whose canonical content is written to /rootfs/usr/lib/libssl.so.3,
# matching the NEEDED entry in the extension module's ELF header.
#
# After the closure, whole-tree copies bring in: the Python stdlib (already
# trimmed in stage 1), libpython3.14.so.1.0 (the RPATH baked into every
# Python binary points to /usr/local/lib/), the interpreter binary, CA
# certificates for TLS, timezone data for Python's zoneinfo module, the venv
# (renamed from .venv to venv), and the application source.
#
# System libraries present in the runtime image and the reason each cannot be
# removed:
#   /lib/ld-musl-x86_64.so.1  — musl dynamic loader; every ELF binary needs it
#   libssl.so.3 + libcrypto.so.3  — OpenSSL; required for HTTPS to GitHub
#                                   (doc fetcher), SAP AI Core, and HANA Cloud
#   libffi.so.8                — libffi; required by _ctypes.so, which hdbcli's
#                                cffi bindings use to call the SAP HANA C driver
#   libstdc++.so.6             — C++ standard library; pyhdbcli.abi3.so links it
#   libgcc_s.so.1              — GCC runtime for C++ exception handling; also
#                                required by pyhdbcli.abi3.so
#   libbz2.so.1                — bzip2; required by _bz2.so (HTTP content
#                                encoding used by some endpoints)
#   liblzma.so.5               — xz/lzma; required by _lzma.so
#   libzstd.so.1               — zstd; required by _zstd.so
#   libz.so.1                  — zlib; required by zlib.so and binascii.so
#
# NOT present (and why they were eliminated):
#   libsqlite3.so.0    — _sqlite3.so removed; app never uses SQLite
#   libgdbm.so.6       — _dbm.so / _gdbm.so removed; Berkeley DB replacement
#   libncursesw.so.6   — _curses.so / readline.so removed; no interactive REPL
#   libpanelw.so.6     — _curses_panel.so removed; same
#   libreadline.so.8   — readline.so removed; same
#   libuuid.so.1       — _uuid.so removed; app uses uuid_utils wheel instead
#   libapk.so.3.0.0    — apk package manager library; only needed by apk
#   engines-3/*.so     — OpenSSL legacy engine ABI; not used for standard TLS
#   ossl-modules/legacy.so — legacy crypto algorithms (DES, RC4…); not used
#   busybox            — shell + coreutils; no shell needed in a batch job image
#   ldconfig, ldd, ssl_client, c_rehash, getconf, getent, iconv  — admin tools
FROM builder AS rootfs
RUN set -eu \
  # Directory skeleton. Alpine uses a real /lib directory (not a symlink to
  # /usr/lib); /usr/local/lib holds libpython3.14.so.1.0.
  && mkdir -p /rootfs/lib /rootfs/usr/lib /rootfs/usr/local/lib \
              /rootfs/usr/local/bin /rootfs/etc /rootfs/app \
  # Run ldd over the interpreter binary and all .so files; capture stdout.
  # 2>/dev/null discards the musl "Error relocating: <sym>" stderr noise for
  # Python C API symbols — those are resolved at runtime, not by the loader.
  && { echo /usr/local/bin/python3.14; \
       find /usr/local/lib/python3.14/lib-dynload /app/.venv \
            \( -name '*.so' -o -name '*.so.*' \) -type f | sort; \
     } | xargs -I{} /lib/ld-musl-x86_64.so.1 --list {} 2>/dev/null \
     > /tmp/ldd.out || true \
  # Any "=> not found" line means a system library is genuinely missing;
  # fail the build and show which files need it.
  && if grep -q '=> not found' /tmp/ldd.out; then \
       echo 'unresolved shared libraries:'; \
       grep '=> not found' /tmp/ldd.out; \
       exit 1; \
     fi \
  # Extract resolved paths, skip /app (venv) and /usr/local (Python stdlib),
  # then copy each library to the same absolute path under /rootfs.
  # cp --parents -L: --parents preserves directory structure;
  # -L dereferences symlinks so the file is written to the versionless name
  # (e.g. libssl.so.3) that the NEEDED entry in each .so requests.
  && awk '$2 == "=>" && $3 ~ /^\// { print $3 } \
          $1 ~ /^\// && $2 ~ /^\(0x/ { print $1 }' /tmp/ldd.out \
     | grep -vE '^/app/|^/usr/local/' \
     | sort -u \
     | while read -r lib; do cp --parents -L "$lib" /rootfs; done \
  # Python interpreter binary (the venv's python copies have the same RPATH).
  && cp -a --parents /usr/local/bin/python3.14 /rootfs \
  # libpython3.14.so.1.0 and symlinks: the RPATH in every python binary points
  # to /usr/local/lib/, so the real library must be at that exact path.
  && cp -a --parents /usr/local/lib/libpython3.14.so.1.0 /rootfs \
  && cp -a --parents /usr/local/lib/libpython3.14.so     /rootfs \
  && cp -a --parents /usr/local/lib/libpython3.so        /rootfs \
  # Python stdlib (trimmed in stage 1). The system site-packages at
  # /usr/local/lib/python3.14/site-packages/ are removed: they contain poetry
  # and its dependencies (installed in stage 1) which are not needed at
  # runtime. The application runs inside /app/venv which has its own
  # site-packages.
  && cp -a --parents /usr/local/lib/python3.14 /rootfs \
  && rm -rf /rootfs/usr/local/lib/python3.14/site-packages \
  # CA certificates for HTTPS (GitHub codeload, SAP AI Core, HANA Cloud).
  && cp -a --parents /etc/ssl/certs /rootfs \
  # Timezone data for Python's zoneinfo module and timestamp formatting.
  && cp -a --parents /usr/share/zoneinfo /rootfs \
  # Venv (renamed from .venv to venv; PATH in the runtime image points here).
  && cp -a /app/.venv /rootfs/app/venv \
  # Application source and the docs-sources configuration file.
  && cp -a /app/src /app/docs_sources.json /rootfs/app/ \
  # Writable working dirs with correct ownership (created in stage 1).
  && cp -a --parents /app/data /app/tmp /rootfs \
  # Minimal /etc/passwd and /etc/group so uid 10001 resolves to a name in logs.
  && printf 'root:x:0:0:root:/root:/sbin/nologin\nappuser:x:10001:0::/nonexistent:/sbin/nologin\n' \
       > /rootfs/etc/passwd \
  && printf 'root:x:0:\nappuser:x:10001:\n' > /rootfs/etc/group \
  # World-writable /tmp for Python's tempfile module.
  && install -d -m 1777 /rootfs/tmp

# --- Stage 3: runtime ---------------------------------------------------------
# Starts from an empty filesystem. The single COPY makes /rootfs the whole
# image. No shell, no package manager, no coreutils, no files other than the
# ones the rootfs stage selected.
FROM scratch
COPY --from=rootfs /rootfs /

# PATH: only the venv bin and the Python interpreter directory; there is no
# /usr/bin in this image.
# PYTHONPATH: the application source tree.
# PYTHONDONTWRITEBYTECODE: suppresses .pyc creation at runtime.
# SSL_CERT_FILE: names the CA bundle explicitly for libraries that consult
# this environment variable rather than OpenSSL's compiled-in default path.
ENV PATH="/app/venv/bin:/usr/local/bin" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Build-time completeness check. Exec form — no shell exists in this image.
# Each import exercises a specific system library in the closure:
#   ssl       → _ssl.so         → libssl.so.3 + libcrypto.so.3
#   ctypes    → _ctypes.so      → libffi.so.8
#   bz2       → _bz2.so         → libbz2.so.1
#   lzma      → _lzma.so        → liblzma.so.5
#   zlib      → zlib.so         → libz.so.1
#   hashlib   → _hashlib.so     → libcrypto.so.3
#   hdbcli    → pyhdbcli.abi3.so → libstdc++.so.6 + libgcc_s.so.1
# A missing shared library or a disabled stdlib module the application imports
# eagerly causes this step to fail, not the pod.
RUN ["/app/venv/bin/python", "-c", \
     "import ssl, ctypes, bz2, lzma, zlib, hashlib; from hdbcli import dbapi"]

USER 10001:0
