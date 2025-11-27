/**
 * Validate Promptfoo test YAML files
 * Usage: node scripts/validate_test_yaml.js [test-file.yaml]
 */

const fs = require('fs');
const yaml = require('js-yaml');
const path = require('path');

const testFile = process.argv[2] || 'tests/15_nginx_oom.yaml';
const testPath = path.resolve(testFile);

console.log(`🧪 Validating test file: ${testFile}\n`);

try {
  // Test 1: File exists
  console.log('✓ Test 1: File exists');
  if (!fs.existsSync(testPath)) {
    throw new Error(`File not found: ${testPath}`);
  }
  console.log(`  Found: ${testPath}`);

  // Test 2: Valid YAML syntax
  console.log('\n✓ Test 2: Valid YAML syntax');
  const content = fs.readFileSync(testPath, 'utf8');
  const test = yaml.load(content);
  console.log('  YAML parses successfully');

  // Test 3: Required fields
  console.log('\n✓ Test 3: Required fields');
  const requiredFields = ['description', 'providers', 'prompts', 'assert'];
  for (const field of requiredFields) {
    if (!(field in test)) {
      throw new Error(`Missing required field: ${field}`);
    }
    console.log(`  - ${field}: ✓`);
  }

  // Test 4: Provider configuration
  console.log('\n✓ Test 4: Provider configuration');
  if (!Array.isArray(test.providers) || test.providers.length === 0) {
    throw new Error('providers must be a non-empty array');
  }
  const provider = test.providers[0];
  console.log(`  - Provider ID: ${provider.id}`);
  if (provider.config && provider.config.resource) {
    const res = provider.config.resource;
    console.log(`  - Resource kind: ${res.kind || 'N/A'}`);
    console.log(`  - Resource name: ${res.name || 'N/A'}`);
    console.log(`  - Resource namespace: ${res.namespace || 'N/A'}`);
  }

  // Test 5: Prompts
  console.log('\n✓ Test 5: Prompts');
  if (!Array.isArray(test.prompts) || test.prompts.length === 0) {
    throw new Error('prompts must be a non-empty array');
  }
  console.log(`  - Number of prompts: ${test.prompts.length}`);
  test.prompts.forEach((prompt, idx) => {
    console.log(`  - Prompt ${idx + 1}: "${prompt.substring(0, 50)}${prompt.length > 50 ? '...' : ''}"`);
  });

  // Test 6: Assertions
  console.log('\n✓ Test 6: Assertions');
  if (!Array.isArray(test.assert) || test.assert.length === 0) {
    throw new Error('assert must be a non-empty array');
  }
  console.log(`  - Number of assertions: ${test.assert.length}`);

  // Count assertion types
  const assertionTypes = {};
  const requiredCount = test.assert.filter(a => a.required === true).length;
  const optionalCount = test.assert.filter(a => a.required === false).length;

  test.assert.forEach(assertion => {
    assertionTypes[assertion.type] = (assertionTypes[assertion.type] || 0) + 1;
  });

  console.log('  - Assertion types:');
  Object.entries(assertionTypes).forEach(([type, count]) => {
    console.log(`    • ${type}: ${count}`);
  });
  console.log(`  - Required: ${requiredCount}, Optional: ${optionalCount}`);

  // Test 7: Assertion structure
  console.log('\n✓ Test 7: Assertion structure');
  test.assert.forEach((assertion, idx) => {
    if (!assertion.type) {
      throw new Error(`Assertion ${idx + 1} missing 'type' field`);
    }
    if (assertion.required === undefined) {
      console.log(`  ⚠️ Warning: Assertion ${idx + 1} missing 'required' field (defaults to true)`);
    }
  });
  console.log('  All assertions have required fields');

  // Test 8: LLM rubric quality
  console.log('\n✓ Test 8: LLM rubric quality');
  const rubrics = test.assert.filter(a => a.type === 'llm-rubric');
  if (rubrics.length > 0) {
    console.log(`  - Found ${rubrics.length} LLM rubrics`);
    rubrics.forEach((rubric, idx) => {
      const hasScoring = rubric.value && (
        rubric.value.includes('Score 1.0') ||
        rubric.value.includes('Score 0.5') ||
        rubric.value.includes('Score 0.0')
      );
      if (hasScoring) {
        console.log(`    • Rubric ${idx + 1}: Has scoring criteria ✓`);
      } else {
        console.log(`    • Rubric ${idx + 1}: ⚠️ Missing scoring criteria`);
      }
      if (rubric.threshold) {
        console.log(`      Threshold: ${rubric.threshold}`);
      }
    });
  } else {
    console.log('  - No LLM rubrics found (using only deterministic checks)');
  }

  console.log('\n✅ Test file validation passed!');
  console.log('\n📊 Summary:');
  console.log(`  - Description: "${test.description.substring(0, 60)}${test.description.length > 60 ? '...' : ''}"`);
  console.log(`  - Prompts: ${test.prompts.length}`);
  console.log(`  - Assertions: ${test.assert.length} (${requiredCount} required, ${optionalCount} optional)`);
  console.log(`  - Deployment scripts: ${test.metadata && (test.metadata.deploy || test.metadata.undeploy) ? '✓' : '✗'}`);

} catch (error) {
  console.error('\n❌ Test file validation failed:');
  console.error(`   ${error.message}`);
  if (error.stack && process.env.DEBUG) {
    console.error(`\n   Stack trace:`);
    console.error(error.stack);
  }
  process.exit(1);
}
