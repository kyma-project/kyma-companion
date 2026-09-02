#!/usr/bin/env bash
# Fails if poetry.lock is out of sync with pyproject.toml. Run lock-fix to regenerate.
set -euo pipefail

poetry check --lock
