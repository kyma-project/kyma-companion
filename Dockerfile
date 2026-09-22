# syntax=docker/dockerfile:1

# Three-stage build:
#
#   builder  Wolfi + a C toolchain. Builds a CPython interpreter from source,
#            installs the application's dependencies into a virtualenv with
#            poetry, and trims both.
#   rootfs   Same image as builder. Assembles, in /rootfs, the complete set
#            of files the application needs at runtime: the interpreter, the
#            virtualenv, the application source, and every shared library
#            those load, found by running the dynamic loader in trace mode
#            over all of them. Also writes the package metadata vulnerability
#            scanners read.
#   runtime  FROM scratch, i.e. an empty filesystem, into which /rootfs is
#            copied. Contains no shell, no package manager, no coreutils, no
#            files other than the ones the rootfs stage selected. A final
#            RUN imports the application inside this image to prove the
#            file set is complete.
#
# Base image: Wolfi (https://wolfi.dev), Chainguard's container-only glibc
# distribution. It is chosen over Garden Linux because it rebuilds glibc,
# OpenSSL and friends within days of an upstream release, so the runtime
# image carries upstream versions that vulnerability scanners recognise as
# fixed without needing distribution backport data (Garden Linux ships
# glibc 2.42 with backports that scanners unaware of Garden Linux do not
# credit). wolfi-base is free and needs no registry account.
#
# Version pins: Wolfi is a rolling distribution with only a "latest" tag, so
# the base image is pinned by digest (WOLFI_BASE_DIGEST); the packages apk
# installs on top are the newest in the Wolfi repository at build time, and
# the glibc version check below fails the build if that ever regresses
# below GLIBC_MIN. PYTHON_VERSION picks the source tarball; the ADD below
# carries the SHA-256 of the tarball it downloads, so a version bump means
# changing the ARG and the checksum together.

ARG WOLFI_BASE_DIGEST=sha256:1d95114038f76513a9ace6fca107d5582b08c65981f81f61cb56bf7fd2ef216d

# --- Stage 1: builder ---------------------------------------------------------
FROM cgr.dev/chainguard/wolfi-base:latest@${WOLFI_BASE_DIGEST} AS builder

ARG PYTHON_VERSION=3.14.7
ARG GLIBC_MIN=2.44

# Toolchain and development headers for the CPython build:
#   build-base             gcc, binutils (strip, readelf), make, pkgconf and
#                          the C library headers (glibc-dev)
#   glibc-dev>=2.44        Wolfi carries several glibc streams side by side;
#                          this makes apk pick the headers of the 2.44 stream
#                          the base image runs on, not an older one
#   linux-headers          kernel headers some stdlib modules probe for
#   openssl-dev            OpenSSL headers, for the ssl and hashlib modules
#   zlib-dev               zlib headers, for the zlib module
#   bzip2-dev, xz-dev      bzip2 / xz headers, for the bz2 and lzma modules
#   libffi-dev             libffi headers, for the _ctypes module. Unlike
#                          Garden Linux, Wolfi ships them, so libffi is no
#                          longer built from source here; the runtime gets
#                          Wolfi's libffi.so.8 through the library closure
#                          and it is tracked in the apk database like every
#                          other library
#   ca-certificates-bundle, tzdata   copied into the runtime image later
#                          (TLS roots, time zone database for zoneinfo)
#   coreutils, findutils, gawk   GNU versions of cp, find, xargs and awk;
#                          the rootfs stage relies on GNU cp --parents and
#                          the base image only has busybox
# The last line asserts the glibc the image runs on: the dynamic loader
# reports its version, which must be at least GLIBC_MIN.
RUN apk add --no-cache \
      build-base "glibc-dev>=${GLIBC_MIN}" linux-headers \
      openssl-dev zlib-dev bzip2-dev xz-dev libffi-dev \
      ca-certificates-bundle tzdata \
      coreutils findutils gawk \
  && v="$(/usr/lib/ld-linux-*.so.* --version | sed -n '1s/.*version \([0-9.]*\).*/\1/p')" \
  && echo "glibc ${v}" \
  && [ "$(printf '%s\n%s\n' "${GLIBC_MIN}" "${v}" | sort -V | head -1)" = "${GLIBC_MIN}" ] \
  || { echo "glibc ${v} is older than ${GLIBC_MIN}"; exit 1; }

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
#   --with-openssl=/usr           use Wolfi's OpenSSL
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
# libffi is found through pkg-config (pkgconf comes with build-base).
# CPython's default build has none of these hardening flags; they apply to
# the interpreter and to every stdlib extension module. The trim step below
# asserts the result.
# The interpreter binary is statically linked against libpython (there is
# no libpython3.14.so); its only runtime library dependencies are libc and
# libm.
ADD --checksum=sha256:62859805f6fdf25e2bcbf3fa3217801e1996887ca33e6a2af80674bdfa2dbe07 \
    https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz /src/
