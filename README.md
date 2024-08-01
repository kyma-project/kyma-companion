> **NOTE:** This is a general template that you can use for a project README.md. Except for the mandatory sections, use
> only those sections that suit your use case but keep the proposed section order.
>
> Mandatory sections:
> - `Overview`
> - `Prerequisites`, if there are any requirements regarding hard- or software
> - `Installation`
> - `Contributing` - do not change this!
> - `Code of Conduct` - do not change this!
> - `Licensing` - do not change this!

# Kyma companion

## Status

[![REUSE status](https://api.reuse.software/badge/github.com/kyma-project/kyma-companion)](https://api.reuse.software/info/github.com/kyma-project/kyma-companion)

## Overview

<!--- mandatory section --->

> Provide a description of the project's functionality.
>
> If it is an example README.md, describe what the example illustrates.

## Prerequisites

> List all the prerequisites that are necessary for the project. Include the required hardware, software, and any other
> dependencies.
> Required software:
> - Python 3.12.*
> - [Poetry](https://python-poetry.org/)
> - [Redis server](https://github.tools.sap/kyma/ai-force/blob/main/docs/infrastructure/setup.md#15-redis)

## Installation

> Explain the steps to install your project. If there are multiple installation options, mention the recommended one and
> include others in a separate document. Create an ordered list for each installation task.
>
> If it is an example README.md, describe how to build, run locally, and deploy the example. Format the example as code
> blocks and specify the language, highlighting where possible. Explain how you can validate that the example ran
> successfully. For example, define the expected output or commands to run which check a successful deployment.
>
> Add subsections (H3) for better readability.

## Managing Dependencies

We use Poetry to manage dependencies in the project. Poetry is a powerful tool for managing dependencies in Python
projects. Here's a quick guide on how to add, remove, and update dependencies using Poetry.

### Adding and Updating Dependencies

To install all dependencies listed in the `pyproject.toml` file, you can use the `poetry install` command:

```bash
poetry install
```

To update a specific dependency to its latest version, you can use the `poetry update` command followed by the name of
the package:

```bash
poetry update {package_name}
```

To add a new dependency to your project, you can use the `poetry add` command followed by the name of the package you
want to add:

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

## Creating and Using Virtual Environments with Poetry

You can create a virtual environment for the project by navigating to the project's root directory and run:

```bash
poetry install
```

This will create a new virtual environment and install the project's dependencies.

### Activating the Virtual Environment

To activate the virtual environment, use `poetry shell`. This will start a new shell session with the virtual
environment activated:

```bash
poetry shell
```

You can now run Python and any installed packages in this shell, and they will use the virtual environment. To exit the
virtual environment, simply `exit` command.

Poetry automatically uses the virtual environment when you run commands like `poetry run`.

Remember to run these commands in the root directory of your project where the `pyproject.toml` file is located.

Pycharm users can also use the virtual environment created by Poetry. To do this follow
the [guides](https://www.jetbrains.com/help/pycharm/poetry.html).

## Using Poe the Poet as Task Runner

[Poe the Poet](https://poethepoet.natn.io/index.html) is a task runner that simplifies running common tasks in a Python project.

To have the command availalbe as `poetry poe <command>` as seen in the following examples, you need to install Poe as a plugin to poetry:

```bash
poetry self add 'poethepoet[poetry_plugin]'
```

If this plugin is not installed you may have to run Poe as a script within the Poetry environment using `poetry run poe <command>`.

## Usage

> Explain how to use the project. You can create multiple subsections (H3). Include the instructions or provide links to
> the related documentation.

## Development
This sections describes how to develop and run the kyma-companion fastapi app.

### Redis Server
Before running the application, the Redis server must be provided that is used to store the conversation with a LLM.
Therefore, REDIS_URL has to be provided as an environment variable.

Here is the [documentation](https://github.tools.sap/kyma/ai-force/blob/main/docs/infrastructure/setup.md#15-redis) how to create a Redis server. For example,
`REDIS_URL="redis://{host or ip}:6379"`

### Running

You can start the FastApi application with the following options:
```bash
poetry run fastapi dev src/main.py --port 8000
```
or, directly with FastApi:
```bash
fastapi dev src/main.py --port 8000
```
or, with a poe task:
```bash
$ poetry poe run-local
```
Prefer running it with poetry as it activates and uses its virtual environment if not activated yet.  
**NOTE:** it cannot be run with python directly.

### Debugging

The FastAPI application can be debugged with PyCharm or VS Code. Follow the following guidelines for these IDEs:

- PyCharm: https://www.jetbrains.com/help/pycharm/fastapi-project.html#create-project
- VS Code: https://code.visualstudio.com/docs/python/tutorial-fastapi

### Configuration
For local development LLM models can be configured inside the config/models.json file.  
**NOTE:** Don't use it to configure models in dev, stage or prod clusters.

## Codechecks

To execute linting, formatting and type checking using ruff, black and mypy respectively use the following command:

```bash
poetry poe codecheck
```

To fix linting and formatting issues use the following command:

```bash
poetry poe codefix
```

Mypy does not support automatically fixing issues.

### Linting

It is recommended to execute the [Ruff](https://docs.astral.sh/ruff/) linting check with the poe lint task with the following command:

```bash
poetry poe lint
```

Alternatively, it can also be done with `ruff check` directly, where ruff may have a different version in a different
virtual environment.

Linting errors can be fixed with the following command, which by default applies only the safe fixes. However, it should
be used with caution, as it may change the code in an unexpected way:

```bash
poetry poe lint-fix
```

### Formatting

To execute the [Black](https://black.readthedocs.io/en/stable/) formatting check with the poe format task use the following command:

```bash
poetry poe format
```

Formatting errros can be fixed with the following command:

```bash
poetry poe format-fix
```

### Type Checking

To execute type checking with [mypy](https://mypy-lang.org/) use the following command:

```bash
poetry poe typecheck
```

Mypy does not support automatically fixing issues.


## Tests

The tests written in the [pytest framework](https://docs.pytest.org/en/stable/) can be executed with the following command:

```bash
poetry poe test
```

Or, with the following command:

```bash
poetry run pytest tests
```

## Release process

Release testing and release creation are two separate processes. You can find the release testing documentation in
the [Contributor Readme](./docs/contributor/README.md) file.

## Contributing

<!--- mandatory section - do not change this! --->

See the [Contributing Rules](CONTRIBUTING.md).

## Code of Conduct

<!--- mandatory section - do not change this! --->

See the [Code of Conduct](CODE_OF_CONDUCT.md) document.

## Licensing

<!--- mandatory section - do not change this! --->

See the [license](./LICENSE) file.



