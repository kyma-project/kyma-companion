from typing import Any, Protocol

from aiohttp import BasicAuth, ClientSession
from langfuse.callback import CallbackHandler

from agents.common.constants import SUCCESS_CODE
from utils.common import MetricsResponse
from utils.settings import (
    LANGFUSE_DEBUG_MODE,
    LANGFUSE_ENABLED,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)
from utils.singleton_meta import SingletonMeta
from utils.utils import string_to_bool


class ILangfuseService(Protocol):
    """Service interface"""

    def handler(self) -> CallbackHandler:
        """Returns the callback handler"""
        ...

    async def get_daily_metrics(
        self,
        from_timestamp: str,
        to_timestamp: str,
        tags: Any = None,
        user_id: Any = None,
    ) -> MetricsResponse | None:
        """
        Fetch daily metrics from the Langfuse API."""
        ...

    async def get_total_token_usage(
        self, from_timestamp: str, to_timestamp: str, tags: Any = None
    ) -> int:
        """
        Calculate the total token utilization by each cluster filtered by tags.
        """
        ...

    def masking_production_data(self, data: str) -> str:
        """
        masking_production_data removes sensitive information from traces
        if Kyma-Companion runs in production mode (LANGFUSE_DEBUG_MODE=false).
        """
        ...


class LangfuseService(metaclass=SingletonMeta):
    """
    A class to interact with the Langfuse API.

    Attributes:
        base_url (str): The base URL for the Langfuse API, set to LANGFUSE_HOST.
        public_key (str): The public key used for authentication, set to LANGFUSE_PUBLIC_KEY.
        secret_key (str): The secret key used for authentication, set to LANGFUSE_SECRET_KEY.
        auth (BasicAuth): An authentication object created using the public and secret keys.
        debug_enabled (bool): A boolean flag to enable debug mode, set to LANGFUSE_DEBUG_MODE.
        _handler (CallbackHandler) : A callback handler for langfuse.
    """

    def __init__(self):
        self.base_url = str(LANGFUSE_HOST)
        self.public_key = str(LANGFUSE_PUBLIC_KEY)
        self.secret_key = str(LANGFUSE_SECRET_KEY)
        self.auth = BasicAuth(self.public_key, self.secret_key)
        self._handler = CallbackHandler(
            secret_key=self.secret_key,
            public_key=self.public_key,
            host=self.base_url,
            enabled=string_to_bool(str(LANGFUSE_ENABLED)),
            mask=self.masking_production_data,
        )
        self.debug_enabled = string_to_bool(str(LANGFUSE_DEBUG_MODE))

    @property
    def handler(self) -> CallbackHandler:
        """Returns the callback handler"""
        return self._handler

    def masking_production_data(self, data: str) -> str:
        """
        Removes sensitive information from traces.

        Args:
            data (dict): The data containing sensitive information.

        Returns:
            dict: The data with sensitive information removed.
        """
        if not self.debug_enabled:
            return "REDACTED"
        return data

    async def get_daily_metrics(
        self,
        from_timestamp: str,
        to_timestamp: str,
        tags: Any = None,
        user_id: Any = None,
    ) -> MetricsResponse | None:
        """
        Fetch daily metrics from the Langfuse API.

        :param from_timestamp: Start timestamp in ISO format (e.g., '2025-01-08T13:50:56.406Z').
        :param to_timestamp: End timestamp in ISO format (e.g., '2025-12-16T13:50:56.406Z').
        :param tags: Optional tags to filter metrics based on tags.
        :param user_id: Optional userId to filter metrics based on user id.
        :return: Parsed MetricsResponse object.
        """
        url = f"{self.base_url}/api/public/metrics/daily"

        params = {
            "fromTimestamp": from_timestamp,
            "toTimestamp": to_timestamp,
        }

        if tags:
            params["tags"] = tags

        if user_id:
            params["userId"] = user_id

        async with ClientSession() as session, session.get(
            url, params=params, auth=self.auth
        ) as response:
            if response.status == SUCCESS_CODE:
                # Parse the JSON response into the MetricsResponse Pydantic model
                data = await response.json()
                return MetricsResponse(**data)
            # If status is not successful, raise the HTTP error
            response.raise_for_status()
            return None

    async def get_total_token_usage(
        self, from_timestamp: str, to_timestamp: str, tags: Any = None
    ) -> int:
        """
        Calculate the total token utilization by each cluster filtered by tags.

        :param from_timestamp: Start timestamp in ISO format (e.g., '2025-01-08T13:50:56.406Z').
        :param to_timestamp: End timestamp in ISO format (e.g., '2025-12-16T13:50:56.406Z').
        :param tags: Optional tags to filter metrics (e.g., 'ClusterID').
        :return: Total token utilization as an integer.
        """
        # Fetch the daily metrics
        metrics = await self.get_daily_metrics(from_timestamp, to_timestamp, tags)

        # Calculate the total token utilization
        total_token_utilization = 0
        if metrics and metrics.data:
            for daily_metric in metrics.data:
                for usage in daily_metric.usage:
                    total_token_utilization += usage.total_usage
        return total_token_utilization
