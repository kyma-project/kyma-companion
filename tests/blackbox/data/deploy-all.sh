#!/bin/bash

# Deploy All Test Cases Script
# This script applies all deployment.yml files from the test-cases directory

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_CASES_DIR="${SCRIPT_DIR}/test-cases"

echo "🚀 Starting deployment of all test cases..."
echo "📂 Test cases directory: ${TEST_CASES_DIR}"
echo

# Check if test-cases directory exists
if [ ! -d "${TEST_CASES_DIR}" ]; then
    echo "❌ Error: test-cases directory not found at ${TEST_CASES_DIR}"
    exit 1
fi

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ Error: kubectl command not found. Please install kubectl first."
    exit 1
fi

# Find all deployment.yml files and apply them
deployment_files=$(find "${TEST_CASES_DIR}" -name "deployment.yml" -type f | sort)

if [ -z "$deployment_files" ]; then
    echo "⚠️  Warning: No deployment.yml files found in ${TEST_CASES_DIR}"
    exit 0
fi

echo "📋 Found $(echo "$deployment_files" | wc -l) deployment files:"
echo "$deployment_files" | sed 's/^/  - /'
echo

# Apply each deployment file
failed_deployments=()
successful_deployments=()

for deployment_file in $deployment_files; do
    test_case=$(basename "$(dirname "$deployment_file")")
    echo "🔧 Deploying test case: ${test_case}"
    echo "   File: ${deployment_file}"

    if kubectl apply -f "${deployment_file}"; then
        echo "✅ Successfully deployed: ${test_case}"
        successful_deployments+=("$test_case")
    else
        echo "❌ Failed to deploy: ${test_case}"
        failed_deployments+=("$test_case")
    fi
    echo
done

# Summary
echo "📊 Deployment Summary:"
echo "✅ Successful: ${#successful_deployments[@]}"
echo "❌ Failed: ${#failed_deployments[@]}"

if [ ${#successful_deployments[@]} -gt 0 ]; then
    echo
    echo "✅ Successfully deployed test cases:"
    printf '  - %s\n' "${successful_deployments[@]}"
fi

if [ ${#failed_deployments[@]} -gt 0 ]; then
    echo
    echo "❌ Failed deployments:"
    printf '  - %s\n' "${failed_deployments[@]}"
    echo
    echo "💡 Tip: Check the error messages above for details on failed deployments"
    exit 1
fi

echo
echo "🎉 All deployments completed successfully!"