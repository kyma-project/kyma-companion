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
  && rm -rf /app/.venv/docs

# Runtime stage: clean Garden Linux with Python 3.14 from Debian sid.
FROM ghcr.io/gardenlinux/gardenlinux:2150.9.0
RUN echo "deb https://deb.debian.org/debian sid main" > /etc/apt/sources.list.d/sid.list \
  && printf 'Package: *\nPin: release a=unstable\nPin-Priority: -1\n\nPackage: python3.14 python3.14-minimal libpython3.14 libpython3.14-minimal libpython3.14-stdlib libdb5.3t64 media-types libexpat1\nPin: release a=unstable\nPin-Priority: 900\n' > /etc/apt/preferences.d/sid-pin \
  && apt-get update \
  && apt-get install -y --no-install-recommends python3.14 libstdc++6 \
  && rm -rf /var/lib/apt/lists/* /var/cache/apt /usr/share/doc /usr/share/man \
  && groupadd --gid 5678 appuser \
  && useradd --uid 5678 --gid appuser --shell /bin/sh --no-create-home appuser \
  && rm -f /usr/bin/perl /usr/bin/perl5* /usr/bin/bashbug \
  && rm -rf /usr/lib/aarch64-linux-gnu/perl-base /usr/lib/aarch64-linux-gnu/perl5 \
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
     /usr/bin/ionice /usr/bin/setsid /usr/bin/setterm

WORKDIR /app

COPY --from=builder /app/.venv ./venv
COPY src ./src
COPY config ./config

RUN chown -R appuser:appuser /app

USER appuser

ENV PATH="/app/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
CMD ["python3.14", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
