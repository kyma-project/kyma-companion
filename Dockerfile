# syntax=docker/dockerfile:1

# Three-stage build:
#
#   builder  Garden Linux + a C toolchain. Builds a static libffi and a
#            CPython interpreter from source, installs the application's
#            dependencies into a virtualenv with poetry, and trims both.
#   rootfs   Same image as builder. Assembles, in /rootfs, the complete set
#            of files the application needs at runtime: the interpreter, the
#            virtualenv, the application source, and every shared library
#            those load, found by running ldd over all of them.
#   runtime  FROM scratch, i.e. an empty filesystem, into which /rootfs is
#            copied. Contains no shell, no package manager, no coreutils, no
#            files other than the ones the rootfs stage selected. A final
#            RUN imports the application inside this image to prove the
#            file set is complete.
#
# Version pins: GARDENLINUX_VERSION picks the builder image and therefore the
# glibc, OpenSSL, zlib, bzip2, xz and libstdc++ that end up in the runtime
# image. PYTHON_VERSION and LIBFFI_VERSION pick the source tarballs; each
# ADD below carries the SHA-256 of the tarball it downloads, so a version
# bump means changing the ARG and the checksum together.

ARG GARDENLINUX_VERSION=2150.9.0

# --- Stage 1: builder ---------------------------------------------------------
FROM ghcr.io/gardenlinux/gardenlinux:${GARDENLINUX_VERSION} AS builder

ARG PYTHON_VERSION=3.14.7
ARG LIBFFI_VERSION=3.8.0

