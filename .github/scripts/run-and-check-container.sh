#!/usr/bin/env bash

# This script runs the given image in a docker container and checks that it's working correctly

# Error handling.
set -o nounset  # treat unset variables as an error and exit immediately.
set -o errexit  # exit immediately when a command fails.
set -E          # needs to be set if we want the ERR trap
set -o pipefail # prevents errors in a pipeline from being masked

# Check for required arguments
if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <image_name> <container_name>"
  exit 1
fi

# Define the image name and optional container name
IMAGE_NAME="$1"
CONTAINER_NAME="$2"
CHECK_INTERVAL=5  # seconds between checks
CHECK_RETRIES=3   # number of checks

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

# Repeatedly check the container status
for ((i=0; i<CHECK_RETRIES; i++)); do
    STATUS=$(check_status)
    if [ "$STATUS" == "running" ]; then
        echo "Container $CONTAINER_NAME is running."
    else
        echo "Container $CONTAINER_NAME is not running yet. Status: $STATUS. Retrying in $CHECK_INTERVAL seconds..."
    fi
    sleep $CHECK_INTERVAL
done

# Final status check
STATUS=$(check_status)
if [ "$STATUS" == "running" ]; then
    echo "Container $CONTAINER_NAME is running and stable."
else
    echo "Container $CONTAINER_NAME failed to start properly. Status: $STATUS"
    exit 1
fi