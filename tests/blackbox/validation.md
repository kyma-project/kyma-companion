# Validation

To find a model that can evaluate the test scenarios, we need to validate the best large language model (LLM) model. This can be done by running the validation tests.

## Usage

To run the validation, follow these steps:

1. Install dependencies:

    ```bash
    poetry install
    ```

2. Prepare the `config-validation.json` file based on the [template](../../config/config-example.json).

3. Run the following command to set up `CONFIG_PATH` environment variable in your system:

    ```bash
    export CONFIG_PATH=<path_to_config-validation.json>
    ```

4. Run the validation:

    ```bash
   poetry run python src/run_validation.py
    ```
