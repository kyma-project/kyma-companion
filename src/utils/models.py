import json

from pydantic import BaseModel


class Model(BaseModel):
    """Model for the deployment request"""
    name: str
    deployment_id: str


def get_models(file_path: str) -> list[Model]:
    """
    Read models from a JSON file
    Args:
        file_path (str): The path to the JSON file.
    Returns:
        list[Model]: A list of models.
    """
    with open(file_path) as f:
        data = json.load(f)
    return [Model(**item) for item in data]


models = get_models("../config/models.json")


def get_model(name: str) -> Model:
    """
    Retrieve a model by its name.

    Args:
        name (str): The name of the model to find.

    Returns:
        Model | None: The matching model if found, otherwise None.
    """
    return next((model for model in models if model.name == name), None)
