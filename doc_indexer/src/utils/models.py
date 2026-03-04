import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings

from utils.logging import get_logger

logger = get_logger(__name__)


def _get_model_config(model_name: str) -> dict[str, str]:
    """Get model configuration from config.json.

    Args:
        model_name: The logical model name (e.g., "text-embedding-3-large")

    Returns:
        Dict with model configuration including deployment_id

    Raises:
        ValueError: If config file not found or model not found in config
    """
    # Default to ../config/config.json relative to this file
    default_config_path = Path(__file__).parent.parent.parent.parent / "config" / "config.json"
    config_path_str = os.getenv("CONFIG_PATH", str(default_config_path))
    config_path = Path(config_path_str)

    if not config_path.exists():
        raise ValueError(
            f"Config file not found at: {config_path}. "
            f"Place the config file at the default location: {default_config_path} "
            "or set the CONFIG_PATH environment variable."
        )

    try:
        with config_path.open() as f:
            config = json.load(f)

        # Find the model in the models list
        models = config.get("models", [])
        for model in models:
            if model.get("name") == model_name:
                return cast(dict[str, str], model)

        raise ValueError(
            f"Model '{model_name}' not found in config file. Available models: {[m.get('name') for m in models]}"
        )

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file {config_path}: {e}") from e
    except Exception as e:
        raise ValueError(f"Error reading config file {config_path}: {e}") from e


def create_embedding_factory(
    embedding_creator: Callable[[str], Embeddings],
) -> Callable[[str], Embeddings]:
    """Create a factory function for embedding models."""

    def factory(model_name: str) -> Embeddings:
        return embedding_creator(model_name)

    return factory


def openai_embedding_creator(model_name: str) -> Embeddings:
    """Create an OpenAI embedding model using SAP AI Core.

    Reads model configuration from config.json to map model names to SAP AI Core
    deployment IDs, then uses the gen_ai_hub proxy for authentication.

    Args:
        model_name: Model name as defined in config.json (e.g., "text-embedding-3-large")

    Returns:
        Embeddings instance configured for SAP AI Core

    Raises:
        ValueError: If model not found in config or missing deployment_id
    """
    try:
        time.sleep(1)  # Sleep to avoid rate limiting

        # Look up deployment_id from config
        model_config = _get_model_config(model_name)
        deployment_id = model_config.get("deployment_id")

        if not deployment_id:
            raise ValueError(f"Model '{model_name}' in config is missing deployment_id")

        # Initialize SAP AI Core proxy client
        proxy_client = get_proxy_client("gen-ai-hub")

        # Create embeddings with model name and deployment_id
        llm = cast(
            Embeddings,
            OpenAIEmbeddings(
                model=model_name,
                deployment_id=deployment_id,
                proxy_client=proxy_client,
            ),
        )
    except Exception:
        logger.exception("Error while creating OpenAI embedding model")
        raise
    return llm