# Toolchain and development headers for the CPython build:
#   gcc, libc6-dev, make   the compiler, C library headers, build driver
#   libssl-dev             OpenSSL headers, for the ssl and hashlib modules
#   zlib1g-dev             zlib headers, for the zlib module
#   libbz2-dev, liblzma-dev  bzip2 / xz headers, for the bz2 and lzma modules
#   ca-certificates, tzdata  copied into the runtime image later (TLS roots,
#                          time zone database for the zoneinfo module)
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       gcc libc6-dev make ca-certificates tzdata \
       libssl-dev zlib1g-dev libbz2-dev liblzma-dev \
  && rm -rf /var/lib/apt/lists/*

# libffi, needed by CPython's _ctypes module. Garden Linux ships the runtime
# library (libffi8) but not the headers, so libffi is built here from source
# as a static library (libffi.a) and linked into _ctypes. Build output goes
# to a log file and is printed only if a step fails.
#   --disable-shared --enable-static   produce only libffi.a
#   --with-pic                         position-independent code, required
#                                      because the .a is linked into a .so
#   --disable-docs                     skip the texinfo manual
#   --disable-multi-os-directory       install to lib/, not lib64/
ADD --checksum=sha256:7da3e2d9a171eb0a038f592ecad3ff2bb2550f3496d87b3b29ad0cf4430c0db4 \
    https://github.com/libffi/libffi/releases/download/v${LIBFFI_VERSION}/libffi-${LIBFFI_VERSION}.tar.gz /src/
RUN cd /src && tar xzf libffi-${LIBFFI_VERSION}.tar.gz && cd libffi-${LIBFFI_VERSION} \
  && ./configure --prefix=/opt/libffi --disable-shared --enable-static --with-pic \
       --disable-docs --disable-multi-os-directory > /tmp/libffi.log 2>&1 \
  && make -j"$(nproc)" >> /tmp/libffi.log 2>&1 \
  && make install >> /tmp/libffi.log 2>&1 \
  || { tail -50 /tmp/libffi.log; exit 1; }

# CPython from source, installed to /opt/python.
#
# Modules/Setup.local lists stdlib extension modules under "*disabled*" that
# are not built at all. Their C libraries therefore never enter the image:
#   _dbm, _gdbm             Berkeley DB / GNU dbm
#   _sqlite3                SQLite
#   _tkinter                Tk
#   readline, _curses, _curses_panel   GNU readline / ncurses
# Importing one of these later raises ModuleNotFoundError.
#
# pyexpat and _elementtree (XML parsing via CPython's bundled expat) are NOT
# disabled here: pip needs xmlrpc.client, which needs pyexpat, to install
# wheels. They are built as shared extension modules in lib-dynload and
# deleted after the virtualenv exists (see the poetry step below).
#
# configure flags:
#   LIBFFI_CFLAGS / LIBFFI_LIBS   point _ctypes at the static libffi above
#   --with-openssl=/usr           use Garden Linux's OpenSSL
#   --with-ensurepip=install      install pip, so poetry can be installed;
#                                 pip is removed again after the venv build
#   --disable-test-modules        skip the _testcapi etc. C test modules
#   --without-static-libpython    do not install libpython3.14.a
# The interpreter binary is statically linked against libpython (there is
# no libpython3.14.so); its only runtime library dependencies are libc and
# libm.
ADD --checksum=sha256:62859805f6fdf25e2bcbf3fa3217801e1996887ca33e6a2af80674bdfa2dbe07 \
    https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz /src/
RUN cd /src && tar xzf Python-${PYTHON_VERSION}.tgz && cd Python-${PYTHON_VERSION} \
  && printf '%s\n' '*disabled*' _dbm _gdbm _sqlite3 _tkinter readline _curses _curses_panel \
       > Modules/Setup.local \
  && LIBFFI_CFLAGS="-I/opt/libffi/include" LIBFFI_LIBS="/opt/libffi/lib/libffi.a" \
     ./configure --prefix=/opt/python --with-openssl=/usr --with-ensurepip=install \
       --disable-test-modules --without-static-libpython > /tmp/python.log 2>&1 \
  && make -j"$(nproc)" >> /tmp/python.log 2>&1 \
  && make install >> /tmp/python.log 2>&1 \
  || { tail -50 /tmp/python.log; exit 1; }

# Trim the installed interpreter tree. Removed:
#   lib/python3.*/test                  the stdlib test suite
#   idlelib, tkinter, turtledemo, turtle.py, __phello__   IDLE, Tk bindings,
#                                       demos; _tkinter is disabled anyway
#   sqlite3, dbm, curses                the pure-Python packages wrapping
#                                       the disabled C modules
#   config-3.*                          Makefile/Setup used only to compile
#                                       new extension modules
#   lib/pkgconfig, include              .pc files and C headers, used only
#                                       to compile against the interpreter
#   bin/idle3*, pydoc3*, python3*-config   tools not used at runtime
#   *.opt-1.pyc, *.opt-2.pyc            bytecode for python -O / -OO;
#                                       make install compiles all three
#                                       levels, the interpreter runs without
#                                       -O so only the plain .pyc is loaded
# strip removes debug symbols (.symtab, .debug_*) from the interpreter and
# the extension modules. The dynamic symbol table (.dynsym) that the loader
# and dlopen use stays, so the modules still import.
# The python -c lines check that the modules the application needs (ssl,
# ctypes, compression, hashing, zoneinfo with a real zone) work, and that
# two disabled modules are indeed absent. pip is kept for the next step.
RUN cd /opt/python \
  && rm -rf lib/python3.*/test lib/python3.*/idlelib lib/python3.*/tkinter \
       lib/python3.*/turtledemo lib/python3.*/turtle.py lib/python3.*/__phello__ \
       lib/python3.*/sqlite3 lib/python3.*/dbm lib/python3.*/curses \
       lib/python3.*/config-3.* lib/pkgconfig include \
       bin/idle3* bin/pydoc3* bin/python3*-config \
  && find lib -name '*.opt-[12].pyc' -delete \
  && strip bin/python3.14 lib/python3.*/lib-dynload/*.so \
  && /opt/python/bin/python3 -c "import ssl, ctypes, zlib, bz2, lzma, hashlib, uuid, zoneinfo; zoneinfo.ZoneInfo('Europe/Berlin')" \
  && ! /opt/python/bin/python3 -c "import dbm.ndbm" 2>/dev/null \
  && ! /opt/python/bin/python3 -c "import sqlite3" 2>/dev/null

ENV PATH="/opt/python/bin:$PATH"
WORKDIR /app

COPY pyproject.toml poetry.lock ./

# Application dependencies into /app/.venv, then cleanup.
#
# 1. Install poetry into the interpreter's site-packages with the pip that
#    ensurepip provided; poetry creates /app/.venv (in-project) and installs
#    the locked main dependencies into it.
# 2. Remove poetry, pip and ensurepip from /opt/python again, plus their
#    caches. The interpreter tree that ships is then stdlib only.
# 3. Delete the pyexpat and _elementtree extension modules that were only
#    needed for the wheel installs, then assert that no expat code remains:
#    import must fail, and the string "expat_<version>" (embedded in every
#    expat build) must appear neither in the interpreter binary nor in any
#    .so under /opt/python or the venv.
# 4. Trim the venv:
#      __pycache__, *.pyc, *.pyo    bytecode caches; the runtime sets
#                                   PYTHONDONTWRITEBYTECODE, so none are
#                                   written later either
#      pip, setuptools, wheel       installers, not needed to run
#      docs                         package documentation
#      rdflib berkeleydb backend    the storage plugin for Berkeley DB, and
#                                   the mention of it in rdflib's METADATA
#      _yaml*.so                    PyYAML's C accelerator; PyYAML falls
#                                   back to its pure-Python implementation
#      tests directories            bundled test suites (pandas/tests alone
#                                   is 16 MB). Only directories named
#                                   exactly "tests" are removed; "testing"
#                                   packages such as numpy.testing are
#                                   public API and stay.
#    strip removes debug symbols from every shared object in the venv;
#    wheels on PyPI ship unstripped.
RUN python3 -m pip install --no-cache-dir "poetry>=2.1" \
  && poetry config virtualenvs.in-project true \
  && poetry install --only main --no-interaction --no-ansi \
  && rm -rf ~/.config/pypoetry ~/.cache/pypoetry ~/.cache/pip \
  && rm -rf /opt/python/lib/python3.*/site-packages/* /opt/python/lib/python3.*/ensurepip \
       /opt/python/bin/pip* /opt/python/bin/poetry \
  && rm -f /opt/python/lib/python3.*/lib-dynload/pyexpat* /opt/python/lib/python3.*/lib-dynload/_elementtree* \
  && ! python3 -c "import pyexpat" 2>/dev/null \
  && ! grep -q 'expat_[0-9]' /opt/python/bin/python3.14 \
  && ! find /opt/python /app/.venv -name '*.so*' -type f -exec grep -l 'expat_[0-9]' {} + | grep . \
  && find /app/.venv -type d -name __pycache__ -prune -exec rm -rf {} + \
  && find /app/.venv -type f -name "*.pyc" -delete \
  && find /app/.venv -type f -name "*.pyo" -delete \
  && rm -rf /app/.venv/lib/python3.*/site-packages/pip* \
  && rm -rf /app/.venv/lib/python3.*/site-packages/setuptools* \
  && rm -rf /app/.venv/lib/python3.*/site-packages/wheel* \
  && rm -f /app/.venv/bin/pip* /app/.venv/bin/wheel /app/.venv/bin/easy_install* \
  && rm -rf /app/.venv/docs \
  && find /app/.venv -path "*/rdflib/plugins/stores/berkeleydb.py" -delete \
  && find /app/.venv -path "*/rdflib*.dist-info/METADATA" -exec sed -i '/berkeleydb/Id' {} \; \
  && find /app/.venv -name "_yaml*.so" -delete \
  && find /app/.venv -type d -name tests -prune -exec rm -rf {} + \
  && find /app/.venv -name "*.so*" -type f -exec strip {} + 2>/dev/null

