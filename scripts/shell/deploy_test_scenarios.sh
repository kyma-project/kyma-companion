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

# Define base directory
base_dir="tests/data/evaluation/namespace-scoped"

# Arrays to track missing and failed scripts
missing_deploy_scripts=()
failed_deploy_scripts=()

## Functions declaration

check_directory_exists() {
  # Check if directory exists
  if [ ! -d "$base_dir" ]; then
    echo "Error: Directory $base_dir does not exist."
    exit 1
  fi
}

deploy_test_cases() {
  # Iterate over directories in base_dir
  for folder in "$base_dir"/*; do
  if [ -d "$folder" ]; then # Check if it's a directory
  folder_name=$(basename "$folder")
  echo "# $folder_name #"
  echo "Checking test-case folder: $folder_name"

  # Path to the deploy.sh file
  deploy_script="$folder/deploy.sh"

  # Check if deploy.sh exists
  if [ -f "$deploy_script" ]; then
  echo "Executing deploy.sh in $folder_name"
  # Change to the directory to ensure relative paths work
  cd "$folder"
  # Run the deploy script. Change permissions if necessary
  if ! ./deploy.sh; then
  # Record failed execution
  failed_deploy_scripts+=("$folder_name")
  fi
  # Change back to the original directory
  cd -
  else
  # If the deploy.sh is not found
  echo "No deploy.sh found in $folder"
  missing_deploy_scripts+=("$folder_name")
  fi
  fi
  done
}

# Final report
final_report() {
  echo "#### Deployment Summary: ####"
  if [ ${#missing_deploy_scripts[@]} -eq 0 ] && [ ${#failed_deploy_scripts[@]} -eq 0 ]; then
  echo "All test-cases were successfully deployed."
  else
  if [ ${#missing_deploy_scripts[@]} -gt 0 ]; then
  echo "## Missing ##"
  echo "Missing deploy.sh in directories: ${missing_deploy_scripts[*]}"
  fi
  if [ ${#failed_deploy_scripts[@]} -gt 0 ]; then
  echo "## Failed ##"
  echo "Failed to execute deploy.sh in directories: ${failed_deploy_scripts[*]}"
  fi
  fi
}

## Main Script

echo "#### Deploying all test-cases in $base_dir... ####"

# Check if the directory exists
check_directory_exists

# Deploy all test-cases
deploy_test_cases

# Final report
final_report