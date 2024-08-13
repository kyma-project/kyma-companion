# Kyma Companion

## Status

[![REUSE status](https://api.reuse.software/badge/github.com/kyma-project/kyma-companion)](https://api.reuse.software/info/github.com/kyma-project/kyma-companion)

## Overview

Kyma Companion is designed to provide in-app context-sensitive help and general assistance to Kyma users.

## Prerequisites

Required software:

 - Python 3.12.\*
 - [Poetry](https://python-poetry.org/)
 - [Redis server](https://github.tools.sap/kyma/ai-force/blob/main/docs/infrastructure/setup.md#15-redis) <!--the link must be replaced when the OS documentation is available -->

## Manage Dependencies

We use Poetry to manage dependencies in the project. Poetry is a powerful tool for managing dependencies in Python projects. 
Here's a quick guide on how to add, remove, and update dependencies using Poetry.

### Add and Update Dependencies

To install all the dependencies listed in the `pyproject.toml` file, you can use the following command:

```bash
poetry install
```

To update a specific dependency to its latest version, you can use the `poetry update` command followed by the name of the package:

```bash
poetry update {package_name}
```

To add a new dependency to your project, you can use the `poetry add` command followed by the name of the package you want to add:

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

You can create a virtual environment for the project by navigating to the project's root directory and running the following command:

```bash
poetry install
```

This will create a new virtual environment and install the project's dependencies.

### Activate the Virtual Environment

To activate the virtual environment, use `poetry shell`. This will start a new shell session with the virtual environment activated:

```bash
poetry shell
```

You can now run Python and any installed packages in this shell. They will use the virtual environment. 
To exit the virtual environment, simply use the `deactivate` command.

Poetry automatically uses the virtual environment when you run, for example, the `poetry run` command.

Remember to run these commands in the root directory of your project, where the `pyproject.toml` file is located.

If you are a PyCharm user and want to use the virtual environment created by Poetry, follow the [configuration guides](https://www.jetbrains.com/help/pycharm/poetry.html).

## Use Poe the Poet as Task Runner

[Poe the Poet](https://poethepoet.natn.io/index.html) is a task runner that simplifies running common tasks in a Python project.

To have the command available as `poetry poe <command>` as seen in the following examples, you need to install poe as a plugin to Poetry:

```bash
poetry self add 'poethepoet[poetry_plugin]'
```

If this plugin is not installed, you may have to run poe as a script within the Poetry environment using `poetry run poe <command>`.

## Development

### Redis Server 

Before running the application, the Redis server must be provided. It is used to store the conversation with a large language model (LLM).
Therefore, **REDIS_URL** must be provided as an environment variable.

Here is the [documentation](https://github.tools.sap/kyma/ai-force/blob/main/docs/infrastructure/setup.md#15-redis) <!--the link must be replaced when the OS documentation is available --> on how to create a Redis server. 
For example, `REDIS_URL="redis://{host or ip}:6379"`

### Running Kyma Companion Locally

You can execute the Kyma Companion locally using the FastAPI framework with the following command:

```bash
poetry run fastapi dev src/main.py --port 8000
```

Or, with a poe task:

```bash
$ poetry poe run-local
```

It is recommended to run Kyma Companion with Poetry as it activates and uses its virtual environment if not activated yet.

> [!NOTE] You cannot run it with Python directly.

### Debugging

As the companion uses the FastAPI framework, refer to the following documentation on how to debug the application with the respective IDE:

* [PyCharm](https://www.jetbrains.com/help/pycharm/fastapi-project.html#create-project)
* [VS Code](https://code.visualstudio.com/docs/python/tutorial-fastapi)

### Configuration

For local development, LLM models can be configured inside the `config/models.json` file.  
> [!NOTE] Don't use the <code>config/models.json</code> file to configure models in dev, stage, or prod clusters.

## Code Checks

To execute linting, formatting, and type checking using Ruff, Black, and mypy, respectively use the following command:

```bash
poetry poe codecheck
```

To fix linting and formatting issues, use the following command:

```bash
poetry poe codefix
```

Mypy does not support fixing issues automatically.

### Linting

It is recommended to execute the [Ruff](https://docs.astral.sh/ruff/) linting check with the poe lint task with the following command:

```bash
poetry poe lint
```

Alternatively, you can also do it with `ruff check` directly, 
where Ruff may have a different version in a different virtual environment.

Linting errors can be fixed with the following command, which by default applies only the safe fixes:

```bash
poetry poe lint-fix
```

> [!WARNING]
Use the command with caution, as it may change the code in an unexpected way.

### Formatting

To execute the [Black](https://black.readthedocs.io/en/stable/) formatting check with the poe format task, use the following command:

```bash
poetry poe format
```

You can fix formatting erros with the following command:

```bash
poetry poe format-fix
```

### Type Checking

To execute type checking with [mypy](https://mypy-lang.org/), use the following command:

```bash
poetry poe typecheck
```

Mypy does not support fixing issues automatically.


## Tests

The tests written in the [pytest framework](https://docs.pytest.org/en/stable/) can be executed with the following command:

```bash
poetry poe test
```

Or, with the following command:

```bash
poetry run pytest tests
```

## Release Process

Release testing and release creation are two separate processes. 
You can find the release testing documentation in the [Contributor README](./docs/contributor/README.md) file.

## Contributing

<!--- mandatory section - do not change this! --->

See the [Contributing Rules](CONTRIBUTING.md).

## Code of Conduct

<!--- mandatory section - do not change this! --->

See the [Code of Conduct](CODE_OF_CONDUCT.md) document.

## Licensing

<!--- mandatory section - do not change this! --->

See the [license](./LICENSE) file.