COPY src ./src
COPY config ./config

# --- Stage 2: rootfs ----------------------------------------------------------
# Assembles /rootfs, the exact file tree the runtime image will consist of.
#
# 1. Directory skeleton with the merged-/usr layout of the builder: /lib,
#    /lib64 and /bin are symlinks into /usr. The dynamic loader searches
#    /lib/x86_64-linux-gnu and /usr/lib/x86_64-linux-gnu, and the interpreter
#    binary names its loader as /lib64/ld-linux-x86-64.so.2, so both spellings
#    must resolve to the same files.
# 2. Shared-library closure. ldd is run over the interpreter binary and every
#    .so under /opt/python and the venv. Its output lists, per file, the
#    libraries the loader would map, as either
#        libssl.so.3 => /usr/lib/x86_64-linux-gnu/libssl.so.3 (0x...)
#    or, for the loader itself,
#        /lib64/ld-linux-x86-64.so.2 (0x...)
#    A library the loader cannot find prints "=> not found"; the build stops
#    there and shows the file that needs it, because a library missing from
#    the closure would surface only when that extension is first imported.
#    The awk picks the resolved paths out of both line shapes; paths inside
#    /app and /opt/python are skipped because those trees are copied whole
#    below. cp --parents -L copies each library to the same path under
#    /rootfs, dereferencing symlinks so the runtime gets real files.
# 3. libgcc_s.so.1 is added by hand: glibc loads it with dlopen for thread
#    cancellation and C++ exception unwinding, so ldd never lists it.
# 4. Whole trees: the interpreter, /etc/ssl and /usr/lib/ssl (CA bundle and
#    OpenSSL's default paths, which point into /etc/ssl), the time zone
#    database, and /etc/nsswitch.conf (name-service order; the "files" and
#    "dns" backends it names are compiled into this glibc, so no libnss_*
#    files are needed). cp -a keeps symlinks as symlinks.
# 5. The venv, renamed from .venv to venv, and the application source and
#    config. The venv's bin/python is a symlink to /opt/python/bin/python3.14,
#    which resolves because /opt/python is copied to the same path.
# 6. /etc/passwd and /etc/group with the root and appuser entries so uid/gid
#    5678 resolve to a name, and a world-writable /tmp for tempfile.
FROM builder AS rootfs
RUN set -eu \
  && mkdir -p /rootfs/usr/lib /rootfs/usr/lib64 /rootfs/usr/bin /rootfs/etc /rootfs/app \
  && ln -s usr/lib /rootfs/lib && ln -s usr/lib64 /rootfs/lib64 && ln -s usr/bin /rootfs/bin \
  && { echo /opt/python/bin/python3.14; find /opt/python /app/.venv -name '*.so*' -type f; } \
     | xargs ldd 2>/dev/null > /tmp/ldd.out \
  && if grep -B1 'not found' /tmp/ldd.out; then echo 'unresolved shared libraries'; exit 1; fi \
  && awk '$2 == "=>" && $3 ~ /^\// { print $3 } $1 ~ /^\// && $2 ~ /^\(0x/ { print $1 }' /tmp/ldd.out \
     | grep -vE '^/(app|opt/python)/' \
     | sort -u \
     | while read -r lib; do cp --parents -L "$lib" /rootfs; done \
  && cp --parents -L "$(find /usr/lib -name libgcc_s.so.1 -print -quit)" /rootfs \
  && cp -a --parents /opt/python /etc/ssl /usr/lib/ssl /usr/share/zoneinfo /etc/nsswitch.conf /rootfs \
  && cp -a /app/.venv /rootfs/app/venv \
  && cp -a /app/src /app/config /rootfs/app/ \
  && printf 'root:x:0:0:root:/root:/sbin/nologin\nappuser:x:5678:5678::/nonexistent:/sbin/nologin\n' > /rootfs/etc/passwd \
  && printf 'root:x:0:\nappuser:x:5678:\n' > /rootfs/etc/group \
  && install -d -m 1777 /rootfs/tmp

# --- Stage 3: runtime ---------------------------------------------------------
# Starts from an empty filesystem; the single COPY makes /rootfs the whole
# image. Nothing from the builder stage is inherited.
FROM scratch
COPY --from=rootfs /rootfs /

# PATH has only the venv and the interpreter; there is no /usr/bin.
# SSL_CERT_FILE names the CA bundle explicitly for libraries that read the
# variable rather than OpenSSL's compiled-in default path.
ENV PATH="/app/venv/bin:/opt/python/bin" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Build-time check that the image is complete. Exec form, because there is
# no shell to run a command line through; the interpreter is started
# directly, on this image's files, and imports the application's entry
# module. A shared library missing from the closure, or a stdlib module the
# application imports eagerly that was disabled above, fails the build here.
# The real config.json is mounted at deploy time; the example config from
# the repository stands in for it so the import can complete.
RUN ["/app/venv/bin/python", "-c", "import os; os.environ['CONFIG_PATH'] = 'config/config-example.json'; import main"]

USER 5678:5678

EXPOSE 8000
CMD ["python3.14", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
