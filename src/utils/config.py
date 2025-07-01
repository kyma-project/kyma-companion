import json
import os
from pathlib import Path

from pydantic import BaseModel

from utils.logging import get_logger

logger = get_logger("config")


class ModelConfig(BaseModel):
    """Model for the deployment request"""

    name: str
    deployment_id: str
    temperature: float = 0.0


class DataSanitizationConfig(BaseModel):
    """Sanitization configuration."""

    resources_to_sanitize: list[str] | None = None
    sensitive_field_names: list[str] | None = None
    sensitive_env_vars: list[str] | None = None
    sensitive_field_to_exclude: list[str] | None = None
    regex_patterns: list[str] | None = None


class Config(BaseModel):
    """Configuration of the application"""

    models: list[ModelConfig]
    sanitization_config: DataSanitizationConfig | None = None


def find_config_file(start_path: Path, target: str) -> Path:
    """
    Recursively search for the target config file starting from start_path.

    Args:
        start_path (Path): The directory to start searching from.
        target (str): The relative path to the config file.

    Returns:
        Path: The path to the config file.

    Raises:
        FileNotFoundError: If the config file is not found.
    """
    for parent in [start_path] + list(start_path.parents):
        potential_path = parent / target
        if potential_path.is_file():
            return potential_path
    raise FileNotFoundError(
        f"{target} not found in any parent directories of {start_path}"
    )


def get_config() -> Config:
    """
    Get the model configuration of the application by automatically locating the config file.

    Returns:
        Config: The model configuration of the application
    """
    # Get the absolute path of the current file
    current_file_path = Path(__file__).resolve()

    target_config_file = os.environ.get("CONFIG_PATH", "config/config.json")
    # Find the config file by searching upwards
    config_file = find_config_file(current_file_path.parent, target_config_file)

    logger.info(f"Loading models config from: {config_file}")
    try:
        with config_file.open() as file:
            data = json.load(file)
        # Extract only the "models" part of the configuration
        models_data = data.get("models", [])
        sanitization_config = data.get("sanitization_config", None)
        config = Config(models=models_data, sanitization_config=sanitization_config)
        return config
    except json.JSONDecodeError:
        logger.exception(f"Invalid JSON format in config file {config_file}")
        raise
    except Exception:
        logger.exception(f"Error loading config from {config_file}")
        raise
