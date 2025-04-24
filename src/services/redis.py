import logging
from collections.abc import Generator

from redis import Redis

from utils.settings import (
    REDIS_DB_NUMBER,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)


def get_redis_connection() -> Generator[Redis, None, None]:
    """Create a connection to the Redis database."""
    conn = Redis(
        host=str(REDIS_HOST),
        port=REDIS_PORT,
        db=REDIS_DB_NUMBER,
        password=str(REDIS_PASSWORD),
    )
    try:
        yield conn
    except Exception as e:
        logging.exception(f"Error with Redis connection: {e}")
        raise
    finally:
        conn.close()
