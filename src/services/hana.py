import logging

from hdbcli import dbapi

from utils.settings import (
    DATABASE_PASSWORD,
    DATABASE_PORT,
    DATABASE_URL,
    DATABASE_USER,
)
from utils.singleton_meta import SingletonMeta


class Hana(metaclass=SingletonMeta):
    """
    Manages a singleton connection to the Hana database.

    This class establishes a connection to the Hana database using the provided
    credentials and configuration. It ensures that only one instance of the connection
    exists at any time by utilizing the SingletonMeta metaclass.
    """

    connection: dbapi.Connection | None = None

    def __init__(self) -> None:
        try:
            self.connection = dbapi.Connection(
                address=str(DATABASE_URL),
                port=DATABASE_PORT,
                user=str(DATABASE_USER),
                password=str(DATABASE_PASSWORD),
            )
        except dbapi.Error as e:
            logging.exception(f"Connection to Hana Cloud failed: {e}")
            self.connection = None
        except Exception as e:
            logging.exception(f"Unknown error occurred: {e}")
            self.connection = None


def get_hana_connection() -> Hana:
    """Create a connection to the Hana database."""
    return Hana()
