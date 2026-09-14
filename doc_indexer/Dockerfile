# syntax=docker/dockerfile:1

# Three-stage build:
#
#   builder  Alpine Python + a C toolchain. Installs the application's
#            dependencies into a virtualenv with poetry, then trims both the
#            venv and the interpreter's stdlib.
#   rootfs   Same image as builder. Assembles, in /rootfs, the complete set
#            of files the application needs at runtime: the interpreter, the
#            virtualenv, the application source, and every shared library
#            those load, found by running the dynamic loader in list mode
#            over all of them.
#   runtime  FROM scratch, i.e. an empty filesystem, into which /rootfs is
#            copied. Contains no shell, no package manager, no coreutils, no
#            files other than the ones the rootfs stage selected. A final
#            RUN imports the application inside this image to prove the
#            file set is complete.
#
# Alpine (musl) rather than Garden Linux (glibc) because hdbcli, the SAP HANA
# client, ships only a musllinux_1_2_x86_64 wheel; there is no glibc wheel.
# Every other dependency has a musllinux wheel too. Because of the hdbcli
# wheel the image must be built for linux/amd64.
#
# Version pin: ALPINE_PYTHON_TAG picks the interpreter version and therefore
# the musl, OpenSSL, zlib, bzip2, xz, zstd and libstdc++ that end up in the
# runtime image. A CVE in any of those is fixed by bumping the tag.

ARG ALPINE_PYTHON_TAG=3.14-alpine

# --- Stage 1: builder ---------------------------------------------------------
FROM python:${ALPINE_PYTHON_TAG} AS builder

# Toolchain for any C-extension wheel that lacks a musllinux binary (none at
# the moment; gcc and musl-dev cover the fallback compile path and libffi-dev
# the cffi header). binutils provides strip. git is excluded on purpose: the
# fetcher downloads release tarballs.
RUN apk add --no-cache gcc musl-dev libffi-dev binutils

# Trim the interpreter's stdlib. Removed stdlib extension modules and the
# system library each of them would otherwise pull into the runtime image:
#   _sqlite3                  libsqlite3.so.0   (the app stores in HANA)
#   _dbm, _gdbm               libgdbm*.so       (Berkeley / GNU dbm)
#   _curses, _curses_panel    libncursesw.so.6, libpanelw.so.6
#   readline                  libreadline.so.8, libncursesw.so.6
#   _uuid                     libuuid.so.1      (uuid falls back to pure Python)
#   _tkinter                  Tk                (not installed anyway)
#   _test*, _ctypes_test, _xxtestfuzz, xxlimited*, xxsubtype   CPython's own
#                             test modules, no runtime purpose
# Also removed: the stdlib test suite, IDLE, the Tk bindings and demos, the
# pure-Python packages wrapping the disabled C modules, and the *.opt-[12].pyc
# bytecode for python -O / -OO (the interpreter runs without -O, so only the
# plain .pyc is loaded). strip removes debug symbols from the remaining
# extension modules; the dynamic symbol table that dlopen and PyInit_* use
# stays, so the modules still import. The python -c lines check that the
# modules the application needs work and that two removed ones are absent.
RUN cd /usr/local/lib/python3.14 \
  && rm -f lib-dynload/_sqlite3* lib-dynload/_dbm* lib-dynload/_gdbm* \
       lib-dynload/_curses* lib-dynload/readline* lib-dynload/_uuid* \
       lib-dynload/_tkinter* lib-dynload/_test* lib-dynload/_ctypes_test* \
       lib-dynload/_xxtestfuzz* lib-dynload/xxlimited* lib-dynload/xxsubtype* \
  && rm -rf test idlelib tkinter turtledemo turtle.py __phello__ sqlite3 dbm curses \
  && find . -name '*.opt-[12].pyc' -delete \
  && strip lib-dynload/*.so \
  && python3 -c "import ssl, ctypes, zlib, bz2, lzma, hashlib, uuid, zoneinfo; zoneinfo.ZoneInfo('Europe/Berlin')" \
  && ! python3 -c "import sqlite3" 2>/dev/null \
  && ! python3 -c "import readline" 2>/dev/null

WORKDIR /app

COPY pyproject.toml poetry.lock ./

# Application dependencies into /app/.venv, then cleanup.
#
# 1. Install poetry into the interpreter's site-packages; poetry creates
#    /app/.venv (in-project) and installs the locked main dependencies into
#    it. always-copy makes the venv's bin/python a copy of the interpreter
#    binary rather than a symlink, so the runtime image can exec it directly.
# 2. Remove poetry, pip and ensurepip from /usr/local again, plus their
#    caches. The interpreter tree that ships is then stdlib only.
# 3. Delete the pyexpat and _elementtree extension modules. They embed a
#    copy of expat (Alpine's CPython links it statically) and were only
#    needed by pip, via xmlrpc.client, to install wheels; nothing in the
#    application parses XML. Assert that no expat code remains: the import
#    must fail, and the string "expat_<version>" (embedded in every expat
#    build) must appear neither in the interpreter nor in any .so under
#    /usr/local or the venv.
# 4. Trim the venv:
#      __pycache__, *.pyc, *.pyo    bytecode caches; the runtime sets
#                                   PYTHONDONTWRITEBYTECODE, so none are
#                                   written later either
#      pip, setuptools, wheel,      installers, not needed to run
#      pkg_resources
#      cffi/setuptools_ext.py       build-time helper for cffi
#      _yaml*.so                    PyYAML's C accelerator; PyYAML falls
#                                   back to its pure-Python implementation
#      tests directories            bundled test suites. Only directories
#                                   named exactly "tests" are removed;
#                                   "testing" packages are public API
#    strip removes debug symbols from every shared object in the venv;
#    wheels on PyPI ship unstripped.
RUN pip install --no-cache-dir "poetry>=2.1" \
  && poetry config virtualenvs.in-project true \
  && poetry config virtualenvs.options.always-copy true \
  && poetry install --only main --no-interaction --no-ansi \
  && rm -rf ~/.config/pypoetry ~/.cache/pypoetry ~/.cache/pip \
  && rm -rf /usr/local/lib/python3.*/site-packages/* /usr/local/lib/python3.*/ensurepip \
       /usr/local/bin/pip* /usr/local/bin/poetry /usr/local/bin/wheel \
  && rm -f /usr/local/lib/python3.*/lib-dynload/pyexpat* /usr/local/lib/python3.*/lib-dynload/_elementtree* \
  && ! python3 -c "import pyexpat" 2>/dev/null \
  && ! grep -q 'expat_[0-9]' /usr/local/bin/python3.14 /usr/local/lib/libpython3.14.so.1.0 \
  && ! find /usr/local /app/.venv -name '*.so*' -type f -exec grep -l 'expat_[0-9]' {} + | grep . \
  && find /app/.venv -type d -name __pycache__ -prune -exec rm -rf {} + \
  && find /app/.venv -type f -name "*.pyc" -delete \
  && find /app/.venv -type f -name "*.pyo" -delete \
  && rm -rf /app/.venv/lib/python3.*/site-packages/pip* \
  && rm -rf /app/.venv/lib/python3.*/site-packages/setuptools* \
  && rm -rf /app/.venv/lib/python3.*/site-packages/wheel* \
  && rm -rf /app/.venv/lib/python3.*/site-packages/pkg_resources \
  && rm -f /app/.venv/bin/pip* /app/.venv/bin/wheel /app/.venv/bin/easy_install* \
  && find /app/.venv -path "*/cffi/setuptools_ext.py" -delete \
  && find /app/.venv -name "_yaml*.so" -delete \
  && find /app/.venv -type d -name tests -prune -exec rm -rf {} + \
  && find /app/.venv -name "*.so*" -type f -exec strip {} + 2>/dev/null

