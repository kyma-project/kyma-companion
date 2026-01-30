import asyncio
import contextlib
from collections.abc import Callable

from hdbcli import dbapi

from utils.logging import get_logger
from utils.settings import (
    DATABASE_HEALTH_CHECK_INTERVAL,
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

    Includes a background health check that periodically validates the connection
    by executing a test query.
    """

    def __init__(self, connection_factory: Callable[[], dbapi.Connection] | None = None) -> None:
        # Initialize instance attributes
        self.connection: dbapi.Connection | None = None
        self._health_status: bool = False
        self._health_check_task: asyncio.Task | None = None
        self._retry_delay: int = 1  # Start at 1 second
        self._max_retry_delay: int = 60  # Cap at 60 seconds

        try:
            self.connection = connection_factory() if connection_factory else _get_hana_connection()
            self._health_status = bool(self.connection)
        except dbapi.Error as e:
            logger.error(f"Connection to Hana Cloud failed: {e}")
            self.connection = None
            self._health_status = False
        except Exception as e:
            logger.error(f"Unknown error occurred: {e}")
            self.connection = None
            self._health_status = False

    def is_connection_operational(self) -> bool:
        """
        Check if the HANA database is ready.

        Returns the health status maintained by the background health check task.
        This reflects whether the connection can execute queries.

        Returns:
            bool: True if HANA is ready, False otherwise.
        """
        return self._health_status

    def mark_unhealthy(self) -> None:
        """Mark the connection as unhealthy. Called when usage detects an error."""
        if self._health_status:
            logger.warning("Marking HANA connection as unhealthy")
        self._health_status = False

    def has_connection(self) -> bool:
        """Check if a connection exists."""
        return bool(self.connection)

    def start_health_check(self) -> None:
        """Start the background health check task."""
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("Started HANA health check background task")

    async def stop_health_check(self) -> None:
        """Stop the background health check task."""
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_check_task
            logger.info("Stopped HANA health check background task")

    async def _health_check_loop(self) -> None:
        """Background loop that periodically checks connection health."""
        while True:
            try:
                if await self._execute_health_check():
                    if not self._health_status:
                        logger.info("HANA health check passed after being unhealthy")
                    self._health_status = True
                    self._retry_delay = 1  # Reset on success
                    await asyncio.sleep(DATABASE_HEALTH_CHECK_INTERVAL)
                else:
                    if self._health_status:
                        logger.warning("HANA health check failed")
                    self._health_status = False
                    await asyncio.sleep(self._retry_delay)
                    self._retry_delay = min(self._retry_delay * 2, self._max_retry_delay)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Unexpected error in health check loop: {e}")
                self._health_status = False
                await asyncio.sleep(self._retry_delay)

    async def _execute_health_check(self) -> bool:
        """Execute a test query to verify connection is operational."""
        if not self.connection:
            return False

        try:
            # Run synchronous HANA query in thread pool
            result = await asyncio.to_thread(self._sync_health_check)
            return result
        except Exception as e:
            logger.debug(f"HANA health check failed: {e}")
            return False

    def _sync_health_check(self) -> bool:
        """Synchronous health check that executes a test query."""
        cursor = None
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1 FROM DUMMY")
            cursor.fetchone()
            return True
        except Exception:
            return False
        finally:
            if cursor:
                cursor.close()

    @classmethod
    def _reset_for_tests(cls) -> None:
        """
        Reset the singleton instance and any associated resources.

        This method clears the stored instance and any related attributes,
        allowing the singleton to be reinitialized.

        Only use for testing purpose.
        """
        SingletonMeta.reset_instance(cls)

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
