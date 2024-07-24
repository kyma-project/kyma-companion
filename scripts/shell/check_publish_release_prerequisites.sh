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
# - RELEASE_TAG - release tag
#
# This script requires the following env variables:
# - IMAGE_NAME - container image name without tag.
#
# Example usage:
# export IMAGE_NAME="europe-docker.pkg.dev/kyma-project/prod/kyma-companion"
# ./check_publish_release_prerequisites.sh 1.0.0

# get the release tag from input arguments.
export RELEASE_TAG=${1}

# check if container image exists.
PROTOCOL=docker://
if [ $(skopeo list-tags ${PROTOCOL}${IMAGE_NAME} | jq '.Tags|any(. == env.RELEASE_TAG)') != "true" ]; then
    echo "Error: image do not exist: ${IMAGE_NAME}:${RELEASE_TAG}"
    exit 1
fi
echo "image ${IMAGE_NAME}:${RELEASE_TAG} exists"

# check version bump in sec-scanners-config.yaml.
ssc_rc_tag=$(yq '.rc-tag' sec-scanners-config.yaml)
if [[ ${ssc_rc_tag} != ${RELEASE_TAG} ]]; then
    echo "Error: rc-tag in sec-scanners-config.yaml is not correct. Expected: ${RELEASE_TAG}, Got: ${ssc_rc_tag}"
    exit 1
fi
echo "rc-tag in sec-scanners-config.yaml is correct: ${ssc_rc_tag}"
