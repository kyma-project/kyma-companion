import logging
from collections.abc import Generator

from redis.asyncio import Redis

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


class AsyncRedis(metaclass=SingletonMeta):
    """An asynchronous Redis client wrapper using SingletonMeta."""

    def __init__(self, redis_connection: Redis) -> None:
        self.connection = redis_connection


def get_redis_connection() -> Generator[AsyncRedis, None, None]:
    """Create a connection to the Redis database."""
    conn = Redis(
        host=str(REDIS_HOST),
        port=REDIS_PORT,
        db=REDIS_DB_NUMBER,
        password=str(REDIS_PASSWORD),
        ssl=REDIS_SSL_ENABLED,
        ssl_ca_certs="/etc/secret/ca.crt" if REDIS_SSL_ENABLED else None,
    )

    if REDIS_SSL_ENABLED:
        logger.info("Redis connection established with SSL.")
    else:
        logger.info("Redis connection established.")

    try:
        yield AsyncRedis(conn)
    except Exception as e:
        logging.exception(f"Error with Redis connection: {e}")
        return
