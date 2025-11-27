#!/usr/bin/env python3
"""
Convert existing scenario.yml files to Promptfoo test format.

This script reads scenario.yml files from the test-cases directory and
generates corresponding Promptfoo YAML test files.
"""

import argparse
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any


def extract_keywords_from_statement(statement: str) -> List[str]:
    """
    Extract potential keywords from an expectation statement.

    Examples:
    - "mentions 'Kubernetes' or 'k8s'" -> ["Kubernetes", "k8s"]
    - "points out insufficient memory" -> ["insufficient", "memory"]
    """
    keywords = []

    # Extract quoted strings
    quoted = re.findall(r"'([^']+)'", statement)
    keywords.extend(quoted)

    # Extract significant words (nouns, adjectives)
    significant_words = [
        'memory', 'insufficient', 'limit', 'OOM', 'exceeded',
        'error', 'failed', 'problem', 'issue',
        'deployment', 'pod', 'container',
        'kubernetes', 'k8s', 'kyma',
        'managed', 'serverless', 'function',
        'apirule', 'subscription', 'apigateway',
        'rbac', 'permission', 'role',
        'storage', 'volume', 'pvc',
        'probe', 'liveness', 'readiness',
        'image', 'pull', 'registry',
    ]

    statement_lower = statement.lower()
    for word in significant_words:
        if word in statement_lower and word not in [k.lower() for k in keywords]:
            keywords.append(word)

    return keywords[:5]  # Limit to 5 keywords to avoid over-specification


def convert_expectation_to_assertions(expectation: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert a scenario expectation to Promptfoo assertions.

    Returns a list of assertions (deterministic + LLM-based).
    """
    assertions = []
    statement = expectation['statement']
    threshold = expectation.get('threshold', 0.5)
    required = expectation.get('required', True)
    name = expectation.get('name', '')

    # Try to extract deterministic checks from the statement
    keywords = extract_keywords_from_statement(statement)

    # Add keyword check if we found any
    if keywords and len(keywords) >= 2:
        assertions.append({
            'type': 'icontains-any',  # Case-insensitive
            'value': keywords,
            'required': required,
            'description': f'{name}: Must mention relevant keywords'
        })

    # Check for specific patterns in statements

    # Pattern: "mentions X" or "contains X"
    if 'mentions' in statement.lower() or 'contains' in statement.lower():
        # Keywords already extracted above
        pass

    # Pattern: YAML expectations
    if 'yaml' in statement.lower():
        assertions.append({
            'type': 'contains',
            'value': '```',
            'required': required,
            'description': f'{name}: Must contain code block'
        })

    # Pattern: step-by-step guide
    if 'step-by-step' in statement.lower() or 'guide' in statement.lower():
        assertions.append({
            'type': 'javascript',
            'value': '''
            // Check for numbered steps or bullet points
            const hasNumberedSteps = /\\d+\\.\\s/.test(output);
            const hasBulletPoints = /^\\s*[-*]\\s/m.test(output);
            return hasNumberedSteps || hasBulletPoints;
            '''.strip(),
            'required': False,  # Usually optional
            'description': f'{name}: Should contain structured steps'
        })

    # Always add LLM rubric for semantic validation
    # Convert statement to a proper evaluation rubric
    rubric = f"""Evaluate if the response {statement.lower()}.

Score 1.0 if:
- The response clearly and accurately {statement.lower()}
- All relevant information is provided

Score 0.5 if:
- The response {statement.lower().replace('points out', 'mentions').replace('provides', 'includes')} but not clearly
- Some relevant information is missing

Score 0.0 if:
- The response does not {statement.lower().replace('points out', 'mention').replace('provides', 'include')}
- Incorrect or misleading information
"""

    assertions.append({
        'type': 'llm-rubric',
        'value': rubric,
        'threshold': max(threshold, 0.7),  # Increase threshold for clearer criteria
        'required': required,
        'description': f'{name}: Semantic validation'
    })

    return assertions


def convert_scenario(scenario_path: Path, output_dir: Path) -> None:
    """
    Convert a single scenario.yml file to Promptfoo format.
    """
    with open(scenario_path) as f:
        scenario = yaml.safe_load(f)

    test_dir = scenario_path.parent
    test_id = scenario['id']
    test_name = test_dir.name

    print(f"Converting {test_name} ({test_id})...")

    # Process each query in the scenario
    for query_idx, query in enumerate(scenario.get('queries', [])):
        # Build Promptfoo test
        promptfoo_test = {
            'description': scenario['description'],
        }

        # Add provider config with resource information
        if 'resource' in query:
            promptfoo_test['providers'] = [{
                'id': 'file://./src/companion_provider.js',
                'config': {
                    'apiUrl': '${COMPANION_API_URL}',
                    'resource': query['resource']
                }
            }]

        # Add prompt
        promptfoo_test['prompts'] = [query['user_query']]

        # Convert expectations to assertions
        assertions = []
        for exp in query.get('expectations', []):
            exp_assertions = convert_expectation_to_assertions(exp)
            assertions.extend(exp_assertions)

        promptfoo_test['assert'] = assertions

        # Add deployment metadata
        deploy_script = test_dir / 'deploy.sh'
        undeploy_script = test_dir / 'undeploy.sh'

        if deploy_script.exists() or undeploy_script.exists():
            promptfoo_test['metadata'] = {}
            if deploy_script.exists():
                promptfoo_test['metadata']['deploy'] = {
                    'script': f'./data/test-cases/{test_name}/deploy.sh'
                }
            if undeploy_script.exists():
                promptfoo_test['metadata']['undeploy'] = {
                    'script': f'./data/test-cases/{test_name}/undeploy.sh'
                }

        # Write output file
        if len(scenario.get('queries', [])) > 1:
            output_file = output_dir / f"{test_name}_query{query_idx + 1}.yaml"
        else:
            output_file = output_dir / f"{test_name}.yaml"

        with open(output_file, 'w') as f:
            yaml.dump(promptfoo_test, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        print(f"  → Created {output_file.name}")


def main():
    parser = argparse.ArgumentParser(description='Convert scenario.yml files to Promptfoo format')
    parser.add_argument(
        '--scenarios-dir',
        type=Path,
        default=Path('data/test-cases'),
        help='Directory containing test scenario subdirectories'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('tests'),
        help='Output directory for Promptfoo test files'
    )
    parser.add_argument(
        '--scenario',
        type=str,
        help='Convert only a specific scenario (by directory name)'
    )

    args = parser.parse_args()

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Find all scenario.yml files
    if args.scenario:
        scenario_files = [args.scenarios_dir / args.scenario / 'scenario.yml']
    else:
        scenario_files = list(args.scenarios_dir.glob('*/scenario.yml'))

    if not scenario_files:
        print(f"No scenario.yml files found in {args.scenarios_dir}")
        return

    print(f"Found {len(scenario_files)} scenarios to convert\n")

    # Convert each scenario
    for scenario_file in sorted(scenario_files):
        if scenario_file.exists():
            try:
                convert_scenario(scenario_file, args.output_dir)
            except Exception as e:
                print(f"  ✗ Error converting {scenario_file}: {e}")
        else:
            print(f"  ✗ Scenario file not found: {scenario_file}")

    print(f"\n✓ Conversion complete! Output files in {args.output_dir}/")
    print(f"\nNext steps:")
    print(f"  1. Review the generated YAML files in {args.output_dir}/")
    print(f"  2. Run tests: npm test")
    print(f"  3. Refine expectations as needed")


if __name__ == '__main__':
    main()
