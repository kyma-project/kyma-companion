import json
import logging
import os
from pathlib import Path

from decouple import config

DEFAULT_RETRY_WAIT_TIME = 60
DEFAULT_RETRY_MAX_WAIT_TIME = 600


class Config:
    """
    Config represent the test configurations.
    """

    test_data_path: str  # Path to the test data directory e.g. "~kyma-companion/tests/blackbox/data"
    namespace_scoped_test_data_path: str
    companion_api_url: str
    companion_token: (
        str  # Authentication token when the companion is deployed in MPS cluster.
    )
    test_cluster_url: str  # Gardener test cluster API server URL.
    test_cluster_ca_data: str  # Gardener test cluster CA data.
    test_cluster_auth_token: str  # Gardener test cluster authentication token.
    redis_url: str  # Redis URL.

    model_name: str

    streaming_response_timeout: int
    max_workers: int
    retry_wait_time: int
    retry_max_wait_time: int
    models: list[dict]

    def __init__(self) -> None:
        # setup environment variables based on config.json.
        self.__load_env_from_json()

        # read configs.
        self.test_data_path = config("TEST_DATA_PATH", default="./data")
        self.namespace_scoped_test_data_path = f"{self.test_data_path}/test-cases"

        self.companion_api_url = config(
            "COMPANION_API_URL", default="http://localhost:8000"
        )
        self.companion_token = config("COMPANION_TOKEN", default="not-needed")
        self.test_cluster_url = config("TEST_CLUSTER_URL")
        self.test_cluster_ca_data = config("TEST_CLUSTER_CA_DATA")
        self.test_cluster_auth_token = config("TEST_CLUSTER_AUTH_TOKEN")

        self.model_name = config("MODEL_NAME", default="gpt-4o-mini")
        self.streaming_response_timeout = config(
            "STREAMING_RESPONSE_TIMEOUT", default=600, cast=int
        )  # seconds
        self.max_workers = config("MAX_WORKERS", default=1, cast=int)
        self.retry_wait_time = config(
            "RETRY_WAIT_TIME", default=60, cast=int
        )  # seconds
        self.retry_max_wait_time = config(
            "RETRY_MAX_WAIT_TIME", default=600, cast=int
        )  # seconds
        self.redis_url = config("REDIS_URL", default="redis://localhost:6379")

    def __load_env_from_json(self) -> None:
        """Load the configuration from the config.json file."""
        default_config_path = (
            Path(__file__).parent.parent.parent.parent.parent / "config" / "config.json"
        )
        config_path = Path(os.getenv("CONFIG_PATH", default_config_path))

        try:
            # Load the configuration from the given path and set the environment variables.
            with config_path.open() as file:
                config_file = json.load(file)

                # Set environment variables for all keys except "models"
                for key, value in config_file.items():
                    if key in os.environ:
                        logging.warning(
                            f"Environment variable {key} is already set. Not overriding it with value from config file."
                        )
                        continue
                    if key != "models":  # Skip models
                        os.environ[key] = str(value)
                    else:
                        self.models = value
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON format in config file {config_path}: {e}")
            raise
        except FileNotFoundError:
            logging.error(
                f"Config file not found at {config_path}. Place the config file at the default location:"
                f"{default_config_path} or set the CONFIG_PATH environment variable."
            )
            raise
        except Exception as e:
            logging.error(f"Error loading config from {config_path}: {e}")
            raise

    def get_model_config(self, model_name: str) -> dict:
        """Return the specified model configuration."""
        for model in self.models:
            if model["name"] == model_name:
                return model

        raise ValueError(f"Model {model_name} not found in the configuration.")

    def get_models(self) -> list[dict]:
        """Return all models."""
        return self.models
