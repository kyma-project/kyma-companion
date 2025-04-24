from redis import Redis


def create_redis_connection(host: str, port: int, db: int, password: str) -> Redis:
    """
    Factory function to create a Redis connection.

    Args:
        host (str): Redis server host.
        port (int): Redis server port.
        db (int): Redis database number.
        password (str): Redis password.

    Returns:
        Redis: A Redis connection instance.
    """
    return Redis(host=host, port=port, db=db, password=password)
