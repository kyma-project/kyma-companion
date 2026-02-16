"""Langfuse tracing service for LangGraph."""

from typing import Any

import scrubadub
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, ToolMessage
from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler

from agents.common.state import GraphInput
from services.k8s import IK8sClient, K8sClient
from utils.logging import get_logger
from utils.settings import (
    LANGFUSE_ENABLED,
    LANGFUSE_HOST,
    LANGFUSE_MASKING_MODE,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
    LangfuseMaskingModes,
)
from utils.singleton_meta import SingletonMeta
from utils.utils import string_to_bool

logger = get_logger(__name__)

REDACTED = "REDACTED"
EMPTY_OBJECT: dict[str, Any] = {}


def get_langfuse_metadata(user_id: str, session_id: str, tags: list[str]) -> dict:
    """
    Returns metadata for Langfuse traces.
    Args:
        user_id (str): The user ID.
        session_id (str): The session ID.
    """
    # check CallbackHandler._parse_langfuse_trace_attributes_from_metadata for possible keys.
    return {
        "langfuse_session_id": session_id,
        "langfuse_user_id": user_id,
        "langfuse_tags": tags,
    }


class LangfuseService(metaclass=SingletonMeta):
    """Service for Langfuse tracing integration with LangGraph."""

    def __init__(self):
        """Initialize the Langfuse service."""
        self.enabled = string_to_bool(str(LANGFUSE_ENABLED.lower()))
        self.masking_mode = LANGFUSE_MASKING_MODE
        self.data_scrubber = scrubadub.Scrubber()
        self.data_scrubber.remove_detector(scrubadub.detectors.UrlDetector)
        self.allowed_tools = ["search_kyma_doc", "fetch_kyma_resource_version"]

        if self.enabled:
            # Create/Configure Langfuse client (once at startup)
            Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                base_url=LANGFUSE_HOST,
                mask=self.masking_production_data,
            )
            # Access singleton instance and check authentication.
            langfuse = get_client()
            if langfuse.auth_check():
                logger.info("Langfuse client is authenticated and ready with host: {LANGFUSE_HOST}")
            else:
                logger.warning("Langfuse is enabled but Authentication failed. Disabling Langfuse.")
                self.enabled = False

    def get_callback_handler(
        self,
    ) -> BaseCallbackHandler | None:
        """Get a Langfuse callback handler for tracing.

        Returns:
            A Langfuse CallbackHandler if enabled, None otherwise.
        """
        if not self.enabled:
            return None

        try:
            return CallbackHandler()
        except Exception as e:
            logger.error(f"Failed to create Langfuse callback handler: {e}")
            return None

    def masking_production_data(self, *, data: Any, **kwargs: dict[str, Any]) -> Any:
        """
        Removes sensitive information from traces.

        Args:
            data (dict): The data containing sensitive information.

        Returns:
            dict: The data with sensitive information removed.
        """
        # First, check for critical information that should always be masked regardless of the masking mode.
        critical_masked = self._mask_critical(data)
        if critical_masked is not None:
            return critical_masked

        if self.masking_mode == LangfuseMaskingModes.DISABLED:
            # If masking is disabled, return the data unmasked.
            return data
        elif self.masking_mode == LangfuseMaskingModes.REDACTED:
            # If masking is set to REDACTED, return a placeholder string
            return REDACTED
        elif self.masking_mode == LangfuseMaskingModes.PARTIAL:
            return self._masking_mode_partial(data)
        elif self.masking_mode == LangfuseMaskingModes.FILTERED:
            return self._masking_mode_filtered(data)

        return REDACTED

    def _mask_critical(self, data: Any) -> Any:
        """Mask critical information such as Kubernetes client instances."""
        if isinstance(data, (IK8sClient, K8sClient)):
            return EMPTY_OBJECT
        return None

    def _masking_mode_partial(self, data: Any) -> Any:
        """Return only the user input and resource information. Everything else is redacted."""
        if isinstance(data, GraphInput):
            output = "\n".join([str(msg.content) for msg in reversed(data.messages)])
            if output:
                return self.data_scrubber.clean(output)

        return REDACTED

    def _masking_mode_filtered(self, data: Any) -> Any:  # noqa: C901
        """Recursively masks sensitive information in the provided data."""
        try:
            if not data or isinstance(data, int | float | bool):
                return data
            # If data is a GraphInput, sanitize the messages in reverse order for better readability.
            if isinstance(data, GraphInput):
                output = "\n".join([str(msg.content) for msg in reversed(data.messages)])
                return self.data_scrubber.clean(output if output else REDACTED)
            # If data is a string, sanitize it directly.
            elif isinstance(data, str):
                return self.data_scrubber.clean(data)
            elif isinstance(data, ToolMessage) and data.name not in self.allowed_tools:
                data.content = REDACTED
                return data
            elif isinstance(data, BaseMessage):
                data.content = self._get_cleaned_content(data.content)
                return data
            elif isinstance(data, dict) and "content" in data and "role" in data:
                # If data is a dictionary with role and content, sanitize the content.
                data["content"] = self.data_scrubber.clean(data["content"]) if data["role"] != "tool" else REDACTED
                return data
            elif isinstance(data, dict):
                for key, value in data.items():
                    # Recursively sanitize each value in the dictionary.
                    data[key] = self._masking_mode_filtered(value)
                return data
            elif isinstance(data, (IK8sClient, K8sClient)):
                # Mask Kubernetes client instances with an empty object.
                return EMPTY_OBJECT
            elif isinstance(data, list):
                # If data is a list, sanitize each item in the list (recursively).
                return [self._masking_mode_filtered(item) for item in data]
            elif hasattr(data, "to_dict"):
                return self._masking_mode_filtered(data.to_dict())
            elif hasattr(data, "model_dump"):
                return self._masking_mode_filtered(data.model_dump())
            elif hasattr(data, "model_dump_json"):
                return self._masking_mode_filtered(data.model_dump_json())
            return f"{REDACTED} - Unsupported data type ({type(data)}) for masking."
        except Exception as e:
            return f"Error while masking data: {e}"

    def _get_cleaned_content(self, content: Any) -> Any:
        """
        Helper function to clean the content of a message.
        """
        if isinstance(content, str):
            return self.data_scrubber.clean(content)
        return f"Error while masking message content: content (type: {type(content)}) is not a string."
