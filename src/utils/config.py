import os
from pathlib import Path

import yaml
from pydantic import BaseModel

from utils.logging import get_logger

logger = get_logger("config")


class ModelConfig(BaseModel):
    """Model for the deployment request"""

    name: str
    deployment_id: str
    temperature: float


class Config(BaseModel):
    """Configuration of the application"""

    models: list[ModelConfig]


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
        f"{target} not found in parent directories of {start_path}"
    )


def get_config() -> Config:
    """
    Get the configuration of the application by automatically locating the config file.

    Returns:
        Config: The configuration of the application
    """
    # Get the absolute path of the current file
    current_file_path = Path(__file__).resolve()

    target_config_file = os.environ.get("CONFIG_PATH", "config/config.yml")
    # Find the config file by searching upwards
    config_file = find_config_file(current_file_path.parent, target_config_file)

    logger.info(f"Loading models config from: {config_file}")
    with config_file.open() as f:
        data = yaml.safe_load(f)
    config = Config(**data)
    return config
