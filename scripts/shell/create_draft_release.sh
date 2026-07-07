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

# fetch the latest published release tag to build the changelog link.
echo "Fetching the latest published release tag..."
latest_release_response=$(curl -sL \
  -H "Accept: application/vnd.github+json" \
  -H "${GITHUB_AUTH_HEADER}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "${GITHUB_URL}/releases/latest")
latest_release_status=$(echo "${latest_release_response}" | jq -r '.status // empty')
if [ "${latest_release_status}" == "404" ]; then
  echo "No previous release found."
  CHANGELOG_LINK="https://github.com/${REPOSITORY_FULL_NAME}/releases/tag/${RELEASE_TAG}"
elif [ -n "${latest_release_status}" ]; then
  echo "Error: Failed to fetch latest release (status: ${latest_release_status})."
  echo "${latest_release_response}" | jq
  exit 1
else
  PREVIOUS_TAG=$(echo "${latest_release_response}" | jq -r '.tag_name // empty')
  echo "Previous release tag: ${PREVIOUS_TAG}"
  CHANGELOG_LINK="https://github.com/${REPOSITORY_FULL_NAME}/compare/${PREVIOUS_TAG}...${RELEASE_TAG}"
fi

# collect merged PRs since the previous release and group by conventional commit prefix.
FEATURES=""
FIXES=""
OTHER=""
if [ -n "${PREVIOUS_TAG:-}" ]; then
  echo "Fetching commits between ${PREVIOUS_TAG} and ${RELEASE_TAG}..."
  compare_response=$(curl -sL \
    -H "Accept: application/vnd.github+json" \
    -H "${GITHUB_AUTH_HEADER}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "${GITHUB_URL}/compare/${PREVIOUS_TAG}...${RELEASE_TAG}")
  compare_status=$(echo "${compare_response}" | jq -r '.status // empty')
  if echo "${compare_status}" | grep -qE '^[0-9]+$'; then
    echo "Warning: Failed to fetch compare (status: ${compare_status}). Sections will be empty."
  else
    # extract first line of each commit message and group by conventional commit prefix.
    while IFS= read -r msg; do
      # skip merge commits and bump commits.
      if echo "${msg}" | grep -qE '^(Merge |Bump )'; then
        continue
      fi
      # extract PR number from trailing (#NNN); non-fatal if absent.
      pr_num=$(echo "${msg}" | grep -oE '\(#[0-9]+\)$' | tr -d '()' || true)
      # strip the conventional commit prefix (e.g. "feat: ", "fix(scope): ").
      title=$(echo "${msg}" | sed -E 's/^[a-z]+\([^)]*\): //' | sed -E 's/^[a-z]+: //' | sed -E 's/ \(#[0-9]+\)$//')
      if [ -z "${pr_num}" ]; then
        entry="* ${title}"
      else
        pr_link="[${pr_num}](https://github.com/${REPOSITORY_FULL_NAME}/pull/${pr_num#\#})"
        entry="* ${title} (${pr_link})"
      fi
      prefix=$(echo "${msg}" | grep -oE '^[a-z]+(\([^)]*\))?:' | grep -oE '^[a-z]+' || true)
      case "${prefix}" in
        feat)    FEATURES="${FEATURES}${entry}\n" ;;
        fix|sec) FIXES="${FIXES}${entry}\n" ;;
        *)       OTHER="${OTHER}${entry}\n" ;;
      esac
    done < <(echo "${compare_response}" | jq -r '.commits[] | .commit.message | split("\n")[0]')
  fi
fi

# build the release body using the Kyma release notes template.
RELEASE_BODY="# Release Notes — v${RELEASE_TAG}

## Deprecations/Breaking Changes

## New Features

$(printf '%b' "${FEATURES}")
## Bug Fixes

$(printf '%b' "${FIXES}")
## Other

$(printf '%b' "${OTHER}")
## Full Changelog

Compare changes between versions: [Changelog](${CHANGELOG_LINK})"

echo "Creating a draft release for tag ${RELEASE_TAG}..."
JSON_PAYLOAD=$(jq -n \
  --arg tag_name "$RELEASE_TAG" \
  --arg name "$RELEASE_TAG" \
  --arg body "$RELEASE_BODY" \
  '{
    "tag_name": $tag_name,
    "name": $name,
    "body": $body,
    "draft": true
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
