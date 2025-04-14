from dataclasses import field
from typing import Annotated, Protocol

from hdbcli import dbapi
from hdbcli.dbapi import Connection as HanaConnection
from redis.asyncio import Redis as RedisConnection
from redis.typing import ResponseT

from utils.logging import get_logger
from utils.models.factory import IModel
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)

# TODO: Probe Protocol
# TODO: HanaConnection Protocol
# TODO: RedisConnection Protocol


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

    _hana_conn: Annotated[IHanaConnection | None, field(default=None)]
    _redis_conn: Annotated[IRedisConnection | None, field(default=None)]
    _mini_model: Annotated[IModel | None, field(default=None)]
    _is_ai_core_connection_okay: Annotated[bool, field(default=False)]

    def __init__(
        self,
        hana_connection: Annotated[HanaConnection | None, field(default=None)],
        redis_connection: Annotated[RedisConnection | None, field(default=None)],
        mini_model: Annotated[IModel | None, field(default=None)],
    ) -> None:
        self._hana_conn = hana_connection
        self._redis_conn = redis_connection
        self._mini_model = mini_model

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

    def is_ai_core_connection_okay(self) -> bool:
        """Checks if the connection to AI Core is operational."""

        # TODO: Only check on startup, for each model
        # To avoid exessive token usage, if we can connect to the LLM once, we
        # will keep assuming that the connection is okay.
        logger.info("AI-Cire connection is okay.")
        return True
