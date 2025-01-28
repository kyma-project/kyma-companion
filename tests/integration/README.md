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

2. Prepare the `config-integration.json` file based on the [template](../../config/config-example.json).

3. Run the following command to set up `CONFIG_PATH` environment variable in your system:

    ```bash
    export CONFIG_PATH=<path_to_config-integration.json>
    ```

4. Run the integration tests:

    ```bash
   poetry run poe test-integration
    ```

