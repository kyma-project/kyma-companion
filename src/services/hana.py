import logging
from collections.abc import Generator

from hdbcli import dbapi

from utils.settings import (
    DATABASE_PASSWORD,
    DATABASE_PORT,
    DATABASE_URL,
    DATABASE_USER,
)
from utils.singleton_meta import SingletonMeta


class HanaConnection(dbapi.Connection, metaclass=SingletonMeta):
    """
    Manages a singleton connection to the Hana database.

    This class establishes a connection to the Hana database using the provided
    credentials and configuration. It ensures that only one instance of the connection
    exists at any time by utilizing the SingletonMeta metaclass.
    """


def get_hana_connection() -> Generator[HanaConnection, None, None]:
    """Create a connection to the Hana database."""
    conn = HanaConnection(
        address=str(DATABASE_URL),
        port=DATABASE_PORT,
        user=str(DATABASE_USER),
        password=str(DATABASE_PASSWORD),
    )

    try:
        yield conn
    except dbapi.Error as e:
        logging.exception(f"Connection to Hana Cloud failed: {e}")
        return None
    except Exception as e:
        logging.exception(f"Unknown error occurred: {e}")
        return None
    finally:
        conn.close()
