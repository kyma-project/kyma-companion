# Kyma Companion

## Status

[![REUSE status](https://api.reuse.software/badge/github.com/kyma-project/kyma-companion)](https://api.reuse.software/info/github.com/kyma-project/kyma-companion)

## Overview

Kyma Companion provides in-app context-sensitive help and general assistance to Kyma users.

## Prerequisites

- Python 3.12.x
- [Poetry](https://python-poetry.org/)
- [Redis server](https://github.tools.sap/kyma/ai-force/blob/main/docs/infrastructure/setup.md#15-redis) <!--the link must be replaced when the OS documentation is available -->

## Manage Dependencies

We use [Poetry](https://python-poetry.org/) to manage dependencies in the project.
Here's a quick guide on how to add, remove, and update dependencies using Poetry.

### Add and Update Dependencies

To install all the dependencies listed in the `pyproject.toml` file, use the following command:

   ```bash
   poetry install
   ```

To update a specific dependency to its latest version, use the `poetry update` command followed by the name of the package:

   ```bash
   poetry update {package_name}
   ```

To add a new dependency to your project, use the `poetry add` command followed by the name of the package you want to add:

   ```bash
   poetry add {package_name}
   ```

Or, with an exact version:

   ```bash
   poetry add {package_name}@{version}
   ```

To remove a dependency from your project, you can use the `poetry remove` command followed by the name of the package:

   ```bash
   poetry remove {package_name}
   ```

## Create and Use Virtual Environments with Poetry

To create a virtual environment for the project, navigate to the project's root directory and run the following command:

   ```bash
   poetry install
   ```

This creates a new virtual environment and installs the project's dependencies.

If you are a PyCharm user and want to use the virtual environment created by Poetry, follow the [configuration guides](https://www.jetbrains.com/help/pycharm/poetry.html).

## Development

### Redis Server

Before running the application, you must provide the Redis server. It stores the conversation with a large language model (LLM).
Therefore, provide **REDIS_URL** as an environment variable.

For details on how to create a Redis server, read [Create Redis](https://github.tools.sap/kyma/ai-force/blob/main/docs/infrastructure/setup.md#15-redis). <!--the link must be replaced when the OS documentation is available -->
For example, `REDIS_URL="redis://{host or ip}:6379"`

### Running Kyma Companion Locally

You can execute the Kyma Companion locally using the FastAPI framework with the following command:

   ```bash
   poetry run fastapi dev src/main.py --port 8000
   ```

Or, with a poe task:

   ```bash
   poetry run poe run-local
   ```

It is recommended to run Kyma Companion with Poetry because it activates and uses its virtual environment if not activated yet.

Alternatively, you can run the application directly using Python and [`uvicorn`](https://www.uvicorn.org/) instead of `FastAPI`. To do this, run the following command:

   ```bash
   python src/main.py
   ```

To enable auto-reloading, pass the `--reload` argument:
    ```bash
    python src/main.pt --reload
    ```
For IDEs, such as Pycharm or VS Code, you must pass this argument in the run or debug configuration.

### Debugging

Because the companion uses the FastAPI framework, read the following documentation on how to debug the application with the respective IDE:

- [PyCharm](https://www.jetbrains.com/help/pycharm/fastapi-project.html#create-project)
- [VS Code](https://code.visualstudio.com/docs/python/tutorial-fastapi)

### Configuration

For local development, you can configure LLMs by modifying the `config/config.json` file.
To use a configuration file from a different location, set the `CONFIG_PATH` environment variable to the path of your desired JSON configuration file.

### Tracing

For tracing, Kyma Companion uses [Langfuse](https://langfuse.com/). For more information, see [Using Langfuse in Kyma Companion](/docs/langfuse.md).

## Code Checks

To execute linting, formatting, and type checking using Ruff, Black, and mypy, respectively use the following command:

   ```bash
   poetry run poe codecheck
   ```

To fix linting and formatting issues, use the following command:

   ```bash
   poetry run poe code-fix
   ```

Mypy does not support fixing issues automatically.

### Linting

It is recommended to execute the [Ruff](https://docs.astral.sh/ruff/) linting check with the poe lint task with the following command:

   ```bash
   poetry run poe lint
   ```

Alternatively, you can also do it with `ruff check` directly, where Ruff may have a different version in a different virtual environment.

Linting errors can be fixed with the following command, which applies only the safe fixes by default:

   ```bash
   poetry run poe lint-fix
   ```

> [!WARNING]
Use the command with caution, as it may change the code in an unexpected way.

### Formatting

To execute the [Black](https://black.readthedocs.io/en/stable/) formatting check with the poe format task, use the following command:

   ```bash
   poetry run poe format
   ```

You can fix formatting erros with the following command:

   ```bash
   poetry run poe format-fix
   ```

### Type Checking

To execute type checking with [mypy](https://mypy-lang.org/), use the following command:

   ```bash
   poetry run poe typecheck
   ```

Mypy does not support fixing issues automatically.

## Tests

### Unit Tests

The tests written in the [pytest framework](https://docs.pytest.org/en/stable/) can be executed with the following command:

   ```bash
   poetry run poe test
   ```

Or, with the following command:

   ```bash
   poetry run pytest tests
   ```

### Integration Tests

For details about integration tests, read the [Integration Tests README file](./tests/integration/README.md).

### Blackbox Tests

For details about blackbox tests, read the [Blackbox Tests README file](./tests/blackbox/README.md).

## Release Process

Release testing and release creation are two separate processes.
For details about release testing, read the [Contributor README](./docs/contributor/README.md) file.

## Contributing

<!--- mandatory section - do not change this! --->

See the [Contributing Rules](CONTRIBUTING.md).

## Code of Conduct

<!--- mandatory section - do not change this! --->

See the [Code of Conduct](CODE_OF_CONDUCT.md) document.

## Licensing

<!--- mandatory section - do not change this! --->

See the [license](./LICENSE) file.
