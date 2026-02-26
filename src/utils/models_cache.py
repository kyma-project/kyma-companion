from __future__ import annotations

import threading
from collections.abc import Iterable

from langchain_core.embeddings import Embeddings

from utils.config import Config
from utils.logging import get_logger
from utils.models.factory import IModel, ModelFactory

logger = get_logger(__name__)


class _ModelsCacheState:
    def __init__(self) -> None:
        self.key: tuple | None = None
        self.models: dict[str, IModel | Embeddings] | None = None


_lock = threading.Lock()
_state = _ModelsCacheState()


def _model_name(model: object) -> str:
    name = getattr(model, "name", None)
    if isinstance(name, str):
        return name

    # Some unit tests use dict-based configs.
    if isinstance(model, dict):
        return str(model.get("name", ""))

    return ""


def _models_key(models: Iterable[object]) -> tuple:
    # Keyed only by model names on purpose:
    # - stable across Config instances
    # - works with mocked configs in unit tests
    return tuple(_model_name(m) for m in models)


def reset_models_cache_for_tests() -> None:
    """Reset the shared models cache. Intended for unit tests only."""
    with _lock:
        _state.key = None
        _state.models = None


def get_models(config: Config) -> dict[str, IModel | Embeddings]:
    """Return a cached dict of model_name -> model instance.

    This cache is shared across routers/services/probes so the process initializes
    models only once.
    """

    key = _models_key(getattr(config, "models", []) or [])

    with _lock:
        if _state.models is not None and _state.key == key:
            return _state.models

        logger.info("Initializing shared models cache")
        model_factory = ModelFactory(config=config)
        _state.models = model_factory.create_models()
        _state.key = key
        return _state.models
