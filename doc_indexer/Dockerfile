# syntax=docker/dockerfile:1

# Three-stage build:
#
#   builder  Garden Linux + a C toolchain. Builds a static libffi and a
#            CPython interpreter from source, installs the application's
#            dependencies into a virtualenv with poetry, and trims both.
#   rootfs   Same image as builder. Assembles, in /rootfs, the complete set
#            of files the application needs at runtime: the interpreter, the
#            virtualenv, the application source, and every shared library
#            those load, found by running ldd over all of them. Also
#            writes the package metadata vulnerability scanners read.
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

ARG GARDENLINUX_VERSION=2150.10.0

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
# CPPFLAGS/CFLAGS compile libffi with the hardening Debian applies to its
# packages (checked-buffer libc calls, stack canaries, stack-clash probes);
# libffi ends up inside _ctypes, so it would otherwise be the one unhardened
# part of that module. Setting CFLAGS replaces libffi's default optimisation
# flags, hence the explicit -O2, which _FORTIFY_SOURCE also requires.
ADD --checksum=sha256:7da3e2d9a171eb0a038f592ecad3ff2bb2550f3496d87b3b29ad0cf4430c0db4 \
    https://github.com/libffi/libffi/releases/download/v${LIBFFI_VERSION}/libffi-${LIBFFI_VERSION}.tar.gz /src/
RUN cd /src && tar xzf libffi-${LIBFFI_VERSION}.tar.gz && cd libffi-${LIBFFI_VERSION} \
  && CPPFLAGS="-D_FORTIFY_SOURCE=3" CFLAGS="-O2 -fstack-protector-strong -fstack-clash-protection" \
     ./configure --prefix=/opt/libffi --disable-shared --enable-static --with-pic \
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
#   --enable-safety               -fstack-protector-strong (stack canaries)
#   --enable-slower-safety        -D_FORTIFY_SOURCE=3 (checked-buffer variants
#                                 of memcpy, sprintf etc.)
#   CFLAGS                        -fstack-clash-protection: probe each page of
#                                 a large stack allocation
#   LDFLAGS                       -z relro -z now: full RELRO; all symbols are
#                                 resolved at load time and the GOT is then
#                                 mapped read-only
# CPython's default build has none of these; the Garden Linux libraries in
# the image have all of them. They apply to the interpreter and to every
# stdlib extension module. The trim step below asserts the result.
# The interpreter binary is statically linked against libpython (there is
# no libpython3.14.so); its only runtime library dependencies are libc and
# libm.
ADD --checksum=sha256:62859805f6fdf25e2bcbf3fa3217801e1996887ca33e6a2af80674bdfa2dbe07 \
    https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz /src/
