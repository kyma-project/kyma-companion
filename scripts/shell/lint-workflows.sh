#!/usr/bin/env bash

# Runs actionlint against all GitHub Actions workflow files.

set -o nounset
set -o errexit
set -E
set -o pipefail

if ! command -v actionlint &>/dev/null; then
  echo "ERROR: actionlint not found. Install it with: brew install actionlint"
  exit 1
fi

actionlint .github/workflows/*.yml .github/workflows/*.yaml
