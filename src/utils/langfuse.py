from typing import AnyStr, Any

import requests
from langfuse.callback import CallbackHandler
from requests.auth import HTTPBasicAuth

from agents.common.constants import SUCCESS_CODE
from utils.common import MetricsResponse
from utils.settings import (
    LANGFUSE_ENABLED,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)
from utils.utils import string_to_bool

handler = CallbackHandler(
    secret_key=LANGFUSE_SECRET_KEY,
    public_key=LANGFUSE_PUBLIC_KEY,
    host=LANGFUSE_HOST,
    enabled=string_to_bool(LANGFUSE_ENABLED),
)


class LangfuseAPI:
    """
    A class to interact with the Langfuse API.

    Attributes:
        base_url (str): The base URL for the Langfuse API,  set to LANGFUSE_HOST.
        public_key (str): The public key used for authentication,  set to LANGFUSE_PUBLIC_KEY.
        secret_key (str): The secret key used for authentication,  set to LANGFUSE_SECRET_KEY.
        auth (HTTPBasicAuth): An authentication object created using the public and secret keys.
    """

    def __init__(self):
        self.base_url = LANGFUSE_HOST
        self.public_key = LANGFUSE_PUBLIC_KEY
        self.secret_key = LANGFUSE_SECRET_KEY
        self.auth = HTTPBasicAuth(self.public_key, self.secret_key)

    def get_daily_metrics(
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

        response = requests.get(url, params=params, auth=self.auth)

        if response.status_code == SUCCESS_CODE:
            # Parse the JSON response into the MetricsResponse Pydantic model
            return MetricsResponse(**response.json())
        else:
            return response.raise_for_status()

    def get_total_token_usage(
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
        metrics = self.get_daily_metrics(from_timestamp, to_timestamp, tags)

        # Calculate the total token utilization
        total_token_utilization = 0
        for daily_metric in metrics.data:
            for usage in daily_metric.usage:
                total_token_utilization += usage.total_usage

        return total_token_utilization
