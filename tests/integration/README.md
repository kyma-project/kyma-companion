# Integration Tests

Integration tests ensure that various modules of Kyma Companion work seamlessly together. The tests are written in Python and use the [pytest framework](https://docs.pytest.org/en/stable/).

## Setup

The integration tests use the same data as the blackbox tests. The data is stored in the [`tests/blackbox/data`](../../tests/blackbox/data) directory.

## Usage

To run the Integration tests, follow these steps:

1. Install dependencies:

    ```bash
    poetry install
    ```

2. Prepare the `.env.test` file based on the following template:

    ```
   LOG_LEVEL=                           # Allowed values: "INFO", "DEBUG", "ERROR", "WARNING"
   TEST_CLUSTER_URL=                    # Kubernetes Cluster (with test-cases configured) URL.
   TEST_CLUSTER_CA_DATA=                # Kubernetes Cluster (with test-cases configured) Certificate Authority Data.
   TEST_CLUSTER_AUTH_TOKEN=             # Kubernetes Cluster (with test-cases configured) Authentication Token.
   AICORE_AUTH_URL=                     # AI-Core Auth URL.
   AICORE_BASE_URL=                     # AI-Core Base URL.
   AICORE_CLIENT_ID=                    # AI-Core Client ID.
   AICORE_CLIENT_SECRET=                # AI-Core Client Secret.
   AICORE_RESOURCE_GROUP=               # AI-Core Resource Group.
    ```

3. Run the following command to set up the environment variables in your system:

    ```bash
    export $(xargs < .env.test)
    ```

4. Run the integration tests:

    ```bash
   poetry run poe test-integration
   # OR
   poetry shell
   poe test-integration
    ```

