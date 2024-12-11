import json
import logging
import os
import sys
from pathlib import Path

from decouple import Config, RepositoryEnv, config
from dotenv import find_dotenv


def is_running_pytest() -> bool:
    """Check if the code is running with pytest.
    This is needed to identify if tests are running.
    """
    return "pytest" in sys.modules

def is_running_kubernetes() -> bool:
    """Check if the code is running in a Kubernetes environment.
    This is needed to identify if the code is running in a Kubernetes environment.
    """
    return "KUBERNETES_SERVICE_HOST" in os.environ


def load_env_from_json() -> None:
    """Load the configuration from the config.json file."""
    default_config_path = Path(__file__).parent.parent.parent / "config" / "config.json"

    config_path = Path(os.getenv("AICORE_HOME", default_config_path))

    if os.path.exists(config_path):
        try:
            # Load the configuration from the given path and set the environment variables.
            with config_path.open() as file:
                config_file = json.load(file)

                # Set environment variables for all keys except "models"
                for key, value in config_file.items():
                    if key != "models":  # Skip models
                        os.environ[key] = str(value)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON format in config file {config_path}: {e}")
            raise
        except Exception as e:
            logging.error(f"Error loading config from {config_path}: {e}")
            raise
    else:
        if is_running_kubernetes():
            logging.debug("Running in Kubernetes environment. Using ConfigMap.")
        else:
            logging.error(
                f"Config file not found at {config_path}. Place the config file at the default location:"
                f"{default_config_path} or set the AICORE_HOME environment variable."
            )
            raise FileNotFoundError


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
