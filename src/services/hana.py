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


class Hana(metaclass=SingletonMeta):
    """
    Manages a singleton connection to the Hana database.

    This class establishes a connection to the Hana database using the provided
    credentials and configuration. It ensures that only one instance of the connection
    exists at any time by utilizing the SingletonMeta metaclass.
    """

    connection: dbapi.Connection | None = None

    def set_connection(self, connection: dbapi.Connection) -> None:
        """
        sets the database connection for the service.

        args:
            connection (dbapi.connection): the database connection object.
        """
        self.connection = connection


def get_hana_connection() -> Generator[Hana, None, None]:
    """Create a connection to the Hana database."""
    try:
        hana = Hana()
        if not hana.connection:
            hana.set_connection(
                dbapi.Connection(
                    address=str(DATABASE_URL),
                    port=DATABASE_PORT,
                    user=str(DATABASE_USER),
                    password=str(DATABASE_PASSWORD),
                )
            )
        yield hana
    except dbapi.Error as e:
        logging.exception(f"Connection to Hana Cloud failed: {e}")
        return None
    except Exception as e:
        logging.exception(f"Unknown error occurred: {e}")
        return None
