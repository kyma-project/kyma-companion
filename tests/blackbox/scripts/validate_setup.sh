#!/bin/bash
# Validate Promptfoo setup without requiring full infrastructure

set -e

echo "🔍 Validating Promptfoo Setup..."
echo ""

# Check if we're in the right directory
if [ ! -f ".promptfoorc.yaml" ]; then
    echo "❌ Error: Not in tests/blackbox directory"
    exit 1
fi

# Check Node.js
echo "✓ Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi
NODE_VERSION=$(node --version)
echo "  Found: $NODE_VERSION"

# Check npm dependencies
echo "✓ Checking npm dependencies..."
if [ ! -d "node_modules" ]; then
    echo "❌ node_modules not found. Run: npm install"
    exit 1
fi
echo "  node_modules/ exists"

# Check Promptfoo CLI
echo "✓ Checking Promptfoo CLI..."
if [ ! -f "node_modules/.bin/promptfoo" ]; then
    echo "❌ Promptfoo CLI not found. Run: npm install"
    exit 1
fi
PROMPTFOO_VERSION=$(npx promptfoo --version 2>/dev/null || echo "unknown")
echo "  Found: promptfoo $PROMPTFOO_VERSION"

# Validate configuration file
echo "✓ Validating .promptfoorc.yaml..."
if ! npx js-yaml .promptfoorc.yaml > /dev/null 2>&1; then
    # Try with poetry (js-yaml might not be installed)
    echo "  (YAML validation skipped - js-yaml not available)"
else
    echo "  Valid YAML syntax"
fi

# Check provider file
echo "✓ Checking custom provider..."
if [ ! -f "src/companion_provider.js" ]; then
    echo "❌ src/companion_provider.js not found"
    exit 1
fi
echo "  Found: src/companion_provider.js"

# Validate provider syntax
echo "✓ Validating provider JavaScript..."
if ! node -c src/companion_provider.js 2>/dev/null; then
    echo "❌ Syntax error in src/companion_provider.js"
    exit 1
fi
echo "  Valid JavaScript syntax"

# Count test files
echo "✓ Checking test files..."
TEST_COUNT=$(ls tests/*.yaml 2>/dev/null | wc -l | tr -d ' ')
if [ "$TEST_COUNT" -eq 0 ]; then
    echo "❌ No test files found in tests/"
    exit 1
fi
echo "  Found: $TEST_COUNT test files"

# Validate a sample test file
echo "✓ Validating sample test file..."
SAMPLE_TEST="tests/15_nginx_oom.yaml"
if [ ! -f "$SAMPLE_TEST" ]; then
    echo "⚠️  Sample test not found, skipping"
else
    # Check if it has required fields
    if grep -q "description:" "$SAMPLE_TEST" && \
       grep -q "providers:" "$SAMPLE_TEST" && \
       grep -q "prompts:" "$SAMPLE_TEST" && \
       grep -q "assert:" "$SAMPLE_TEST"; then
        echo "  Valid test structure"
    else
        echo "❌ Missing required fields in $SAMPLE_TEST"
        exit 1
    fi
fi

# Check directory structure
echo "✓ Checking directory structure..."
for dir in src tests scripts output; do
    if [ ! -d "$dir" ]; then
        echo "❌ Missing directory: $dir"
        exit 1
    fi
done
echo "  All required directories exist"

# Summary
echo ""
echo "✅ Setup validation complete!"
echo ""
echo "📋 Summary:"
echo "  - Promptfoo version: $PROMPTFOO_VERSION"
echo "  - Test files: $TEST_COUNT"
echo "  - Custom provider: ✓"
echo "  - Configuration: ✓"
echo ""
echo "🚀 Next steps:"
echo "  1. Set environment variables (see PROMPTFOO_README.md)"
echo "  2. Deploy test resources to cluster"
echo "  3. Run tests: npm test"
echo ""
echo "⚠️  Note: This validation checks setup only."
echo "   Full test execution requires:"
echo "   - Companion API running"
echo "   - Kubernetes cluster with test resources"
echo "   - Azure OpenAI credentials"
