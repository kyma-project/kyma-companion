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
base_dir="tests/blackbox/data/test-cases"

# Arrays to track missing and failed scripts
missing_undeploy_scripts=()
failed_undeploy_scripts=()

## Functions declaration

check_directory_exists() {
  # Check if directory exists
  if [ ! -d "$base_dir" ]; then
    echo "Error: Directory $base_dir does not exist."
    exit 1
  fi
}

undeploy_test_cases() {
  # Iterate over directories in base_dir
  for folder in "$base_dir"/*; do
    if [ -d "$folder" ]; then # Check if it's a directory
      folder_name=$(basename "$folder")
      echo "# $folder_name #"
      echo "Checking test-case folder: $folder_name"

      # Path to the undeploy.sh file
      undeploy_script="$folder/undeploy.sh"

      # Check if deploy.sh exists
      if [ -f "$undeploy_script" ]; then
        # Add execute permissions if necessary
        if [ ! -x "$undeploy_script" ]; then
          echo "Adding execute permissions to undeploy.sh in $folder_name"
          if ! chmod +x "$undeploy_script"; then
            echo "Failed to add execute permissions to $undeploy_script"
            failed_undeploy_scripts+=("$folder_name")
            continue
          fi
        fi
        echo "Executing undeploy.sh in $folder_name"
        if ! (cd "$folder" && ./undeploy.sh); then
          failed_undeploy_scripts+=("$folder_name")
        fi
      else
        echo "No undeploy.sh found in $folder"
        missing_undeploy_scripts+=("$folder_name")
      fi
    fi
  done
}

# Final report
final_report() {
  echo "#### Undeployment Summary: ####"
  if [ ${#missing_undeploy_scripts[@]} -eq 0 ] && [ ${#failed_undeploy_scripts[@]} -eq 0 ]; then
    echo "All test-cases were successfully undeployed."
  else
    if [ ${#missing_undeploy_scripts[@]} -gt 0 ]; then
      echo "## Missing ##"
      echo "Missing undeploy.sh in directories: ${missing_undeploy_scripts[*]}"
      exit 1
    fi
    if [ ${#failed_undeploy_scripts[@]} -gt 0 ]; then
      echo "## Failed ##"
      echo "Failed to execute undeploy.sh in directories: ${failed_undeploy_scripts[*]}"
      exit 1
    fi
  fi
  exit 0
}

## Main Script

echo "#### Undeploying all test-cases in $base_dir... ####"

# Check if the directory exists
check_directory_exists

# Deploy all test-cases
undeploy_test_cases

# Final report
final_report
