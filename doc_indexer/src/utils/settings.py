import json
import logging
import os
from pathlib import Path

from decouple import config

from utils.models import ModelConfig

project_root = os.path.dirname(os.path.abspath(__file__))

MODELS_CONFIGS_KEY = "MODELS_CONFIGS"


def load_env_from_json() -> None:
    """Load the configuration from the config.json file."""
    default_config_path = (
        Path(__file__).parent.parent.parent.parent / "config" / "config.json"
    )

    config_path = Path(os.getenv("CONFIG_PATH", default_config_path))

    try:
        # Load the configuration from the given path and set the environment variables.
        with config_path.open() as file:
            config_file = json.load(file)

            # Set environment variables for all keys except "models"
            for key, value in config_file.items():
                if key != "models":
                    os.environ[key] = str(value)
                else:
                    os.environ[MODELS_CONFIGS_KEY] = json.dumps(value)
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


# Load the environment variables from the json file.
load_env_from_json()


LOG_LEVEL = config("LOG_LEVEL", default="INFO")
EMBEDDING_MODEL_NAME = config("EMBEDDING_MODEL_NAME", default="text-embedding-3-large")

TMP_DIR = config("TMP_DIR", default=os.path.join(project_root, "tmp"))
DOCS_SOURCES_FILE_PATH = config(
    "DOCS_SOURCES_FILE_PATH", default=os.path.join(project_root, "docs_sources.json")
)
DOCS_PATH = config("DOCS_PATH", default="data")
DOCS_TABLE_NAME = config("DOCS_TABLE_NAME", default="kyma_docs")
CHUNKS_BATCH_SIZE = config("CHUNKS_BATCH_SIZE", cast=int, default=200)

DATABASE_URL = config("DATABASE_URL")
DATABASE_PORT = config("DATABASE_PORT", cast=int)
DATABASE_USER = config("DATABASE_USER")
DATABASE_PASSWORD = config("DATABASE_PASSWORD")

INDEX_TO_FILE = config("INDEX_TO_FILE", default=False)


def get_embedding_model_config(name: str) -> ModelConfig:
    """Get the configuration of the embedding model by name."""
    models = config(MODELS_CONFIGS_KEY, cast=json.loads)
    for model in models:
        if model["name"] == name:
            # cast model as ModelConfig
            return ModelConfig(**model)

    raise ValueError(f"Model {name} not found in the configuration.")
