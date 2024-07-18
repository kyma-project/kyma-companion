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
