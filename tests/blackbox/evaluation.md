# Blackbox Testing Framework

To measure any improvement of Kyma Companion, we need a black box test. This test is referred to as an Evaluation test.

For the evaluation, we need to define a set of scenarios, with each scenario further divided into expectations. Kyma Companion is prompted through its endpoints to evaluate the given scenario. In the Evaluation, the response is compared to the given expectations. This comparison will either result in a match or no match. However, as different expectations can be more or less complex, this boolean value is multiplied by a complexity factor. Every expectation must be evaluated multiple times so the idempotency performance of Kyma Companion can be calculated.

## Setup

The test cases are deployed on a Gardener cluster. The cluster is set up by hand and is not deleted unless necessary.

When the cluster is set up, manually trigger the GitHub Action [Setup Gardener Test Cluster](https://github.com/kyma-project/kyma-companion/actions/workflows/setup-test-cluster.yaml).
The action automatically connects to the Gardener cluster, cleans it and deploys all the examples in the [tests/blackbox/data/evaluation/namespace-scoped](../../tests/blackbox/data/evaluation/namespace-scoped) directory.

The GitHub Action provides a summary of any missing scenarios or ones that failed to be deployed. You must fix these within their own `deploy.sh` script.

## Usage

To run the Evaluation tests, follow these steps:

1. Install dependencies:

    ```bash
    poetry install
    ```

2. Prepare the `config-evaluation.json` file based on the [template](../../config/config-example.json).

3. Run the following command to set up `CONFIG_PATH` environment variable in your system:

    ```bash
    export CONFIG_PATH=<path_to_config-evaluation.json>
    ```

4. (Optional) Configure retry behavior for failed scenarios:

    ```bash
    export KC_EVAL_RETRIES=3  # Default: 3 (total number of attempts, including the initial attempt)
    ```

    This controls how many times a failed scenario will be retried. Each retry creates a fresh conversation to handle LLM non-determinism. Set to 1 to disable retries.

5. Run the Evaluation tests:

    ```bash
   poetry run python src/run_evaluation.py
    ```
