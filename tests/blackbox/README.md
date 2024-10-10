# Black Box Testing Framework

The black box testing framework provides evaluation tests for Kyma Companion and validation of large language models (LLMs) as assessments for tests. The evaluation tests measure the improvement of Kyma Companion, while validation finds the best model to verify the test scenarios.

## Testing Data

The data we use for both `Validation` and `Evaluation` is stored in `kyma-companion/tests/blackbox/data/namespace-scoped`. Located in that directory are several subdirectories named after the testing scenario they represent. In each of these you will find:
- `deploy.sh`, a shell script that helps deploy the scenario in a Kubernetes cluster.
- `deployment.yml`, a Kubernetes manifest used by the `deploy.sh` shell script.
- `scenario.yml`, a file that contains all data for running the `Evaluation` test against the scenario.
- `validation.yml`, a file that contains all data for running the `Validation` test against the scenario.

## Evaluation

To measure any improvement of the Kyma Companion, we need a black box test. This test is referred to as an evaluation test.

For the evaluation, we need to define a set of scenarios, with each scenario further divided into expectations. Kyma
Companion is prompted through its endpoints to evaluate the given scenario. In the evaluation, the response is compared
to the given expectations. This comparison will either result in a match or no match. However, as different expectations
can be more or less complex, this boolean value is multiplied by a complexity factor. Every expectation must be
evaluated multiple times so the idempotency performance of Kyma Companion can be calculated.

Refer to the [Evaluation](./evaluation.md) documentation for more details.


## Validation

An LLM assesses the test scenarios' actual value against the expected value. To find the best model to judge, we need to validate several LLMs with mock data.

Refer to the [Validation](./validation.md) documentation for more details.
