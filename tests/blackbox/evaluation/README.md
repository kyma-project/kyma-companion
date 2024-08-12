# Blackbox Testing Framework

To measure any improvement of Kyma Companion, we need a black box test. This test is referred to as an Evaluation test.

For the Evaluation, we need to define a set of scenarios, with each scenario further divided into expectations. Kyma Companion is prompted through its endpoints to evaluate the given scenario. In the Evaluation, the response is compared to the given expectations. This comparison will either result in a match or no match. However, as different expectations can be more or less complex, this boolean value is multiplied by a complexity factor. Every expectation must be evaluated multiple times so the idempotency performance of Kyma Companion can be calculated.

## Usage

To run the Evaluation tests, follow these steps:

1. Install dependencies:

    ```bash
    poetry install
    ```

2. Prepare the `.env.companion.evaluation.tests` file based on the following template:

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
    export $(xargs < .env.companion.evaluation.tests)
    ```

4. Run the Evaluation tests:

    ```bash
   poetry run python tests/blackbox/evaluation/run.py
   # OR
   poetry shell
   python tests/blackbox/evaluation/run.py
    ```
