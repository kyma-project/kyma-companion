#!/usr/bin/env bash

# Render, run, and privacy-filter one Kubernetes Job in the isolated E2E K3d cluster.
set -euo pipefail

namespace="$1"
manifest="$2"
job="$3"
timeout_seconds="$4"
expected_log_kind="$5"

: "${KUBECONFIG:?KUBECONFIG must point to the isolated E2E kubeconfig}"
: "${EXPECTED_K3D_CONTEXT:?EXPECTED_K3D_CONTEXT is required}"
: "${CI_HELPER:?CI_HELPER is required}"

context="$(kubectl config current-context)"
server="$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')"
if [[ "$context" != "$EXPECTED_K3D_CONTEXT" ]] ||
  [[ ! "$server" =~ ^https://(0\.0\.0\.0|127\.0\.0\.1|localhost):[0-9]+$ ]]; then
  echo "context_guard=failed expected_contexts=1 matching_contexts=0"
  exit 1
fi

rendered_manifest="$(mktemp)"
raw_log="$(mktemp)"
trap 'rm -f "$rendered_manifest" "$raw_log"' EXIT
envsubst < "$manifest" > "$rendered_manifest"
kubectl apply -f "$rendered_manifest" >/dev/null

deadline=$((SECONDS + timeout_seconds))
job_status="timeout"
while ((SECONDS < deadline)); do
  complete="$(kubectl get job "$job" -n "$namespace" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}')"
  failed="$(kubectl get job "$job" -n "$namespace" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}')"
  if [[ "$complete" == "True" ]]; then
    job_status="complete"
    break
  fi
  if [[ "$failed" == "True" ]]; then
    job_status="failed"
    break
  fi
  sleep 10
done

if ! kubectl logs -n "$namespace" "job/$job" > "$raw_log" 2>/dev/null; then
  echo "job_status=log-retrieval-failed completed_jobs=0 failed_jobs=1"
  exit 1
fi
python3 "$CI_HELPER" sanitize-logs --input "$raw_log" --expected-kind "$expected_log_kind"

if [[ "$job_status" == "complete" ]]; then
  echo "job_status=complete completed_jobs=1 failed_jobs=0"
  exit 0
fi
if [[ "$job_status" == "failed" ]]; then
  echo "job_status=failed completed_jobs=0 failed_jobs=1"
  exit 1
fi
echo "job_status=timeout completed_jobs=0 failed_jobs=0"
exit 1
