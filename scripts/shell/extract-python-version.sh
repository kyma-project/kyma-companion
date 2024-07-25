#!/usr/bin/env bash

# This script gets the python version from the pyproject.toml file

# Error handling.
set -o nounset  # treat unset variables as an error and exit immediately.
set -o errexit  # exit immediately when a command fails.
set -E          # needs to be set if we want the ERR trap
set -o pipefail # prevents errors in a pipeline from being masked

echo "Getting Python version from pyproject.toml"

# Extract Python version from pyproject.toml and set it as a GitHub Actions environment variable
PYTHON_VERSION=$(grep '^python = ' pyproject.toml | sed 's/python = \"//g' | sed 's/\"//g')
echo "PYTHON_VERSION=${PYTHON_VERSION}" >> "$GITHUB_ENV"