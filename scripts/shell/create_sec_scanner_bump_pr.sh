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
#   GH_TOKEN                      - GitHub token for GitHub CLI.
#   GIT_EMAIL                     - Email setting for PR to be created.
#   GIT_NAME                      - User name setting for PR to be created.
#   REPOSITORY_FULL_NAME          - Repository name including owner name e.g. kyma-project/kyma-companion.
#   BUMP_SEC_SCANNERS_BRANCH_NAME - branch with updated sec-scanners-config.

TAG=$1
TARGET_BRANCH=${2:-main}

# add changed files to stage
git add sec-scanners-config.yaml

# stash staged changes
git stash push --staged

# pass changes to branch created from TARGET_BRANCH
git checkout --force -B ${TARGET_BRANCH} refs/remotes/origin/${TARGET_BRANCH}
git checkout -B ${BUMP_SEC_SCANNERS_BRANCH_NAME}

# apply stashed changes
git stash apply
git add sec-scanners-config.yaml

# configure git
git config --global user.email ${GIT_EMAIL}
git config --global user.name ${GIT_NAME}

# commit and push changes
git commit -m "Bump sec-scanners-config.yaml to ${TAG} on branch ${TARGET_BRANCH}"
git remote set-url origin https://x-access-token:${GH_TOKEN}@github.com/${REPOSITORY_FULL_NAME}.git
git push --set-upstream origin ${BUMP_SEC_SCANNERS_BRANCH_NAME} -f

#create PR
pr_link=$(gh pr create -B ${TARGET_BRANCH} --title "chore: bump sec-scanners-config.yaml to ${TAG} on branch ${TARGET_BRANCH}" --body "" | tail -n 1)

pr_number=$(echo "$pr_link" | awk -F'/' '{print $NF}')

# NOTE: make sure that this script only echo the id of the PR.
# It should not echo any other information e.g. debug logs/status messages.
echo "$pr_number"
