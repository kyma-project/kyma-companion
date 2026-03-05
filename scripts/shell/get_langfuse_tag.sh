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


TAG_FILE="${TAG_FILE:-./tmp/langfuse_tag.version}"

if [[ ! -f "$DOCKERFILE" ]]; then
  echo "Dockerfile not found: $DOCKERFILE" >&2
  exit 1
fi

from_line=$(grep -m1 '^FROM' "$DOCKERFILE" || true)
if [[ -z "$from_line" ]]; then
  echo "No FROM line found in $DOCKERFILE" >&2
  exit 1
fi

image_ref=${from_line#FROM }
tag_part=${image_ref#*:}
if [[ "$tag_part" == "$image_ref" || -z "$tag_part" ]]; then
  echo "No tag found in first FROM line" >&2
  exit 1
fi

mkdir -p "$(dirname "$TAG_FILE")"
echo "$tag_part" > "$TAG_FILE"
echo "Tag $tag_part extracted from $DOCKERFILE and saved to $TAG_FILE!"
