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
# - release tag - mandatory
#
# Example usage: ./check_release_tag.sh 2.1.0

# regular expression to match major.minor.patch format
regex="^[0-9]+\.[0-9]+\.[0-9]+$"

# check if the input string is a valid release tag.
release_tag="$1"

echo "****************************"
echo "checking if release tag: $release_tag is correctly formatted..."
if [[ $release_tag =~ $regex ]]; then
    echo "Release tag: $release_tag is valid!"
else
    echo "Error: Invalid release tag: $release_tag. Correct format: <major>.<minor>.<patch>"
    exit 1
fi

# extract the major and minor versions.
echo "****************************"
echo "extracting major, minor and patch versions from release tag: $release_tag"
major=$(echo "$release_tag" | cut -d. -f1)
minor=$(echo "$release_tag" | cut -d. -f2)

# check if the release branch exists.
branch_name="release-$major.$minor"
echo "checking if the release branch: $branch_name  exists..."
if git show-ref --verify --quiet refs/remotes/origin/"${branch_name}"; then
    echo "Branch: $branch_name exists!"
else
    echo "Error: Branch: $branch_name does not exist. Please create the branch before creating the release."
    exit 1
fi

exit 0
