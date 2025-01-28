from pydantic import BaseModel


class ModelConfig(BaseModel):
    """Model for the deployment request"""

    name: str
    deployment_id: str
    temperature: float = 0.0
