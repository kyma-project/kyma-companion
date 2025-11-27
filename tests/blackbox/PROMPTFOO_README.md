# Promptfoo Blackbox Evaluation Tests

This directory contains the Promptfoo-based blackbox evaluation tests for Kyma Companion. These tests validate the end-to-end behavior of the Companion API by testing real scenarios against a live cluster.

## Overview

**Promptfoo** is an open-source LLM testing framework that provides:
- Declarative YAML test configuration
- Mix of deterministic and LLM-based assertions
- Built-in caching and cost tracking
- Snapshot/baseline testing
- CI/CD integration

## Directory Structure

```
tests/blackbox/
├── .promptfoorc.yaml          # Main Promptfoo configuration
├── package.json                # Node.js dependencies
├── tests/                      # Promptfoo test scenarios (YAML)
│   ├── 15_nginx_oom.yaml
│   ├── 19_question_what_is_kyma.yaml
│   └── ...
├── src/
│   └── companion_provider.js   # Custom provider for Companion API
├── scripts/
│   └── convert_to_promptfoo.py # Migration script from scenario.yml
├── output/                     # Test results (gitignored)
├── snapshots/                  # Baseline snapshots (optional)
└── data/test-cases/            # Original scenario.yml files (for reference)
```

## Prerequisites

1. **Node.js 18+** installed
2. **Companion API** running and accessible
3. **Kubernetes cluster** with test resources deployed
4. **Environment variables** configured (see below)

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment Variables

Create a `.env` file or export these variables:

```bash
# Companion API
export COMPANION_API_URL="http://localhost:8000"
export COMPANION_TOKEN="your-auth-token"

# Kubernetes Cluster Access
export TEST_CLUSTER_URL="https://your-cluster-url"
export TEST_CLUSTER_CA_DATA="base64-encoded-ca-cert"
export TEST_CLUSTER_AUTH_TOKEN="your-k8s-token"

# Azure OpenAI (for LLM-based assertions)
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com"
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4"
```

## Running Tests

### Run All Tests

```bash
npm test
```

This will:
1. Load all test files from `tests/*.yaml`
2. Execute tests sequentially (to prevent race conditions)
3. Generate results in `output/` directory

### Run Specific Test

```bash
npx promptfoo eval -c tests/15_nginx_oom.yaml
```

### View Results

```bash
npm run test:report
```

Opens an interactive web UI to review test results.

### Watch Mode (Development)

```bash
npm run test:watch
```

Auto-reruns tests when files change.

## Test Structure

Each test file (e.g., `tests/15_nginx_oom.yaml`) contains:

### 1. Test Metadata

```yaml
description: The nginx Deployment is configured with insufficient memory
```

### 2. Provider Configuration

```yaml
providers:
  - id: file://./src/companion_provider.js
    config:
      apiUrl: ${COMPANION_API_URL}
      resource:
        kind: Deployment
        api_version: apps/v1
        name: nginx
        namespace: test-deployment-15
```

### 3. Prompts (User Queries)

```yaml
prompts:
  - "Why is the Deployment not available?"
```

### 4. Assertions

Mix of deterministic and LLM-based checks:

```yaml
assert:
  # Deterministic: Must contain keywords
  - type: icontains-any
    value: [memory, insufficient, OOM]
    required: true
    description: Must mention memory-related issues

  # Deterministic: Must contain code block
  - type: contains
    value: '```'
    required: false
    description: Should provide YAML example

  # Semantic: LLM-based evaluation
  - type: llm-rubric
    value: |
      Evaluate if the response identifies insufficient memory as root cause.

      Score 1.0 if: Clearly states insufficient memory is the problem
      Score 0.5 if: Mentions memory but not as root cause
      Score 0.0 if: Does not identify memory issue
    threshold: 0.7
    required: true
    description: Semantic validation
```

### 5. Deployment Metadata

```yaml
metadata:
  deploy:
    script: ./data/test-cases/15_nginx_oom/deploy.sh
  undeploy:
    script: ./data/test-cases/15_nginx_oom/undeploy.sh
```

## Assertion Types

### Deterministic Assertions (Fast, Reliable)

- `contains`: Exact substring match
- `icontains`: Case-insensitive substring match
- `contains-any`: Contains any of the listed strings
- `icontains-any`: Case-insensitive any match
- `regex`: Regular expression match
- `is-json`: Valid JSON format
- `javascript`: Custom JavaScript validation function

### LLM-Based Assertions (Semantic)

- `llm-rubric`: Custom scoring criteria using LLM
- `similar`: Embedding similarity comparison
- `factuality`: Checks adherence to facts
- `answer-relevance`: Output relates to query

### Performance Assertions

- `latency`: Response time below threshold
- `cost`: Evaluation cost below threshold

## Converting Legacy Scenarios

To convert existing `scenario.yml` files to Promptfoo format:

```bash
# Convert all scenarios
poetry run python scripts/convert_to_promptfoo.py

