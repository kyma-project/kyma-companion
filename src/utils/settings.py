import json
import logging
import os
import sys

from decouple import Config, RepositoryEnv, config
from dotenv import find_dotenv, load_dotenv


def is_running_pytest() -> bool:
    """Check if the code is running with pytest.
    This is needed to identify if tests are running.
    """
    return "pytest" in sys.modules


def _is_running_github_actions() -> bool:
    """Check if the code is running with GitHub Actions."""
    logging.warning("Check for Github Action environment.")
    is_gh = os.getenv("GITHUB_ACTIONS")
    logging.warning(f"Is Github Action: {is_gh}")
    return os.getenv("GITHUB_ACTIONS") == "true"


def load_env_from_json() -> None:
    """Load the configuration from the config.json file."""
    config_path = os.getenv(
        "AICORE_HOME",
        os.path.abspath(
            "../../go/src/github.com/kyma-project/kyma-companion/config/config.json"
        ),
    )  # Default to root config.json.

    if os.path.exists(config_path):
        try:
            # Load the configuration from the given path and set the environment variables.
            with open(config_path) as file:
                config_file = json.load(file)

                # Set environment variables for all keys except "models"
                for key, value in config_file.items():
                    if key != "models":  # Skip models
                        os.environ[key] = str(value)
        except Exception as e:
            logging.error(f"Error loading config from {config_path}: {e}")
    else:
        logging.error(f"Config file not found at {config_path}.")


if is_running_pytest():
    # For tests use .env.test if available
    env_path = find_dotenv(".env.test")
    if env_path and os.path.exists(env_path):
        repository = RepositoryEnv(env_path)
        for key, value in repository.data.items():
            os.environ[key] = str(value)
        config = Config(repository)
    else:
        # Load the config.json if no .env.test file is found
        logging.warning("No .test.env file found. Using config.json.")
        load_env_from_json()

    # deepeval specific environment variables
    DEEPEVAL_TESTCASE_VERBOSE = config("DEEPEVAL_TESTCASE_VERBOSE", default="False")
elif _is_running_github_actions():
    # For GitHub Actions use environment variables
    load_dotenv()
else:
    # For production load the env variables needed dynamically from the config.json.
    load_env_from_json()


LOG_LEVEL = config("LOG_LEVEL", default="INFO")
# Redis
REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = config("REDIS_PORT", default=6379, cast=int)
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
# Langfuse
LANGFUSE_SECRET_KEY = config("LANGFUSE_SECRET_KEY", default="dummy")
LANGFUSE_PUBLIC_KEY = config("LANGFUSE_PUBLIC_KEY", default="dummy")
LANGFUSE_HOST = config("LANGFUSE_HOST", default="localhost")
LANGFUSE_ENABLED = config("LANGFUSE_ENABLED", default="True")

DATABASE_URL = config("DATABASE_URL", None)
DATABASE_PORT = config("DATABASE_PORT", cast=int, default=443)
DATABASE_USER = config("DATABASE_USER", None)
DATABASE_PASSWORD = config("DATABASE_PASSWORD", None)
DOCS_TABLE_NAME = config("DOCS_TABLE_NAME", default="kyma_docs")
