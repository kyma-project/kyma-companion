#!/usr/bin/env bash

##############################################################################
# NOTE: This script is used in the GitHub Actions workflow.
# Make sure any changes are compatible with the existing workflows.
##############################################################################

# This script has the following arguments:
# - filename of file to be created (mandatory)
# - release tag (mandatory)
# ./create_scan_config image temp_scan_config.yaml tag
# - use when bumping the config on the main branch

# standard bash error handling
set -o nounset  # treat unset variables as an error and exit immediately.
set -o errexit  # exit immediately when a command fails.
set -E          # needs to be set if we want the ERR trap
set -o pipefail # prevents errors in a pipeline from being maskedPORT=5001

FILENAME=${1}
TAG=${2}

echo "Creating security scan configuration file:"

cat <<EOF | tee ${FILENAME}
module-name: kyma-companion
kind: kcp
bdba:
  # kyma-companion
  - europe-docker.pkg.dev/kyma-project/prod/kyma-companion:${TAG}
  # doc-indexer
  - europe-docker.pkg.dev/kyma-project/prod/kyma-companion-doc-indexer:${TAG}
  # langfuse
  - europe-docker.pkg.dev/kyma-project/prod/external/langfuse/langfuse-worker:3.63.0
  - europe-docker.pkg.dev/kyma-project/prod/external/langfuse/langfuse:3.63.0
  - europe-docker.pkg.dev/kyma-project/prod/external/bitnami/clickhouse:24.12.3-debian-12-r1
  - europe-docker.pkg.dev/kyma-project/prod/external/bitnami/zookeeper:3.9.3-debian-12-r3
checkmarx-one:
  preset: python-default
  exclude:
    - "tests/**"
    - "**/tests/**"
mend:
  language: python
  exclude:
    - "tests/**"
    - "**/tests/**"
EOF
