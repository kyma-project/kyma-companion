from dataclasses import field
from typing import Annotated, Protocol

from hdbcli import dbapi
from langchain_core.embeddings import Embeddings
from redis.typing import ResponseT

from routers.common import ReadynessModel
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)

# Interfaces:


class IHanaConnection(Protocol):
    """Protocol for the Hana database connection."""

    def isconnected(self) -> bool:
        """Veryfies if a connection to a Hana database is ready."""
        ...


class IRedisConnection(Protocol):
    """
    Protocol to ensure the Redis connection has a `ping` method.
    """

    def ping(self, **kwargs) -> ResponseT:  # noqa
        """Ping the Redis server."""
        ...


class IReadynessProbe(Protocol):
    """
    Protocol to ensure the Readyness probe has a `get_dto` method.
    """

    def is_hana_ready(self) -> bool:
        """Check if the HANA database is ready."""
        ...

    def is_redis_ready(self) -> bool:
        """Check if the Redis service is ready."""
        ...

    def are_llms_ready(self) -> bool:
        """Check if all LLMs (Large Language Models) are ready."""
        ...

    def get_llms_states(self) -> dict[str, bool]:
        """Get the readiness states of all LLMs."""
        ...

    def get_dto(self) -> ReadynessModel:
        """Get a DTO (Data Transfer Object) representing the readiness states of all components."""
        ...


# Classes:


class Readyness:
    """
    A class to check the readiness of various system components.
    """

    _hana_conn: IHanaConnection | None = None
    _redis_conn: IRedisConnection | None = None
    _models: dict[str, (IModel | Embeddings)] | None = None
    _model_states: dict[str, bool] | None = None

    def __init__(
        self,
        hana_connection: Annotated[IHanaConnection | None, field(default=None)],
        redis_connection: Annotated[IRedisConnection | None, field(default=None)],
        models: dict[str, IModel | Embeddings] | None,
    ) -> None:
        logger.info("Creating new readiness probe")
        self._hana_conn = hana_connection
        self._redis_conn = redis_connection
        self._models = models or {}
        self._model_states = {name: False for name in self._models}

    def is_hana_ready(self) -> bool:
        """
        Check if the HANA database is ready.

        Returns:
            bool: True if HANA is ready, False otherwise.
        """
        if not self._hana_conn:
            logger.warning("HANA DB connection is not initialized.")
            return False

        try:
            if self._hana_conn.isconnected():
                logger.info("HANA DB connection is ready.")
                return True
            logger.info("HANA DB connection is not ready.")
        except dbapi.Error as e:
            logger.error(f"Error while connecting to HANA DB: {e}")

        return False

    def is_redis_ready(self) -> bool:
        """
        Check if the Redis service is ready.

        Returns:
            bool: True if Redis is ready, False otherwise.
        """
        if not self._redis_conn:
            logger.error("Redis connection is not initialized.")
            return False

        try:
            if self._redis_conn.ping():
                logger.info("Redis connection is ready.")
                return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
        return False

    def are_llms_ready(self) -> bool:
        """
        Check if all LLMs (Large Language Models) are ready.
        Once a model was successfully cheched,
        it will not be checked again to avoid excessive token usage.

        Returns:
            bool: True if all LLMs are ready, False otherwise.
        """

        if not self._models or not self._model_states:
            logger.warning("No models available for readiness check.")
            return False

        all_ready = True
        for name, model in self._models.items():
            model_state = self._model_states.get(name, False)
            if model_state:
                logger.info(f"{name} connection is ready.")
                continue

            try:
                response = (
                    model.invoke("Test.")
                    if isinstance(model, IModel)
                    else model.embed_query("Test.")
                )

                if response:
                    self._model_states[name] = True
                    logger.info(f"{name} connection is ready.")
                else:
                    logger.warning(f"{name} connection is not working.")
                    all_ready = False

            except Exception as e:
                logger.error(f"{name} connection has an error: {e}")
                all_ready = False

        # Return the overall readiness status.
        return all_ready

    def get_llms_states(self) -> dict[str, bool]:
        """
        Get the readiness states of all LLMs.

        Returns:
            dict[str, bool]: A dictionary where keys are LLM names and values are their readiness states.
        """
        if self._model_states and not all(self._model_states.values()):
            self.are_llms_ready()
        return self._model_states or {}

    def get_dto(self) -> ReadynessModel:
        """
        Get a DTO (Data Transfer Object) representing the readiness states of all components.

        Returns:
            ReadynessModel: An object containing the readiness states of Redis, HANA, and LLMs.
        """
        return ReadynessModel(
            is_redis_ready=self.is_redis_ready(),
            is_hana_ready=self.is_hana_ready(),
            llms=self.get_llms_states(),
        )


def create_readyness_probe(
    hana_connection: IHanaConnection | None,
    redis_connection: IRedisConnection | None,
    models: dict[str, IModel | Embeddings] | None,
) -> IReadynessProbe:
    """
    Factory function to create a Readyness probe.

    Args:
        hana_connection (IHanaConnection | None): The HANA database connection.
        redis_connection (IRedisConnection | None): The Redis connection.

    Returns:
        IReadyness_Probe: An instance of the Readyness class.
    """
    return Readyness(hana_connection, redis_connection, models)
