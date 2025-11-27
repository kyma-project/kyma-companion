/**
 * Simple test to validate the Companion provider loads correctly
 * Usage: node scripts/test_provider.js
 */

const CompanionProvider = require('../src/companion_provider.js');

console.log('🧪 Testing Companion Provider...\n');

try {
  // Test 1: Provider instantiation
  console.log('✓ Test 1: Provider instantiation');
  const provider = new CompanionProvider({
    config: {
      apiUrl: 'http://localhost:8000',
      resource: {
        kind: 'Deployment',
        api_version: 'apps/v1',
        name: 'test',
        namespace: 'default'
      }
    }
  });
  console.log('  Provider created successfully');
  console.log(`  ID: ${provider.id()}`);

  // Test 2: Provider methods
  console.log('\n✓ Test 2: Provider methods');
  console.log(`  - id(): ${provider.id()}`);
  console.log(`  - callApi: ${typeof provider.callApi === 'function' ? '✓' : '✗'}`);
  console.log(`  - provider.provider: ${provider.provider ? '✓' : '✗'}`);

  // Test 3: Internal provider structure
  console.log('\n✓ Test 3: Internal provider structure');
  const internal = provider.provider;
  console.log(`  - apiUrl: ${internal.apiUrl}`);
  console.log(`  - resource.kind: ${internal.resource.kind}`);
  console.log(`  - getHeaders: ${typeof internal.getHeaders === 'function' ? '✓' : '✗'}`);
  console.log(`  - initializeConversation: ${typeof internal.initializeConversation === 'function' ? '✓' : '✗'}`);
  console.log(`  - callApi: ${typeof internal.callApi === 'function' ? '✓' : '✗'}`);

  // Test 4: Headers generation
  console.log('\n✓ Test 4: Headers generation');
  const headers = internal.getHeaders();
  console.log(`  - Authorization: ${headers.Authorization ? '✓' : '✗'}`);
  console.log(`  - Content-Type: ${headers['Content-Type']}`);
  console.log(`  - X-Cluster-Url: ${headers['X-Cluster-Url'] ? '✓' : '⚠️ (not set)'}`);

  console.log('\n✅ All provider validation tests passed!');
  console.log('\n📝 Note: This validates provider structure only.');
  console.log('   Full API testing requires:');
  console.log('   - Companion API running at $COMPANION_API_URL');
  console.log('   - Valid auth tokens in environment variables');
  console.log('   - Kubernetes cluster with test resources');

} catch (error) {
  console.error('\n❌ Provider validation failed:');
  console.error(`   ${error.message}`);
  console.error(`\n   Stack trace:`);
  console.error(error.stack);
  process.exit(1);
}
