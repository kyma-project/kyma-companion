#!/usr/bin/env bash
# Ensures poetry.lock is in sync with pyproject.toml; regenerates it if not.
set -euo pipefail

poetry check --lock || poetry lock
