from collections.abc import Callable

from hdbcli import dbapi

from utils.logging import get_logger
from utils.settings import (
    DATABASE_PASSWORD,
    DATABASE_PORT,
    DATABASE_URL,
    DATABASE_USER,
)
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)


class Hana(metaclass=SingletonMeta):
    """
    Manages a singleton connection to the Hana database.

    This class establishes a connection to the Hana database using the provided
    credentials and configuration. It ensures that only one instance of the connection
    exists at any time by utilizing the SingletonMeta metaclass.
    """

    connection: dbapi.Connection | None = None

    def __init__(
        self, connection_factory: Callable[[], dbapi.Connection] | None = None
    ) -> None:
        try:
            self.connection = (
                connection_factory() if connection_factory else _get_hana_connection()
            )
        except dbapi.Error as e:
            logger.error(f"Connection to Hana Cloud failed: {e}")
            self.connection = None
        except Exception as e:
            logger.error(f"Unknown error occurred: {e}")
            self.connection = None

    def is_connection_operational(self) -> bool:
        """
        Check if the HANA database is ready.

        Returns:
            bool: True if HANA is ready, False otherwise.
        """
        if not self.connection:
            logger.warning("HANA DB connection is not initialized.")
            return False

        try:
            if self.connection.isconnected():
                logger.info("HANA DB connection is ready.")
                return True
        except Exception as e:
            logger.error(f"Error while connecting to HANA DB: {e}")
            return False
        logger.info("HANA DB connection is not ready.")
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

    def get_connction(self) -> dbapi.Connection:
        """
        Get the current connection.

        Returns:
            dbapi.Connection: The current HANA database connection.
        """
        if not self.connection:
            logger.warning("HANA DB connection is not initialized.")
            raise ValueError("HANA DB connection is not initialized.")
        return self.connection


def _get_hana_connection() -> dbapi.Connection:
    """Do not use this function directly to create connections. Use the Hana() or get_hana() instead."""
    return dbapi.Connection(
        address=str(DATABASE_URL),
        port=DATABASE_PORT,
        user=str(DATABASE_USER),
        password=str(DATABASE_PASSWORD),
    )


def get_hana() -> Hana:
    """Create a connection to the Hana database."""
    return Hana()
