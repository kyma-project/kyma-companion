#!/usr/bin/env bash
# Approve all pending e2e environment gates for a PR.
# Usage: ./scripts/shell/approve-integration-gates.sh <pr-number> [repo]
# Example: ./scripts/shell/approve-integration-gates.sh 1265
# Example: ./scripts/shell/approve-integration-gates.sh 1265 kyma-project/kyma-companion

set -euo pipefail

PR_NUMBER="${1:?Usage: $0 <pr-number> [repo]}"
REPO="${2:-kyma-project/kyma-companion}"

echo "Approving e2e gates for PR #${PR_NUMBER} in ${REPO}..."

# Get all workflow runs for this PR
run_ids=$(gh api "repos/${REPO}/actions/runs" \
  --jq ".workflow_runs[] | select(.pull_requests[].number == ${PR_NUMBER}) | .id" 2>/dev/null || \
  gh pr checks "${PR_NUMBER}" --repo "${REPO}" --json databaseId --jq '.[].databaseId' 2>/dev/null)

if [ -z "$run_ids" ]; then
  echo "No workflow runs found for PR #${PR_NUMBER}"
  exit 1
fi

approved=0
for run_id in $run_ids; do
  pending=$(gh api "repos/${REPO}/actions/runs/${run_id}/pending_deployments" 2>/dev/null || echo "[]")
  env_ids=$(echo "$pending" | jq -r '.[].environment.id' 2>/dev/null || echo "")
  if [ -n "$env_ids" ]; then
    for env_id in $env_ids; do
      env_name=$(echo "$pending" | jq -r --arg id "$env_id" '.[] | select(.environment.id == ($id | tonumber)) | .environment.name')
      can_approve=$(echo "$pending" | jq -r --arg id "$env_id" '.[] | select(.environment.id == ($id | tonumber)) | .current_user_can_approve')
      if [ "$can_approve" = "true" ]; then
        gh api --method POST "repos/${REPO}/actions/runs/${run_id}/pending_deployments" \
          --input - <<EOF
{"environment_ids":[${env_id}],"state":"approved","comment":"Approved via approve-integration-gates.sh"}
EOF
        echo "  Approved environment '${env_name}' on run ${run_id}"
        approved=$((approved + 1))
      else
        echo "  Skipping environment '${env_name}' on run ${run_id} (cannot approve)"
      fi
    done
  fi
done

echo "Done. Approved ${approved} gate(s)."
