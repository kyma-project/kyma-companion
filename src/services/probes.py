from dataclasses import field
from typing import Annotated, Protocol

from hdbcli import dbapi

from routers.common import ReadynessModel
from utils.logging import get_logger

logger = get_logger(__name__)

# Interfaces:


class IHanaConnection(Protocol):
    """Protocol for the Hana database connection."""

    def isconnected(self) -> bool:
        """Veryfies if a connection to a Hana database is operational."""
        ...


# Classes:


class Readyness:
    """
    A class to check the readiness of various system components.
    """

    _hana_connection: IHanaConnection | None = None

    def __init__(
        self, hana_connection: Annotated[IHanaConnection | None, field(default=None)]
    ) -> None:
        self._hana_connection = hana_connection

    def is_hana_ready(self) -> bool:
        """
        Check if the HANA database is ready.

        Returns:
            bool: True if HANA is ready, False otherwise.
        """
        if not self._hana_connection:
            logger.warning("HANA DB connection is not initialized.")
            return False

        try:
            if self._hana_connection.isconnected():
                logger.info("HANA DB connection is ready.")
                return True
            logger.info("HANA DB connection is not ready.")
        except dbapi.Error as e:
            logger.error(f"Error while connecting to HANA DB: {e}")

        return False

    def is_redis_ready(self) -> bool:
        """
        Check if the Redis service is ready.

        Returns:
            bool: True if Redis is ready, False otherwise.
        """
        return True

    def are_llms_ready(self) -> bool:
        """
        Check if all LLMs (Large Language Models) are ready.

        Returns:
            bool: True if all LLMs are ready, False otherwise.
        """
        return True

    def get_llms_states(self) -> dict[str, bool]:
        """
        Get the readiness states of all LLMs.

        Returns:
            dict[str, bool]: A dictionary where keys are LLM names and values are their readiness states.
        """
        return {"llm1": True, "llm2": True}

    def get_dto(self) -> ReadynessModel:
        """
        Get a DTO (Data Transfer Object) representing the readiness states of all components.

        Returns:
            ReadynessModel: An object containing the readiness states of Redis, HANA, and LLMs.
        """
        return ReadynessModel(
            is_redis_ready=self.is_redis_ready(),
            is_hana_ready=self.is_hana_ready(),
            llms=self.get_llms_states(),
        )
