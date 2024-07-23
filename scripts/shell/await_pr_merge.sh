#!/usr/bin/env bash

##############################################################################
# NOTE: This script is used in the GitHub Actions workflow.
# Make sure any changes are compatible with the existing workflows.
##############################################################################

# standard bash error handling
set -o nounset  # treat unset variables as an error and exit immediately.
set -o errexit  # exit immediately when a command fails.
set -E          # needs to be set if we want the ERR trap
set -o pipefail # prevents errors in a pipeline from being masked

# Required env variables:
#   REPOSITORY_FULL_NAME  - Repository name including owner name e.g. kyma-project/kyma-companion.
#   PR_NUMBER             - Number of the PR with the changes to be merged.

# wait until the PR is merged.
until [ $(gh pr view ${PR_NUMBER} --json mergedAt | jq -r '.mergedAt') != "null" ]; do
  echo "Waiting for https://github.com/${REPOSITORY_FULL_NAME}/pull/${PR_NUMBER} to be merged..."
  sleep 30
done

echo "The PR: ${PR_NUMBER} was merged at: $(gh pr view ${PR_NUMBER} --json mergedAt | jq -r '.mergedAt')"
