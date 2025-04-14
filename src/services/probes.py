from dataclasses import field
from typing import Annotated, Protocol

from hdbcli import dbapi
from hdbcli.dbapi import Connection as HanaConnection
from langchain_core.embeddings import Embeddings
from redis.asyncio import Redis as RedisConnection
from redis.typing import ResponseT

from utils.logging import get_logger
from utils.models.factory import IModel
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)


class IHanaConnection(Protocol):
    """Protocol for the Hana database connection."""

    def isconnected(self) -> bool:
        """Veryfies if a connection to a Hana database is operational."""
        ...


class IRedisConnection(Protocol):
    """Protocol for the Redis database connection."""

    def ping(self) -> ResponseT:
        """Veryfies if a connection to a Redis database is operational."""
        ...


class Probe(metaclass=SingletonMeta):
    """Probe is a class that aggregates methods to check essential connections."""

    _hana_conn: IHanaConnection | None = None
    _redis_conn: IRedisConnection | None = None
    _models: dict[str, (IModel | Embeddings)] | None = None
    _model_states: dict[str, bool] | None = None

    def __init__(
        self,
        hana_connection: Annotated[HanaConnection | None, field(default=None)],
        redis_connection: Annotated[RedisConnection | None, field(default=None)],
        models: dict[str, IModel | Embeddings] | None,
    ) -> None:
        self._hana_conn = hana_connection
        self._redis_conn = redis_connection
        self._models = {}
        self._model_states = {}
        if models:
            for name, model in models.items():
                self._models[name] = model
                self._model_states[name] = False

    def is_hana_connection_ready(self) -> bool:
        """Checks if the connection to the Hana database is operational."""
        if self._hana_conn:
            try:
                if self._hana_conn.isconnected():
                    logger.info("Hana DB connection is okay.")
                    return True
            except dbapi.Error as e:
                logger.error(f"Error while connecting to Hana DB: {e}")
        return False

    async def is_redis_connection_ready(self) -> bool:
        """Checks if the connection to the Redis database is operational."""
        if self._redis_conn:
            try:
                response = await self._redis_conn.ping()
                if response:
                    logger.info("Redis connection is okay.")
                    return True
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
        return False

    def are_model_connections_okay(self) -> bool:
        """Checks if the connections to LLMs is operational.
        Once a model was successfully cheched,
        it will not be checked again to avoid excessive token usage."""

        # Check if models or model states are unavailable and log a warning if so.
        if not self._models or not self._model_states:
            logger.warning("No models available for readiness check.")
            return False

        all_ready = True
        # Iterate through all models to check their readiness.
        for name, model in self._models.items():
            # Retrieve the current state of the model.
            model_state = self._model_states.get(name, False)
            if model_state:
                # Log if the model is already marked as ready.
                logger.info(f"{name} connection is okay.")
                continue

            try:
                response = None
                # Invoke the appropriate method based on the model type.
                if isinstance(model, IModel):
                    response = model.invoke("Test.")
                elif isinstance(model, Embeddings):
                    response = model.embed_query("Test.")

                if response:
                    # Update the model state and log readiness.
                    self._model_states[name] = True
                    logger.info(f"{name} connection is okay.")
                else:
                    # Log a warning if the model is not okay.
                    logger.warning(f"{name} connection is not working.")
                    all_ready = False

            except Exception as e:
                # Log an error if an exception occurs during readiness check.
                logger.error(f"{name} connection has an error: {e}")
                all_ready = False

        # Return the overall readiness status.
        return all_ready
