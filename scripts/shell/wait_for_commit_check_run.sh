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

# This script waits for git check to completed.
# There are two types of git statuses i.e. check runs and statuses.
# For more information, see # https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks#types-of-status-checks-on-github

# Required env variables:
# - REPOSITORY_FULL_NAME           - Repository name including owner name e.g. kyma-project/kyma-companion.
# - GIT_REF                        - Git reference to check for the check run (i.e. commit sha, branch name or tag name).
# - GIT_CHECK_RUN_NAME             - Name of the git check to wait for.
# - INTERVAL                       - Interval in seconds to wait before check the status again.
# - TIMEOUT                        - Timeout in seconds to wait for the check run to complete before failing.

# echo configs.
echo "REPOSITORY_FULL_NAME: ${REPOSITORY_FULL_NAME}"
echo "GIT_CHECK_RUN_NAME: ${GIT_CHECK_RUN_NAME}"
echo "GIT_REF: ${GIT_REF}"
echo "INTERVAL: ${INTERVAL}"
echo "TIMEOUT: ${TIMEOUT}"

# https://docs.github.com/en/rest/checks/runs?apiVersion=2022-11-28#list-check-runs-for-a-git-reference
checks_uri="/repos/${REPOSITORY_FULL_NAME}/commits/${GIT_REF}/check-runs"
# jq filter to find check run by name.
jq_filter=".check_runs[] | select(.name == \"${GIT_CHECK_RUN_NAME}\")"

# wait for check run to complete.
start_time=$(date +%s)
while true
do
  # check timeout.
  current_time=$(date +%s)
  elapsed=$((current_time - start_time))
  echo "Elapsed time: ${elapsed} seconds"
  if [ $((elapsed)) -ge $((TIMEOUT)) ]; then
    echo "Error: Timeout reached!"
    exit 1
  fi

  # get check run from github API.
  echo "****************************************************************************************"
  echo "Checking for check run: \"${GIT_CHECK_RUN_NAME}\" from ${checks_uri}..."
  check_json=$(gh api -q "${jq_filter}" -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" "${checks_uri}")

  # if check run not found.
  if [ -z "${check_json}" ]; then
    echo "Check run not found. Waiting for ${INTERVAL} seconds..."
    sleep ${INTERVAL}
    continue
  fi

  # extract status and conclusion from check run.
  status=$(echo $check_json | jq -r ".status")
  conclusion=$(echo $check_json | jq -r ".conclusion")
  echo "Status: $status, Conclusion: $conclusion"

  # check if check run is not completed.
  if [ "$status" != "completed" ]; then
      echo "Check run not completed. Waiting for ${INTERVAL} seconds..."
      sleep ${INTERVAL}
      continue
  fi

  # check success.
  if [ "$conclusion" == "success" ]; then
      echo "Check run completed with success."
      exit 0
  fi

  # check failure.
  # https://docs.github.com/en/rest/checks/runs?apiVersion=2022-11-28#list-check-runs-for-a-git-reference
  case "$conclusion" in
    failure|neutral|cancelled|skipped|timed_out)
      echo "Check run failed. Conclusion: ${conclusion}"
      exit 1
      ;;
  esac

  # wait for interal before checking again.
  sleep ${INTERVAL}
done
