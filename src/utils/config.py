import yaml
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from pydantic import BaseModel

proxy_client = get_proxy_client('gen-ai-hub')


class Model(BaseModel):
    """Model for the deployment request"""
    name: str
    deployment_id: str


class Config(BaseModel):
    """Configuration of the application"""
    models: list[Model]


def load(file_path: str) -> Config:
    """
    Load the configuration from a file
    Args:
        file_path (str): The path to the configuration file
    Returns:
        Config: The configuration of the application
    """
    with open(file_path) as f:
        data = yaml.safe_load(f)

    return Config(**data)


def get_config() -> Config:
    """
    Get the configuration of the application
    Returns:
        Config: The configuration of the application
    """
    config = load("config/config.yml")
    return config
