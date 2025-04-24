from collections.abc import Generator

from langchain_core.embeddings import Embeddings

from utils.config import get_config
from utils.logging import get_logger
from utils.models.factory import IModel, ModelFactory
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)


class LLMReadinessProbe(metaclass=SingletonMeta):
    """
    A probe to check the readiness of Large Language Models (LLMs).

    This class manages the readiness states of LLMs and ensures that
    they are operational before being used.
    """

    _models: dict[str, IModel | Embeddings] | None = None
    _model_states: dict[str, bool] | None = None

    def __init__(self, models: dict[str, IModel | Embeddings] | None = None) -> None:
        """
        Initialize the LLMReadinessProbe.

        Args:
            models (dict[str, IModel | Embeddings] | None): A dictionary of model names
                and their corresponding model instances. If None, models will be
                created using the ModelFactory.
        """
        logger.info("Creating new LLM readiness probe")
        self._models = models or ModelFactory(config=get_config()).create_models()
        self._model_states = {name: False for name in self._models}

    def has_models(self) -> bool:
        """
        Check if there are any models available.

        Returns:
            bool: True if models are available, False otherwise.
        """
        return bool(self._models) and len(self._models or {}) > 0

    def are_llms_ready(self) -> bool:
        """
        Check if all LLMs (Large Language Models) are ready.
        Once a model is successfully checked, it will not be checked again
        to avoid excessive token usage.

        Returns:
            bool: True if all LLMs are ready, False otherwise.
        """
        if not self._models or not self._model_states:
            logger.warning("No models available for readiness check.")
            return False

        all_ready = True
        for name, model in self._models.items():
            if self._model_states.get(name, False):
                logger.info(f"{name} connection is ready.")
                continue

            try:
                response = (
                    model.invoke("Test.")
                    if isinstance(model, IModel)
                    else model.embed_query("Test.")
                )
                self._model_states[name] = bool(response)
                if response:
                    logger.info(f"{name} connection is ready.")
                else:
                    logger.warning(f"{name} connection is not working.")
                    all_ready = False
            except Exception as e:
                logger.error(f"{name} connection has an error: {e}")
                all_ready = False

        return all_ready

    def get_llms_states(self) -> dict[str, bool]:
        """
        Get the readiness states of all LLMs.

        Returns:
            dict[str, bool]: A dictionary where keys are LLM names and values
            are their readiness states.
        """
        self.are_llms_ready()
        return self._model_states or {}


def get_llm_readiness_probe() -> Generator[LLMReadinessProbe, None, None]:
    """
    Create and yield an LLMReadinessProbe instance.

    This function initializes the required models using the ModelFactory
    and yields an LLMReadinessProbe instance. It ensures proper error
    handling in case of initialization failure.
    """
    try:
        yield LLMReadinessProbe(models=None)
    except Exception as e:
        logger.exception(f"Failed to initialize LLMReadinessProbe: {e}")
        raise
