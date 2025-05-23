from collections.abc import Callable

from langchain_core.embeddings import Embeddings

from utils.config import get_config
from utils.logging import get_logger
from utils.models.factory import IModel, ModelFactory
from utils.singleton_meta import SingletonMeta

USAGE_TRACKER_FAILURE_THRESHOLD = 3

logger = get_logger(__name__)


class LLMProbe(metaclass=SingletonMeta):
    """
    A probe to check the readiness of Large Language Models (LLMs).

    This class manages the readiness states of LLMs and ensures that
    they are operational before being used.
    """

    _models: dict[str, IModel | Embeddings]
    _model_states: dict[str, bool]

    def __init__(
        self, model_factory: Callable[[], dict[str, IModel | Embeddings]] | None = None
    ) -> None:
        """
        Initialize the LLMReadinessProbe.

        Args:
            models (dict[str, IModel | Embeddings] | None): A dictionary of model names
                and their corresponding model instances. If None, models will be
                created using the ModelFactory.
        """
        logger.info("Creating new LLM readiness probe")

        try:
            self._models = model_factory() if model_factory else _get_models()
        except Exception as e:
            logger.exception(f"Unknown error occurred: {e}")
            self._models = {}

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
            # If the current model already is ready, we will not check the state again.
            if self._model_states.get(name, False):
                logger.debug(f"{name} connection is ready.")
                continue

            try:
                # Check if the model is an implementation of IModel or an embedding and test accordingly,
                # if they are operational.

                logger.info(
                    f"Invoking the mode: {name} to check its accessibility. "
                    f"This should only be done once. If you see this log message multiple "
                    f"times, please open a bug report."
                )
                response = (
                    model.invoke("Test.")
                    if isinstance(model, IModel)
                    else model.embed_query("Test.")
                )
                # If we got a response, we will store the state of the corresponding model.
                self._model_states[name] = bool(response)
                if response:
                    logger.info(f"{name} connection is ready.")
                else:
                    logger.warning(f"{name} connection is not working.")
                    # If any model is not ready, we will return `False`, eventually.
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

    @classmethod
    def _reset_for_tests(cls) -> None:
        """Reset the singleton instance. Only use for testing purpose."""
        SingletonMeta.reset_instance(cls)


def _get_models() -> dict[str, IModel | Embeddings]:
    """Do not use this function directly to create Models. Use the ModelFactory instead."""
    return ModelFactory(get_config()).create_models()


def get_llm_probe() -> LLMProbe:
    """
    Returns a LLMReadinessProbe instance.
    """
    return LLMProbe()


class UsageTrackerProbe(metaclass=SingletonMeta):
    """Probe that checks if the UsageTracker is health."""

    _failure_threshold: int
    _failure_count: int

    def __init__(self, failure_threshold: int = 3, failure_count: int = 0) -> None:
        self._failure_threshold = failure_threshold
        self._failure_count = failure_count

    def reset_failure_count(self) -> None:
        """Sets the failure count back to 0."""
        logger.debug("resetting the failure counter of the Usage Tracker Probe")
        self._failure_count = 0

    def increase_failure_count(self) -> None:
        """Increases the failure count by 1."""
        self._failure_count += 1
        logger.warning(
            f"failure counter for Usage Tracker Probe increased to {self._failure_count}"
        )

    def is_healthy(self) -> bool:
        """Checks if the failure count is snaller than the threshold."""
        return self._failure_count < self._failure_threshold

    def get_failure_count(self) -> int:
        """Returns the current value of the failure count."""
        return self._failure_count

    @classmethod
    def _reset_for_tests(cls) -> None:
        """Reset the singleton instance. Only use for testing purpose."""
        SingletonMeta.reset_instance(cls)


def get_usage_tracker_probe() -> UsageTrackerProbe:
    """Retrieve an instance of UsageTrackerProbe."""
    return UsageTrackerProbe()
