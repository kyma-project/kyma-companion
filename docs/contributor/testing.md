# Testing

## Testing Levels


| Test suite | Testing level | Purpose                                                                                                                                              |
|------------|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| Unit       | Unit          | This test suite tests the units in isolation. It assesses the implementation correctness of the unit's business logic.                               |
| Blackbox   | Improvement   | This test suite measures the improvement of the Kyma Companion. It tests the Kyma Companion as a whole without peering into it's internal structure. |

## Unit Tests

To run the unit tests, the following command must be executed:

```bash
poetry poe test
```

The unit tests are automatically executed on any PR using the [GitHub Actions workflow](https://github.com/kyma-project/kyma-companion/actions/workflows/unit-test.yaml).

Further information about the setup of Poetry and Poe the Poet can be found in the general [README](../../README.md).

## Blackbox Tests

The blackbox tests are set up and executed in two different steps.

### Setup

The test cases are deployed on a Gardener cluster. The cluster is set up by hand and is not deleted unless necessary.

Once the cluster is set up, the [Setup Gardener Test Cluster](https://github.com/kyma-project/kyma-companion/actions/workflows/setup-test-cluster.yaml) GitHub Action can be manually triggered.
The action automatically connects to the Gardener cluster, cleans it and deploys all the examples in the [tests/data/evaluation/namespace-scoped](../../tests/data/evaluation/namespace-scoped) directory.

The GitHub Action provides a summary of any missing scenarios or ones that failed to be deployed. These need to be fixed within their own `deploy.sh` script.

### Execution

For more information about the blackbox testing framework and how to execute them, refer to the [Blackbox Testing](../../tests/blackbox/evaluation/README.md) document.