COPY src ./src
COPY docs_sources.json ./

# Writable working directories for the fetcher (downloaded docs, tarball
# scratch space). Owned by the runtime uid with gid 0 and group write, the
# OpenShift arbitrary-uid idiom, so the process can write regardless of the
# uid the orchestrator assigns.
RUN install -d -o 10001 -g 0 -m 0775 /app/data /app/tmp

# --- Stage 2: rootfs ----------------------------------------------------------
# Assembles /rootfs, the exact file tree the runtime image will consist of.
#
# 1. Directory skeleton. Alpine has a real /lib (not a symlink into /usr);
#    the musl loader lives at /lib/ld-musl-x86_64.so.1 and searches /lib,
#    /usr/local/lib and /usr/lib by default.
# 2. Shared-library closure. The musl loader in --list mode (Alpine's ldd)
#    is run over the interpreter binary and every .so under the stdlib and
#    the venv. Its output lists, per file, the libraries the loader would
#    map, as either
#        libssl.so.3 => /usr/lib/libssl.so.3 (0x...)
#    or, for the loader itself,
#        /lib/ld-musl-x86_64.so.1 (0x...)
#    A library the loader cannot find is reported on stderr as "Error
#    loading shared library ... (needed by ...)". Such a line is fatal
#    unless a file of that name exists under /usr/local or the venv: wheels
#    vendor libraries next to their extension modules (numpy.libs holds a
#    libstdc++ that needs a libgcc_s from the same directory), and those
#    resolve through the RPATH of the module that loads them, not when the
#    vendored library is listed on its own. Anything else missing would
#    surface only when that extension is first imported, so the build stops
#    and shows the line. Listing a lone extension module also makes musl
#    report "Error relocating ... symbol not found" for the Python C API
#    symbols that the interpreter process provides at runtime, and exit
#    non-zero; those are not missing libraries, so the loop ignores the
#    exit status. The awk picks the resolved paths out of both stdout line
#    shapes;
#    paths inside /app and /usr/local are skipped because those trees are
#    copied whole below. cp --parents -L copies each library to the same
#    path under /rootfs, dereferencing symlinks so the runtime gets real
#    files.
# 3. Whole trees: the interpreter binary, libpython3.14.so.1.0 (the binary
#    is linked against it; the venv's bin/python copy carries a RUNPATH of
#    $ORIGIN/../lib that does not resolve, so the loader falls back to its
#    default path and finds it in /usr/local/lib), the trimmed stdlib,
#    /etc/ssl (CA bundle and
#    OpenSSL's default cert paths, which point into it), and the time
#    zone database. cp -a keeps symlinks as symlinks.
# 4. The venv, renamed from .venv to venv, the application source, the
#    docs-sources file, and the writable data and tmp directories with their
#    ownership.
# 5. /etc/passwd and /etc/group with the root and appuser entries so uid
#    10001 resolves to a name, and a world-writable /tmp for tempfile.
FROM builder AS rootfs
RUN set -eu \
  && mkdir -p /rootfs/lib /rootfs/usr/lib /rootfs/usr/local/lib /rootfs/usr/local/bin /rootfs/etc /rootfs/app \
  && for f in /usr/local/bin/python3.14 $(find /usr/local/lib/python3.14 /app/.venv -name '*.so*' -type f); do \
       /lib/ld-musl-x86_64.so.1 --list "$f" >> /tmp/ldd.out 2>> /tmp/ldd.err || true; \
     done \
  && grep -h 'Error loading' /tmp/ldd.err | sed 's/^Error loading shared library \([^:]*\):.*/\1/' | sort -u > /tmp/missing \
  && for lib in $(cat /tmp/missing); do \
       find /usr/local /app/.venv -name "$lib" | grep -q . \
         || { echo "unresolved shared library: $lib"; grep "$lib" /tmp/ldd.err; exit 1; }; \
     done \
  && awk '$2 == "=>" && $3 ~ /^\// { print $3 } $1 ~ /^\// && $2 ~ /^\(0x/ { print $1 }' /tmp/ldd.out \
     | grep -vE '^/(app|usr/local)/' \
     | sort -u \
     | while read -r lib; do cp --parents -L "$lib" /rootfs; done \
  && cp -a --parents /usr/local/bin/python3.14 /usr/local/lib/libpython3.14.so.1.0 \
       /usr/local/lib/python3.14 /etc/ssl /usr/share/zoneinfo /rootfs \
  && cp -a /app/.venv /rootfs/app/venv \
  && cp -a /app/src /app/docs_sources.json /app/data /app/tmp /rootfs/app/ \
  && printf 'root:x:0:0:root:/root:/sbin/nologin\nappuser:x:10001:0::/nonexistent:/sbin/nologin\n' > /rootfs/etc/passwd \
  && printf 'root:x:0:\nappuser:x:10001:\n' > /rootfs/etc/group \
  && install -d -m 1777 /rootfs/tmp