# Convert specific scenario
poetry run python scripts/convert_to_promptfoo.py --scenario 15_nginx_oom
```

The script will:
1. Parse the `scenario.yml` file
2. Extract keywords for deterministic checks
3. Convert expectations to Promptfoo assertions
4. Generate LLM rubrics with scoring criteria
5. Output YAML file to `tests/` directory

## Tips for Writing Reliable Tests

### 1. Use Deterministic Checks First

Always start with fast, deterministic assertions before LLM-based ones:

```yaml
assert:
  # First: Fast keyword check
  - type: icontains-any
    value: [memory, oom]
    required: true

  # Then: Semantic validation
  - type: llm-rubric
    value: "Validates correct diagnosis"
    required: true
```

### 2. Clear LLM Rubrics

Provide explicit scoring criteria with examples:

```yaml
- type: llm-rubric
  value: |
    Score 1.0 if: [specific condition]
    Score 0.5 if: [partial condition]
    Score 0.0 if: [failure condition]
  threshold: 0.7  # Higher threshold for clearer criteria
```

### 3. Required vs Optional

- `required: true` - Test fails if assertion fails
- `required: false` - Assertion tracked but doesn't fail test

Use required sparingly for critical checks only.

### 4. Threshold Selection

- `0.5` - Lenient (use for ambiguous criteria)
- `0.7` - Standard (use for clear criteria)
- `0.8+` - Strict (use for must-have conditions)

## Debugging Failed Tests

### 1. Check Output Directory

```bash
ls -la output/
cat output/latest-results.json
```

### 2. View Detailed Report

```bash
npm run test:report
```

### 3. Run Single Test with Debug

```bash
DEBUG=* npx promptfoo eval -c tests/15_nginx_oom.yaml
```

### 4. Inspect Companion Provider Logs

The provider logs conversation IDs, API calls, and errors.

## CI/CD Integration

Tests run automatically in GitHub Actions:

```yaml
- name: Install Promptfoo
  working-directory: tests/blackbox
  run: npm install

- name: Run Promptfoo tests
  working-directory: tests/blackbox
  env:
    COMPANION_API_URL: ${{ secrets.COMPANION_API_URL }}
    # ... other env vars
  run: npm test
```

See `.github/workflows/blackbox-tests.yml` for full configuration.

## Troubleshooting

### Tests hang or timeout

- Check `COMPANION_API_URL` is correct
- Verify cluster resources are deployed
- Increase timeout in provider if needed

### Authentication errors

- Verify `COMPANION_TOKEN` is valid
- Check `TEST_CLUSTER_AUTH_TOKEN` has proper permissions
- Ensure `TEST_CLUSTER_CA_DATA` is correct base64-encoded cert

### LLM-based assertions fail inconsistently

- This is expected due to LLM non-determinism
- Consider:
  - Adding more deterministic checks
  - Lowering threshold slightly
  - Improving rubric clarity with examples
  - Using `similar` (embedding) instead of `llm-rubric`

### Provider errors

- Check `src/companion_provider.js` logs
- Verify SSE stream parsing is working
- Test Companion API directly with curl

## Migration Status

**Phase 1: Proof of Concept** ✅
- [x] 3 scenarios converted (nginx_oom, what_is_kyma, apirule_broken)
- [x] Custom Companion provider implemented
- [x] Conversion script created

**Phase 2: Full Migration** (In Progress)
- [ ] 21 remaining scenarios converted
- [ ] CI/CD pipeline updated
- [ ] Team training completed

**Phase 3: Advanced Features** (Planned)
- [ ] Embedding-based similarity evaluation
- [ ] Snapshot/regression testing
- [ ] LangSmith integration (production monitoring)

## Resources

- [Promptfoo Documentation](https://www.promptfoo.dev/docs/intro/)
- [Promptfoo Assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/)
- [Custom Providers Guide](https://www.promptfoo.dev/docs/providers/custom/)
- [GitHub Repository](https://github.com/promptfoo/promptfoo)

## Questions?

See `tests/blackbox/CLAUDE.md` or contact the Kyma Companion team.
