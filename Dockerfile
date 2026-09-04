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
  && rm -f /app/.venv/bin/pip* /app/.venv/bin/wheel /app/.venv/bin/easy_install* \
  && rm -rf /app/.venv/docs \
  && find /app/.venv -path "*/rdflib/plugins/stores/berkeleydb.py" -delete \
  && find /app/.venv -path "*/rdflib*.dist-info/METADATA" -exec sed -i '/berkeleydb/Id' {} \; \
  && find /app/.venv -name "_yaml*.so" -delete

# Runtime stage: clean Garden Linux with Python 3.14 from Debian sid.
FROM ghcr.io/gardenlinux/gardenlinux:2150.9.0
RUN echo "deb https://deb.debian.org/debian sid main" > /etc/apt/sources.list.d/sid.list \
  && printf 'Package: *\nPin: release a=unstable\nPin-Priority: -1\n\nPackage: python3.14 python3.14-minimal libpython3.14 libpython3.14-minimal libpython3.14-stdlib libdb5.3t64 media-types libexpat1\nPin: release a=unstable\nPin-Priority: 900\n' > /etc/apt/preferences.d/sid-pin \
  && apt-get update \
  && apt-get install -y --no-install-recommends python3.14 libstdc++6 \
  && rm -rf /var/lib/apt/lists/* /var/cache/apt /usr/share/doc /usr/share/man \
  && dpkg --purge --force-depends libdb5.3t64 2>/dev/null || true \
  && dpkg --purge --force-depends libsqlite3-0 2>/dev/null || true \
  && dpkg --purge --force-depends libncurses6 libncursesw6 libtinfo6 2>/dev/null || true \
  && dpkg --purge --force-depends libsystemd0 2>/dev/null || true \
  && groupadd --gid 5678 appuser \
  && useradd --uid 5678 --gid appuser --shell /bin/sh --no-create-home appuser \
  && rm -f /usr/bin/perl /usr/bin/perl5* /usr/bin/bashbug \
  && find /usr/lib -maxdepth 3 -type d \( -name "perl-base" -o -name "perl5" \) -exec rm -rf {} + 2>/dev/null || true \
  && rm -f /bin/bash /usr/bin/bash \
  && rm -f /usr/bin/openssl /usr/bin/c_rehash \
  && rm -f /usr/bin/apt /usr/bin/apt-get /usr/bin/apt-cache /usr/bin/apt-mark \
     /usr/bin/apt-cdrom /usr/bin/apt-config /usr/bin/apt-sortpkgs /usr/bin/apt-extracttemplates \
  && rm -f /usr/bin/su /usr/bin/chsh /usr/bin/chfn /usr/bin/passwd /usr/bin/gpasswd \
     /usr/bin/chage /usr/bin/expiry \
  && rm -f /usr/bin/login /usr/sbin/sulogin /usr/sbin/runuser \
  && rm -f /usr/sbin/useradd /usr/sbin/userdel /usr/sbin/usermod \
     /usr/sbin/groupadd /usr/sbin/groupdel /usr/sbin/groupmod /usr/sbin/newusers \
  && rm -f /usr/bin/dpkg /usr/bin/dpkg-deb /usr/bin/dpkg-divert /usr/bin/dpkg-query \
     /usr/bin/dpkg-split /usr/bin/dpkg-statoverride /usr/bin/dpkg-trigger \
     /usr/bin/dpkg-realpath /usr/bin/dpkg-maintscript-helper \
     /usr/bin/debconf /usr/bin/debconf-apt-progress /usr/bin/debconf-communicate \
     /usr/bin/debconf-copydb /usr/bin/debconf-escape /usr/bin/debconf-set-selections \
     /usr/bin/debconf-show \
  && rm -f /usr/bin/pdb3.14 /usr/bin/pydoc3.14 /usr/bin/pygettext3.14 \
  && rm -f /usr/bin/sqv \
  && rm -f /usr/bin/ldd /usr/bin/pldd \
  && rm -f /usr/bin/mount /usr/bin/umount /usr/sbin/losetup /usr/sbin/swapoff \
     /usr/sbin/swapon /usr/sbin/mkswap /usr/sbin/blkdiscard /usr/sbin/blkid \
     /usr/sbin/blockdev /usr/sbin/fsck /usr/sbin/mkfs /usr/sbin/fsfreeze \
     /usr/sbin/fstrim /usr/sbin/wipefs /usr/sbin/zramctl /usr/sbin/swaplabel \
     /usr/bin/mountpoint /usr/bin/findmnt /usr/bin/lsblk /usr/bin/partx \
  && rm -f /usr/bin/tar /usr/bin/gzip /usr/bin/gunzip /usr/bin/gzexe \
     /usr/bin/zcat /usr/bin/zcmp /usr/bin/zdiff /usr/bin/zegrep /usr/bin/zfgrep \
     /usr/bin/zforce /usr/bin/zgrep /usr/bin/zless /usr/bin/zmore /usr/bin/znew \
  && rm -f /usr/bin/cmp /usr/bin/diff /usr/bin/diff3 /usr/bin/sdiff \
  && rm -f /usr/bin/sensible-browser /usr/bin/sensible-editor /usr/bin/sensible-terminal \
     /usr/bin/sensible-pager /usr/bin/select-editor \
  && rm -f /usr/bin/dmesg /usr/bin/lscpu /usr/bin/lsipc /usr/bin/lslocks \
     /usr/bin/lsns /usr/bin/nsenter /usr/bin/unshare /usr/bin/setarch \
     /usr/bin/linux32 /usr/bin/linux64 /usr/bin/setpriv /usr/bin/chroot \
  && rm -f /usr/sbin/agetty /usr/sbin/getty /usr/sbin/killall5 \
     /usr/sbin/ldconfig /usr/sbin/iconvconfig \
     /usr/sbin/start-stop-daemon /usr/sbin/invoke-rc.d /usr/sbin/service \
     /usr/sbin/update-rc.d /usr/sbin/update-passwd /usr/sbin/update-shells \
     /usr/sbin/update-ca-certificates \
     /usr/sbin/shadowconfig /usr/sbin/dpkg-preconfigure /usr/sbin/dpkg-reconfigure \
     /usr/sbin/pam-auth-update /usr/sbin/pam_getenv /usr/sbin/pam_namespace_helper \
     /usr/sbin/pam_timestamp_check \
     /usr/sbin/grpck /usr/sbin/grpconv /usr/sbin/grpunconv \
     /usr/sbin/pwck /usr/sbin/pwconv /usr/sbin/pwunconv /usr/sbin/pwhistory_helper \
     /usr/sbin/vigr /usr/sbin/vipw \
     /usr/sbin/installkernel \
     /usr/sbin/rtcwake /usr/sbin/readprofile \
     /usr/sbin/rmt /usr/sbin/rmt-tar /usr/sbin/tarcat \
     /usr/sbin/nologin /usr/sbin/unix_chkpwd /usr/sbin/unix_update \
     /usr/sbin/mkhomedir_helper /usr/sbin/add-shell /usr/sbin/remove-shell \
     /usr/sbin/faillock /usr/sbin/findfs /usr/sbin/fstab-decode \
  && rm -f /usr/bin/update-alternatives \
  && rm -f /usr/sbin/chgpasswd /usr/sbin/chpasswd /usr/sbin/zic \
  && rm -f /usr/bin/deb-systemd-helper /usr/bin/deb-systemd-invoke \
  && rm -f /usr/bin/chcon /usr/bin/choom /usr/bin/chrt /usr/bin/runcon \
  && rm -f /usr/bin/ipcmk /usr/bin/ipcrm /usr/bin/ipcs \
  && rm -f /usr/bin/captoinfo /usr/bin/infocmp /usr/bin/infotocap \
     /usr/bin/tic /usr/bin/toe /usr/bin/tput /usr/bin/tset /usr/bin/reset \
     /usr/bin/clear /usr/bin/clear_console /usr/bin/tabs \
  && rm -f /usr/bin/ischroot /usr/bin/savelog /usr/bin/tempfile \
     /usr/bin/run-parts /usr/bin/hardlink \
  && rm -f /usr/bin/mcookie /usr/bin/namei /usr/bin/whereis \
     /usr/bin/which /usr/bin/which.debianutils \
  && rm -f /usr/bin/rbash /usr/bin/localedef \
  && rm -f /usr/bin/taskset /usr/bin/uclampset /usr/bin/prlimit \
     /usr/bin/ionice /usr/bin/setsid /usr/bin/setterm \
  && rm -f /usr/bin/grep /usr/bin/egrep /usr/bin/fgrep \
  && find /usr/lib/python3* -name "_sqlite3*.so" -delete 2>/dev/null || true \
  && find /usr/lib/python3* \( -name "_curses*.so" -o -name "readline*.so" \) -delete 2>/dev/null || true \
  && find /lib /usr/lib -maxdepth 4 \( -name "libsqlite3.so*" -o -name "libncurses*.so*" -o -name "libtinfo*.so*" \) -delete 2>/dev/null || true \
  && find /lib /usr/lib -maxdepth 5 \( -name "libsystemd.so*" -o -name "libsystemd-shared*.so*" \) -delete 2>/dev/null || true \
  && find /usr/share -maxdepth 2 -type d -name "perl*" -exec rm -rf {} + 2>/dev/null || true \
  && find /lib /usr/lib -maxdepth 4 -name "libperl*.so*" -delete 2>/dev/null || true \
  && rm -f \
     /usr/bin/b2sum /usr/bin/base32 /usr/bin/base64 /usr/bin/basename /usr/bin/basenc \
     /usr/bin/cat /usr/bin/chgrp /usr/bin/chmod /usr/bin/chown /usr/bin/cksum \
     /usr/bin/comm /usr/bin/cp /usr/bin/csplit /usr/bin/cut /usr/bin/date \
     /usr/bin/dd /usr/bin/df /usr/bin/dir /usr/bin/dircolors /usr/bin/dirname \
     /usr/bin/du /usr/bin/echo /usr/bin/env /usr/bin/expand /usr/bin/expr \
     /usr/bin/factor /usr/bin/false /usr/bin/fmt /usr/bin/fold /usr/bin/groups \
     /usr/bin/head /usr/bin/hostid /usr/bin/id /usr/bin/install /usr/bin/join \
     /usr/bin/kill /usr/bin/link /usr/bin/ln /usr/bin/logname /usr/bin/ls \
     /usr/bin/md5sum /usr/bin/mkdir /usr/bin/mkfifo /usr/bin/mknod /usr/bin/mktemp \
     /usr/bin/mv /usr/bin/nice /usr/bin/nl /usr/bin/nohup /usr/bin/nproc \
     /usr/bin/numfmt /usr/bin/od /usr/bin/paste /usr/bin/pathchk /usr/bin/pinky \
     /usr/bin/pr /usr/bin/printenv /usr/bin/printf /usr/bin/ptx /usr/bin/pwd \
     /usr/bin/readlink /usr/bin/realpath /usr/bin/seq \
     /usr/bin/sha1sum /usr/bin/sha224sum /usr/bin/sha256sum /usr/bin/sha384sum \
     /usr/bin/sha512sum /usr/bin/shred /usr/bin/shuf /usr/bin/sleep /usr/bin/sort \
     /usr/bin/split /usr/bin/stat /usr/bin/stdbuf /usr/bin/stty /usr/bin/sum \
     /usr/bin/sync /usr/bin/tac /usr/bin/tail /usr/bin/tee /usr/bin/test \
     /usr/bin/timeout /usr/bin/touch /usr/bin/tr /usr/bin/true /usr/bin/truncate \
     /usr/bin/tsort /usr/bin/tty /usr/bin/uname /usr/bin/unexpand /usr/bin/uniq \
     /usr/bin/unlink /usr/bin/uptime /usr/bin/users /usr/bin/vdir /usr/bin/wc \
     /usr/bin/who /usr/bin/whoami /usr/bin/yes \
  && rm -rf /var/lib/dpkg /var/cache/debconf /etc/apt \
  && rm -f /usr/bin/rm

WORKDIR /app

COPY --chown=appuser:appuser --from=builder /app/.venv ./venv
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser config ./config

USER appuser

ENV PATH="/app/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
CMD ["python3.14", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
