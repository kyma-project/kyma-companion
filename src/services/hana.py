import logging

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
    def reset(cls) -> None:
        """
        Reset the singleton instance and any associated resources.

        This method clears the stored instance and any related attributes,
        allowing the singleton to be reinitialized.
        """
        SingletonMeta.reset_instance(cls)
        cls.connection = None


def get_hana_connection() -> Hana:
    """Create a connection to the Hana database."""
    return Hana()