RUN cd /src && tar xzf Python-${PYTHON_VERSION}.tgz && cd Python-${PYTHON_VERSION} \
  && printf '%s\n' '*disabled*' _dbm _gdbm _sqlite3 _tkinter readline _curses _curses_panel \
       > Modules/Setup.local \
  && LIBFFI_CFLAGS="-I/opt/libffi/include" LIBFFI_LIBS="/opt/libffi/lib/libffi.a" \
     CFLAGS="-fstack-clash-protection" LDFLAGS="-Wl,-z,relro -Wl,-z,now" \
     ./configure --prefix=/opt/python --with-openssl=/usr --with-ensurepip=install \
       --disable-test-modules --without-static-libpython \
       --enable-safety --enable-slower-safety > /tmp/python.log 2>&1 \
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
# The readelf lines assert the hardening requested at configure time, on the
# interpreter and on _ctypes (which contains libffi): a GNU_RELRO program
# header together with BIND_NOW in the dynamic section means full RELRO (the
# segment alone is partial RELRO, which leaves the GOT entries for library
# functions writable); an undefined __stack_chk_fail means stack
# canaries are compiled in; a __*_chk import (__memcpy_chk, __snprintf_chk,
# ...) means _FORTIFY_SOURCE took effect.
RUN cd /opt/python \
  && rm -rf lib/python3.*/test lib/python3.*/idlelib lib/python3.*/tkinter \
       lib/python3.*/turtledemo lib/python3.*/turtle.py lib/python3.*/__phello__ \
       lib/python3.*/sqlite3 lib/python3.*/dbm lib/python3.*/curses \
       lib/python3.*/config-3.* lib/pkgconfig include \
       bin/idle3* bin/pydoc3* bin/python3*-config \
  && find lib -name '*.opt-[12].pyc' -delete \
  && strip bin/python3.14 lib/python3.*/lib-dynload/*.so \
  && for f in bin/python3.14 lib/python3.*/lib-dynload/_ctypes.*.so; do \
       readelf -lW "$f" | grep -q GNU_RELRO \
       && readelf -dW "$f" | grep -q BIND_NOW \
       && readelf -W --dyn-syms "$f" | grep -q __stack_chk_fail \
       && readelf -W --dyn-syms "$f" | grep -qE '__(mem|str|stp|v?sn?printf)[a-z]*_chk' \
       || { echo "hardening missing in $f"; exit 1; }; \
     done \
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
#    The list of copied libraries is kept in /tmp/libs.txt for step 7.
# 4. Whole trees: the interpreter, /etc/ssl and /usr/lib/ssl (CA bundle and
#    OpenSSL's default paths, which point into /etc/ssl), the time zone
#    database, and /etc/nsswitch.conf (name-service order; the "files" and
#    "dns" backends it names are compiled into this glibc, so no libnss_*
#    files are needed). cp -a keeps symlinks as symlinks.
# 5. The venv, renamed from .venv to venv, the application source, the
#    docs-sources file, and the writable data and tmp directories with their
#    ownership. The venv's bin/python is a symlink to /opt/python/bin/python3.14,
#    which resolves because /opt/python is copied to the same path.
# 6. /etc/passwd and /etc/group with the root and appuser entries so uid
#    10001 resolves to a name (gid 0, OpenShift arbitrary-uid idiom), and a
#    world-writable /tmp for tempfile.
# 7. Metadata for vulnerability scanners and SBOM tools. A scratch image has
#    no dpkg database, so Trivy, Grype and Syft would report no OS packages
#    and the Garden Linux libraries copied in step 2 and 3 would go unscanned.
#    Each copied library is mapped to the package that owns it with dpkg -S
#    (tried on the path ldd printed and on its symlink-resolved form, since
#    dpkg records only one of them); a library no package owns stops the
#    build. For glibc's loader dpkg -S also prints "diversion by libc6"
#    lines, which name no package and are dropped. The status stanza of each
#    package is written to
#    /var/lib/dpkg/status.d/<package>, the per-package layout of Google's
#    distroless images, which those tools read. /etc/os-release tells them
#    which distribution the versions belong to. A package is listed in full
#    even if only one of its files is in the image, so findings can concern
#    files that are not there; that errs on the safe side. CPython and libffi
#    are compiled here, belong to no package and are not listed; they are
#    tracked through PYTHON_VERSION and LIBFFI_VERSION above.
FROM builder AS rootfs
RUN set -eu \
  && mkdir -p /rootfs/usr/lib /rootfs/usr/lib64 /rootfs/usr/bin /rootfs/etc /rootfs/app \
  && ln -s usr/lib /rootfs/lib && ln -s usr/lib64 /rootfs/lib64 && ln -s usr/bin /rootfs/bin \
  && { echo /opt/python/bin/python3.14; find /opt/python /app/.venv -name '*.so*' -type f; } \
     | xargs ldd 2>/dev/null > /tmp/ldd.out \
  && if grep -B1 'not found' /tmp/ldd.out; then echo 'unresolved shared libraries'; exit 1; fi \
  && awk '$2 == "=>" && $3 ~ /^\// { print $3 } $1 ~ /^\// && $2 ~ /^\(0x/ { print $1 }' /tmp/ldd.out \
     | grep -vE '^/(app|opt/python)/' \
     | sort -u > /tmp/libs.txt \
  && find /usr/lib -name libgcc_s.so.1 -print -quit >> /tmp/libs.txt \
  && while read -r lib; do cp --parents -L "$lib" /rootfs; done < /tmp/libs.txt \
  && while read -r lib; do \
       dpkg -S "$lib" 2>/dev/null || dpkg -S "$(readlink -f "$lib")" 2>/dev/null \
       || { echo "no package owns $lib" >&2; exit 1; }; \
     done < /tmp/libs.txt > /tmp/owners.txt \
  && grep -v '^diversion by ' /tmp/owners.txt | sed 's|: /.*||' | sort -u > /tmp/pkgs.txt \
  && test -s /tmp/pkgs.txt \
  && mkdir -p /rootfs/var/lib/dpkg/status.d \
  && while read -r pkg; do \
       dpkg-query -s "$pkg" > "/rootfs/var/lib/dpkg/status.d/${pkg%%:*}" || exit 1; \
     done < /tmp/pkgs.txt \
  && cp -L /etc/os-release /rootfs/etc/os-release \
  && cp -a --parents /opt/python /etc/ssl /usr/lib/ssl /usr/share/zoneinfo /etc/nsswitch.conf /rootfs \
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
ENV PATH="/app/venv/bin:/opt/python/bin" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Build-time check that the image is complete. Exec form, because there is
# no shell to run a command line through; the interpreter is started
# directly, on this image's files. It imports the stdlib modules that
# exercise every system library in the closure (ssl and hashlib for OpenSSL,
# ctypes for libffi, the compression modules for zlib/bzip2/xz), loads a
# time zone, and then imports the application's entry module, which pulls in
# hdbcli (libstdc++, libgcc_s) and the whole dependency tree. The real
# config.json is mounted at deploy time; an empty one written to a scratch
# directory under /tmp stands in for it so the import can complete. The
# indexer module builds a tiktoken encoder at import time, which downloads
# the encoding and caches it; the cache is pointed at the same scratch
# directory, and the directory is removed at the end so nothing from the
# check ends up in the layer. A shared library missing from the closure, or
# a stdlib module the application imports eagerly that was disabled above,
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
