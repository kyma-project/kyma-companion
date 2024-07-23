#!/usr/bin/env bash

# This script runs the given image in a docker container and checks that it's working correctly

# Error handling.
set -o nounset  # treat unset variables as an error and exit immediately.
set -o errexit  # exit immediately when a command fails.
set -E          # needs to be set if we want the ERR trap
set -o pipefail # prevents errors in a pipeline from being masked

# Define the image name and optional container name
IMAGE_NAME="$1"
CONTAINER_NAME="${2:-$(basename "$IMAGE_NAME")}"

# Run the Docker container
docker run -d --name "$CONTAINER_NAME" "$IMAGE_NAME"

# Check if the container is running
STATUS=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME")

if [ "$STATUS" == "running" ]; then
    echo "Container $CONTAINER_NAME is running."
else
    echo "Container $CONTAINER_NAME is not running. Status: $STATUS"
    docker rm "$CONTAINER_NAME"
    exit 1
fi

# Clean up the container
docker rm "$CONTAINER_NAME"