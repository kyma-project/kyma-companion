from collections.abc import Callable

from redis.asyncio import Redis as AsyncRedis

from utils.logging import get_logger
from utils.settings import (
    REDIS_DB_NUMBER,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_SSL_ENABLED,
)
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)


class Redis(metaclass=SingletonMeta):
    """
    Manages a singleton connection to the Redis database.

    This class establishes a connection to the Redis database using the provided
    credentials and configuration. It ensures that only one instance of the connection
    exists at any time by utilizing the SingletonMeta metaclass.
    """

    connection: AsyncRedis | None = None

    def __init__(
        self, connection_factory: Callable[[], AsyncRedis] | None = None
    ) -> None:
        try:
            self.connection = (
                connection_factory() if connection_factory else _get_redis_connection()
            )
        except Exception as e:
            logger.error(f"Error with Redis connection: {e}")
            self.connection = None

    async def is_connection_operational(self) -> bool:
        """
        Check if the Redis service is is_connection_operational.
        """
        if not self.connection:
            logger.error("Redis connection is not initialized.")
            return False

        try:
            if await self.connection.ping():
                logger.debug("Redis connection is ready.")
                return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False
        logger.info("Redis connection is not ready.")
        return False

    def has_connection(self) -> bool:
        """Check if a connection exists."""
        return bool(self.connection)

    @classmethod
    def _reset_for_tests(cls) -> None:
        """
        Reset the singleton instance and any associated resources.

        This method clears the stored instance and any related attributes,
        allowing the singleton to be reinitialized.

        Only use for testing purpose.
        """
        SingletonMeta.reset_instance(cls)
        cls.connection = None

    def get_connection(self) -> AsyncRedis:
        """Get the current Redis connection."""
        if self.connection is None:
            logger.error("Redis connection is not initialized.")
            raise ValueError("Redis connection is not initialized.")
        return self.connection


def _get_redis_connection() -> AsyncRedis:
    return AsyncRedis(
        host=str(REDIS_HOST),
        port=REDIS_PORT,
        db=REDIS_DB_NUMBER,
        password=str(REDIS_PASSWORD),
        ssl=REDIS_SSL_ENABLED,
        ssl_ca_certs="/etc/secret/ca.crt" if REDIS_SSL_ENABLED else None,
    )


def get_redis() -> Redis:
    """Create a connection to the Redis database."""
    return Redis()
