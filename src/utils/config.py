import yaml
from pydantic import BaseModel


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
    with open("config/config.yml") as f:
        data = yaml.safe_load(f)
    config = Config(**data)
    return config
