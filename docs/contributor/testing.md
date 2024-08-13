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

The blackbox tests are executed using GitHub Actions and consists of multiple steps.

### Setup

- examples deployed on a cluster
- using Gardener cluster
- is set-up by hand
- here is the configuration of the cluster <--configuration only in private repo?-->
- action first cleans the cluster
- then deploys the examples

### Execution

For more information about the blackbox testing framework and how to execute them, refer to the [Blackbox Testing](../../tests/blackbox/evaluation/README.md) document.


