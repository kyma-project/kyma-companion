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

2. Prepare the `.env.evaluation` file based on the following template:

    ```
   LOG_LEVEL=                           # Allowed values: "INFO", "DEBUG", "ERROR", "WARNING"
   TEST_DATA_PATH=                      # Directory path of test data. e.g. "/Users/<username>/git/kyma-project/kyma-companion/tests/data".
   MODEL_NAME=                          # [Optional] Model name to use for validator.
   COMPANION_API_URL=                   # Kyma Companion API URL. e.g. "http://localhost:8080/api/v1/pods/stream".
   COMPANION_TOKEN=                     # [Optional] Kyma Companion API Authentication Token.
   TEST_CLUSTER_URL=                    # Kubernetes Cluster (with test-cases configured) URL.
   TEST_CLUSTER_CA_DATA=                # Kubernetes Cluster (with test-cases configured) Certificate Authority Data.
   TEST_CLUSTER_AUTH_TOKEN=             # Kubernetes Cluster (with test-cases configured) Authentication Token.
   AICORE_AUTH_URL=                     # AI-Core Auth URL.
   AICORE_BASE_URL=                     # AI-Core Base URL.
   AICORE_CLIENT_ID=                    # AI-Core Client ID.
   AICORE_CLIENT_SECRET=                # AI-Core Client Secret.
   AICORE_RESOURCE_GROUP=               # AI-Core Resource Group.
   AICORE_CONFIGURATION_ID_GPT4=        # AI-Core Configuration ID for GPT-4.
   AICORE_DEPLOYMENT_ID_GPT4=           # AI-Core Deployment ID for GPT-4.
    ```

3. Run the following command to set up the environment variables in your system:

    ```bash
    export $(xargs < .env.evaluation)
    ```

4. Run the Evaluation tests:

    ```bash
   poetry run python src/run_evaluation.py
   # OR
   poetry shell
   python src/run_evaluation.py
    ```
