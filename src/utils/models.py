from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI

from utils.config import Model, get_config

proxy_client = get_proxy_client('gen-ai-hub')


def get_model(name: str) -> Model:
    """
    Retrieve a model by its name.

    Args:
        name (str): The name of the model to find.

    Returns:
        Model | None: The matching model if found, otherwise None.
    """
    config = get_config()
    return next((model for model in config.models if model.name == name), None)


def create_llm(name: str, temperature: int = 0) -> ChatOpenAI:
    """
    Create a ChatOpenAI instance.
    """
    model = get_model(name)
    return ChatOpenAI(deployment_id=model.deployment_id,
                      proxy_client=proxy_client,
                      temperature=temperature)
