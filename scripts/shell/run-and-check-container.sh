#!/usr/bin/env bash

# This script runs the given image in a docker container and checks that it's working correctly

# Error handling.
set -o nounset  # treat unset variables as an error and exit immediately.
set -o errexit  # exit immediately when a command fails.
set -E          # needs to be set if we want the ERR trap
set -o pipefail # prevents errors in a pipeline from being masked

# Define the image name and optional container name
IMAGE_NAME="$1"
CONTAINER_NAME="$2"
CHECK_INTERVAL=5  # seconds between checks
TIMEOUT=30        # total timeout in seconds

# Define a cleanup function
cleanup() {
    echo "Cleaning up container:"
    docker rm -f "$CONTAINER_NAME" || true
}

# Set up a trap to ensure cleanup happens on exit
trap cleanup EXIT

# Run the Docker container
docker run -d --name "$CONTAINER_NAME" "$IMAGE_NAME"

# Function to check the container status
check_status() {
    docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME"
}

# Initialize elapsed time
elapsed=0

# Repeatedly check the container status until it is "running" or timeout occurs
while [ "$elapsed" -lt "$TIMEOUT" ]; do
    STATUS=$(check_status)
    echo "Check: Container $CONTAINER_NAME status: $STATUS."
    if [ "$STATUS" == "running" ]; then
        echo "Container $CONTAINER_NAME is running."
        exit 0
    fi
    sleep $CHECK_INTERVAL
    elapsed=$((elapsed + CHECK_INTERVAL))
done

# If we reach here, the container did not reach the "running" state within the timeout
echo "Container $CONTAINER_NAME did not start properly within $TIMEOUT seconds. Final status: $STATUS"
exit 1