# --- Stage 3: runtime ---------------------------------------------------------
# Starts from an empty filesystem; the single COPY makes /rootfs the whole
# image. Nothing from the builder stage is inherited.
FROM scratch
COPY --from=rootfs /rootfs /

# PATH has only the venv and the interpreter; there is no /usr/bin.
# SSL_CERT_FILE names the CA bundle explicitly for libraries that read the
# variable rather than OpenSSL's compiled-in default path.
ENV PATH="/app/venv/bin:/usr/local/bin" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Build-time check that the image is complete. Exec form, because there is
# no shell to run a command line through; the interpreter is started
# directly, on this image's files. It imports the stdlib modules that
# exercise every system library in the closure (ssl and hashlib for OpenSSL,
# ctypes for libffi, the compression modules for zlib/bzip2/xz/zstd), loads a
# time zone, and then imports the application's entry module, which pulls in
# hdbcli (libstdc++, libgcc_s) and the whole dependency tree. The real
# config.json is mounted at deploy time; an empty one written to a scratch
# directory under /tmp stands in for it so the import can complete. The
# indexer module builds a tiktoken encoder at import time, which downloads
# the encoding and caches it; the cache is pointed at the same scratch
# directory, and the directory is removed at the end so nothing from the
# check ends up in the layer. A shared library missing from the closure, or
# a stdlib module the application imports eagerly that was removed above,
# fails the build here rather than the Job.
RUN ["/app/venv/bin/python", "-c", "\
import os, shutil, ssl, ctypes, zlib, bz2, lzma, hashlib, zoneinfo; \
zoneinfo.ZoneInfo('Europe/Berlin'); \
os.mkdir('/tmp/gate'); \
open('/tmp/gate/config.json', 'w').write('{}'); \
os.environ['CONFIG_PATH'] = '/tmp/gate/config.json'; \
os.environ['TIKTOKEN_CACHE_DIR'] = '/tmp/gate/tiktoken'; \
import main; \
shutil.rmtree('/tmp/gate')"]

USER 10001:0

# The task (fetch, index, drop, tables) is supplied by the Job/CronJob
# manifest in exec form, e.g. ["python", "src/main.py", "fetch"]. There is no
# shell in this image, so "sh -c" command lines do not work. No
# ENTRYPOINT/CMD, matching the prior image's contract.