RUN cd /src && tar xzf Python-${PYTHON_VERSION}.tgz && cd Python-${PYTHON_VERSION} \
  && printf '%s\n' '*disabled*' _dbm _gdbm _sqlite3 _tkinter readline _curses _curses_panel \
       > Modules/Setup.local \
  && CFLAGS="-fstack-clash-protection" LDFLAGS="-Wl,-z,relro -Wl,-z,now" \
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
# interpreter and on _ctypes: a GNU_RELRO program header together with
# BIND_NOW in the dynamic section means full RELRO (the segment alone is
# partial RELRO, which leaves the GOT entries for library functions
# writable); an undefined __stack_chk_fail means stack canaries are compiled
# in; a __*_chk import (__memcpy_chk, __snprintf_chk, ...) means
# _FORTIFY_SOURCE took effect.
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
# 1. Directory skeleton with the merged-/usr layout of the builder. In Wolfi
#    /lib, /lib64, /bin and /sbin are symlinks into /usr, and /usr/lib64 is
#    a symlink to /usr/lib; every one of those symlinks is copied as is, so
#    that the loader path the interpreter binary names,
#    /lib64/ld-linux-x86-64.so.2, and the library directory the loader
#    searches, /usr/lib, resolve to the same files as in the builder.
# 2. Shared-library closure. The dynamic loader is run in trace mode
#    (ld.so --list, which is what the ldd script does; Wolfi does not
#    install ldd by default) over the interpreter binary and every .so
#    under /opt/python and the venv. Its output lists, per file, the
#    libraries the loader would map, as either
#        libssl.so.3 => /usr/lib/libssl.so.3 (0x...)
#    or, for the loader itself,
#        /lib64/ld-linux-x86-64.so.2 (0x...)
#    A library the loader cannot find prints "=> not found"; the build stops
#    there and shows the file that needs it, because a library missing from
#    the closure would surface only when that extension is first imported.
#    A file the loader cannot process at all, or a symbol-version mismatch
#    ("version GLIBC_2.44 not found"), is reported on stderr with a
#    non-zero exit instead; that also stops the build, with the loader's
#    message.
#    The awk picks the resolved paths out of both line shapes; paths inside
#    /app and /opt/python are skipped because those trees are copied whole
#    below. cp --parents -L copies each library to the same path under
#    /rootfs, dereferencing symlinks so the runtime gets real files.
# 3. libgcc_s.so.1 is added by hand: glibc loads it with dlopen for thread
#    cancellation and C++ exception unwinding, so the trace never lists it.
#    The list of copied libraries is kept in /tmp/libs.txt for step 7.
# 4. Whole trees: the interpreter, /etc/ssl (CA bundle, and OpenSSL's
#    compiled-in default directory on Wolfi) and the time zone database.
#    cp -a keeps symlinks as symlinks.
# 5. The venv, renamed from .venv to venv, and the application source and
#    config. The venv's bin/python is a symlink to /opt/python/bin/python3.14,
#    which resolves because /opt/python is copied to the same path.
# 6. /etc/passwd and /etc/group with the root and appuser entries so uid/gid
#    5678 resolve to a name, /etc/nsswitch.conf naming the "files" and
#    "dns" backends, which are compiled into glibc, so no libnss_* files
#    are needed (Wolfi's own nsswitch.conf uses "compat" for passwd and
#    group, a backend that lives in a separate libnss_compat.so.2 and is
#    therefore not copied), and a world-writable /tmp for tempfile.
# 7. Metadata for vulnerability scanners and SBOM tools. A scratch image has
#    no apk database, so Trivy, Grype and Syft would report no OS packages
#    and the Wolfi libraries copied in step 2 and 3 would go unscanned.
#    Each copied library is mapped to the package that owns it with
#    apk info -W (tried on the path the loader printed and on its
#    symlink-resolved form); a library no package owns stops the build.
#    The stanza of each package is copied from the builder's package
#    database, /lib/apk/db/installed, into the same file under /rootfs; the
#    file is at /usr/lib/apk/db/installed on disk, /lib being a symlink,
#    which is where the scanners look on Wolfi. /etc/os-release tells them
#    which distribution the versions belong to. A package is listed in full
#    even if only one of its files is in the image, so findings can concern
#    files that are not there; that errs on the safe side. CPython is
#    compiled here, belongs to no package and is not listed; it is tracked
#    through PYTHON_VERSION above.
FROM builder AS rootfs
RUN set -eu \
  && mkdir -p /rootfs/usr/lib /rootfs/usr/bin /rootfs/etc /rootfs/app \
  && for d in /lib /lib64 /bin /sbin /usr/lib64 /usr/sbin; do \
       if [ -L "$d" ]; then cp -a "$d" "/rootfs$d"; fi; \
     done \
  && LD="$(find /usr/lib -maxdepth 1 -name 'ld-linux-*.so.*' -type f | head -1)" \
  && { echo /opt/python/bin/python3.14; find /opt/python /app/.venv -name '*.so*' -type f; } \
     | while read -r f; do \
         out="$("$LD" --list "$f" 2>&1)" \
           || { echo "failed to trace $f:" >&2; echo "$out" >&2; exit 1; }; \
         echo "$out"; \
       done > /tmp/ldd.out \
  && if grep -B1 'not found' /tmp/ldd.out; then echo 'unresolved shared libraries'; exit 1; fi \
  && awk '$2 == "=>" && $3 ~ /^\// { print $3 } $1 ~ /^\// && $2 ~ /^\(0x/ { print $1 }' /tmp/ldd.out \
     | grep -vE '^/(app|opt/python)/' \
     | sort -u > /tmp/libs.txt \
  && find /usr/lib -maxdepth 1 -name libgcc_s.so.1 -print -quit >> /tmp/libs.txt \
  && while read -r lib; do cp --parents -L "$lib" /rootfs; done < /tmp/libs.txt \
  && while read -r lib; do \
       pkg="$(apk info -W "$lib" 2>/dev/null | sed -n 's/.* is owned by //p')"; \
       [ -n "$pkg" ] || pkg="$(apk info -W "$(readlink -f "$lib")" 2>/dev/null | sed -n 's/.* is owned by //p')"; \
       [ -n "$pkg" ] || { echo "no package owns $lib" >&2; exit 1; }; \
       echo "$pkg" | sed -E 's/-[^-]+-r[0-9]+$//'; \
     done < /tmp/libs.txt | sort -u > /tmp/pkgs.txt \
  && test -s /tmp/pkgs.txt \
  && mkdir -p /rootfs/usr/lib/apk/db \
  && while read -r pkg; do \
       awk -v RS= -v ORS='\n\n' -v p="$pkg" \
         '{ n = split($0, L, "\n"); for (i = 1; i <= n; i++) if (L[i] == "P:" p) { print; break } }' \
         /lib/apk/db/installed >> /rootfs/usr/lib/apk/db/installed; \
       grep -q "^P:$pkg\$" /rootfs/usr/lib/apk/db/installed || { echo "no db stanza for $pkg" >&2; exit 1; }; \
     done < /tmp/pkgs.txt \
  && cp -L /etc/os-release /rootfs/etc/os-release \
  && cp -a --parents /opt/python /etc/ssl /usr/share/zoneinfo /rootfs \
  && cp -a /app/.venv /rootfs/app/venv \
  && cp -a /app/src /app/config /rootfs/app/ \
  && printf 'root:x:0:0:root:/root:/sbin/nologin\nappuser:x:5678:5678::/nonexistent:/sbin/nologin\n' > /rootfs/etc/passwd \
  && printf 'root:x:0:\nappuser:x:5678:\n' > /rootfs/etc/group \
  && printf 'passwd: files\ngroup: files\nhosts: files dns\n' > /rootfs/etc/nsswitch.conf \
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
