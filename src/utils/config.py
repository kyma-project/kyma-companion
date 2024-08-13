import os

import yaml
from pydantic import BaseModel

from utils.logging import get_logger

logger = get_logger("config")


class Model(BaseModel):
    """Model for the deployment request"""

    name: str
    deployment_id: str


class Config(BaseModel):
    """Configuration of the application"""

    models: list[Model]


def get_config() -> Config:
    """
    Get the configuration of the application
    Returns:
        Config: The configuration of the application
    """

    config_file = os.environ.get("MODELS_CONFIG_FILE_PATH", "config/config.yml")
    logger.info(f"Loading models config from: {config_file}")
    with open(config_file) as f:
        data = yaml.safe_load(f)
    config = Config(**data)
    return config
