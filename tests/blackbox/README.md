# Blackbox Testing Framework

Provides evaluation tests for Kyma Companion and Validation of LLMs as judge for tests. Evaluation tests are used to measure the improvement of Kyma Companion, while validation is used to find the best model to judge the test scenarios.

## Evaluation

To measure any improvement of Kyma Companion, we need a black box test. This test is referred to as an Evaluation test.

For the evaluation, we need to define a set of scenarios, with each scenario further divided into expectations. Kyma
Companion is prompted through its endpoints to evaluate the given scenario. In the Evaluation, the response is compared
to the given expectations. This comparison will either result in a match or no match. However, as different expectations
can be more or less complex, this boolean value is multiplied by a complexity factor. Every expectation must be
evaluated multiple times so the idempotency performance of Kyma Companion can be calculated.

Refer to [Evaluation](./evaluation.md) documentation for more details.


## Validation

A LLM is used to judge the test scenarios actual value against the expected value. To find the best model to judge , we need to validate several LLMs with mock data.

Refer to [Validation](./validation.md) documentation for more details.
