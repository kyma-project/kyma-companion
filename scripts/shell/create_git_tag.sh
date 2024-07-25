#!/usr/bin/env bash

##############################################################################
# NOTE: This script is used in the GitHub Actions workflow.
# Make sure any changes are compatible with the existing workflows.
##############################################################################

# standard bash error handling
set -o nounset  # treat unset variables as an error and exit immediately.
set -o errexit  # exit immediately when a command fails.
set -E          # must be set if you want the ERR trap
set -o pipefail # prevents errors in a pipeline from being masked

# This script requires the following arguments:
# - release tag - mandatory
#
# Example usage: ./create_git_tag.sh 2.1.0

# get the release tag from arguments.
release_tag="$1"

echo "Checking if tag ${release_tag} already exists."
if [ $(git tag -l "${release_tag}") ]; then
  echo "Release tag ${release_tag} already exists. Checking if the SHA of tag is correct..."

  tag_sha=$(git rev-list -n 1 "${release_tag}")
  if [ -z "${tag_sha}" ]; then
    echo "Error: Unable to get SHA of the existing tag: ${release_tag}"
    exit 1
  fi

  branch_sha=$(git rev-parse HEAD)
  if [ -z "${branch_sha}" ]; then
    echo "Error: Unable to get SHA of HEAD."
    exit 1
  fi

  if [ "${tag_sha}" == "${branch_sha}" ]; then
    echo "Tag (${release_tag}) SHA (${tag_sha}) matches the current branch SHA(${branch_sha}). Skipping tag creation!"
    exit 0
  fi

  echo "Error: Tag (${release_tag}) SHA (${tag_sha}) does not match the current branch SHA (${branch_sha})."
  exit 1
fi

echo "Creating git tag: ${release_tag}"
git tag "${release_tag}"
git push origin "${release_tag}"

exit 0
