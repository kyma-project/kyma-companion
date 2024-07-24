#!/usr/bin/env bash

##############################################################################
# NOTE: This script is used in the GitHub Actions workflow.
# Make sure any changes are compatible with the existing workflows.
##############################################################################

# This script returns the id of the draft release

# standard bash error handling
set -o nounset  # treat unset variables as an error and exit immediately.
set -o errexit  # exit immediately when a command fails.
set -E          # needs to be set if we want the ERR trap
set -o pipefail # prevents errors in a pipeline from being masked

# Required env variables:
#   GITHUB_TOKEN                  - GitHub token for GitHub CLI (It will be used to create release)
#   REPOSITORY_FULL_NAME          - Repository name including owner name e.g. kyma-project/kyma-companion.
#   RELEASE_TAG                   - release tag

# check if any published release exists for the specified release tag.
echo "****************************************************************************************"
git_release_api="https://api.github.com/repos/${REPOSITORY_FULL_NAME}/releases/tags/${RELEASE_TAG}"
echo "Checking for existing published release with tag ${RELEASE_TAG} using API: ${git_release_api}."
existing_releases=$(curl -sL \
                      -H "Accept: application/vnd.github+json" \
                      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
                      -H "X-GitHub-Api-Version: 2022-11-28" \
                      "${git_release_api}")


if [ $(echo "$existing_releases" | jq -r '.status') == "404" ]; then
  echo "No published release exists."
else
  echo "Error: Release for this tag ${RELEASE_TAG} already exists."
  echo "$existing_releases" | jq
  exit 1
fi

# check if any draft release exists for the specified release tag.
echo "****************************************************************************************"
git_list_release_api="https://api.github.com/repos/${REPOSITORY_FULL_NAME}/releases"
releases=$(curl -sL \
                    -H "Accept: application/vnd.github+json" \
                    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
                    -H "X-GitHub-Api-Version: 2022-11-28" \
                    "${git_list_release_api}")

existing_drafts=$(echo "${releases}" | jq -r ".[] | select(.tag_name == \"${RELEASE_TAG}\") | .html_url")
# check if existing_drafts is not empty.
if [ -n "${existing_drafts}" ]; then
  echo "Error: Draft release(s) for this tag ${RELEASE_TAG} already exists."
  echo "Release(s):"
  echo "${existing_drafts}"
  echo "[User Action Required] Please delete the existing draft release(s) before creating a new one."
  exit 1
fi

# create a new draft release for the specified release tag.
echo "****************************************************************************************"
GITHUB_URL=https://api.github.com/repos/${REPOSITORY_FULL_NAME}
GITHUB_AUTH_HEADER="Authorization: Bearer ${GITHUB_TOKEN}"

echo "Creating a draft release for tag ${RELEASE_TAG}..."
# it will create a draft release for the specified release tag.
JSON_PAYLOAD=$(jq -n \
  --arg tag_name "$RELEASE_TAG" \
  --arg name "$RELEASE_TAG" \
  '{
    "tag_name": $tag_name,
    "name": $name,
    "draft": true,
    "generate_release_notes": true
  }')

CURL_RESPONSE=$(curl -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "${GITHUB_AUTH_HEADER}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  ${GITHUB_URL}/releases \
  -d "$JSON_PAYLOAD")

# NOTE: make sure that this script only echo the id of the draft release.
# It should not echo any other information e.g. debug logs/status messages.
release_id=$(echo "${CURL_RESPONSE}" | jq -r ".id")
echo "${release_id}" > release_id.txt
echo "Draft release created with id: ${release_id}"