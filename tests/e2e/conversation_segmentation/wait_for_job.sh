#!/usr/bin/env bash

set -euo pipefail

namespace="$1"
job="$2"
timeout_seconds="$3"
deadline=$((SECONDS + timeout_seconds))

while ((SECONDS < deadline)); do
  complete="$(kubectl get job "$job" -n "$namespace" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}')"
  failed="$(kubectl get job "$job" -n "$namespace" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}')"
  if [[ "$complete" == "True" ]]; then
    echo "job_status=complete completed_jobs=1 failed_jobs=0"
    exit 0
  fi
  if [[ "$failed" == "True" ]]; then
    echo "job_status=failed completed_jobs=0 failed_jobs=1"
    exit 1
  fi
  sleep 10
done

echo "job_status=timeout completed_jobs=0 failed_jobs=0"
exit 1
