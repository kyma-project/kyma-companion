#!/bin/bash
# Runs deploy.sh for each test case directory, one at a time.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

failed=()

for deploy_script in "$SCRIPT_DIR"/*/deploy.sh; do
    test_case_dir="$(dirname "$deploy_script")"
    test_case_name="$(basename "$test_case_dir")"

    echo ""
    echo "========================================="
    echo "Deploying: $test_case_name"
    echo "========================================="

    if (cd "$test_case_dir" && bash deploy.sh); then
        echo "✅  $test_case_name — OK"
    else
        echo "❌  $test_case_name — FAILED (exit $?)"
        failed+=("$test_case_name")
    fi
done

echo ""
echo "========================================="
if [ ${#failed[@]} -eq 0 ]; then
    echo "All test cases deployed successfully."
else
    echo "The following test cases FAILED:"
    for name in "${failed[@]}"; do
        echo "  - $name"
    done
    exit 1
fi
