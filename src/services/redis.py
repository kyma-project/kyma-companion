import logging
from collections.abc import Generator

from redis.asyncio import Redis as AsyncRedis

from utils.settings import (
    REDIS_DB_NUMBER,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_SSL_ENABLED,
)
from utils.singleton_meta import SingletonMeta


class Redis(metaclass=SingletonMeta):
    """
    Manages a singleton connection to the Redis database.

    This class establishes a connection to the Redis database using the provided
    credentials and configuration. It ensures that only one instance of the connection
    exists at any time by utilizing the SingletonMeta metaclass.
    """

    connection: AsyncRedis | None = None

    def set_connection(self, connection: AsyncRedis) -> None:
        """
        sets the database connection for the service.

        args:
            connection (AsyncRedis): the database connection object.
        """
        self.connection = connection


def get_redis_connection() -> Generator[Redis, None, None]:
    """Create a connection to the Redis database."""
    try:
        redis = Redis()
        if not redis.connection:
            redis.set_connection(
                AsyncRedis(
                    host=str(REDIS_HOST),
                    port=REDIS_PORT,
                    db=REDIS_DB_NUMBER,
                    password=str(REDIS_PASSWORD),
                    ssl=REDIS_SSL_ENABLED,
                    ssl_ca_certs="/etc/secret/ca.crt" if REDIS_SSL_ENABLED else None,
                )
            )
        yield redis
    except Exception as e:
        logging.exception(f"Error with Redis connection: {e}")
        return None
