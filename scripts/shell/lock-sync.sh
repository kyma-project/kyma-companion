#!/usr/bin/env bash
# Regenerates poetry.lock to match pyproject.toml.
set -euo pipefail

poetry lock
