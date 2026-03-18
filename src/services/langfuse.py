"""Langfuse tracing service."""

import copy
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, ToolMessage
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from services.k8s import IK8sClient, K8sClient
from services.pii_detector import scrub_pii
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

# Tools whose output is safe to include in traces
ALLOWED_TOOL_NAMES = ["search_kyma_doc", "fetch_kyma_resource_version"]


def get_langfuse_metadata(user_id: str, session_id: str, tags: list[str]) -> dict:
    """Returns metadata for Langfuse traces."""
    return {
        "langfuse_session_id": session_id,
        "langfuse_user_id": user_id,
        "langfuse_tags": tags,
    }


class LangfuseService(metaclass=SingletonMeta):
    """Service for Langfuse tracing integration."""

    def __init__(self):
        """Initialize the Langfuse service."""
        self.enabled = string_to_bool(str(LANGFUSE_ENABLED.lower()))
        self.masking_mode = LANGFUSE_MASKING_MODE
        self.allowed_tools = ALLOWED_TOOL_NAMES

        if self.enabled:
            Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                base_url=LANGFUSE_HOST,
                mask=self.masking_production_data,
            )
            logger.debug(f"Langfuse client is initialized with host: {LANGFUSE_HOST}")
        else:
            logger.debug("Langfuse is disabled. No client will be initialized.")

    def get_callback_handler(self) -> BaseCallbackHandler | None:
        """Get a Langfuse callback handler for tracing."""
        if not self.enabled:
            return None

        try:
            return CallbackHandler()
        except Exception as e:
            logger.error(f"Failed to create Langfuse callback handler: {e}")
            return None

    def masking_production_data(self, *, data: Any, **kwargs: dict[str, Any]) -> Any:
        """Removes sensitive information from traces."""
        critical_masked = self._mask_critical(data)
        if critical_masked is not None:
            return critical_masked

        if self.masking_mode == LangfuseMaskingModes.DISABLED:
            return data
        elif self.masking_mode == LangfuseMaskingModes.REDACTED:
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
        if isinstance(data, str):
            return scrub_pii(data)
        if isinstance(data, dict) and "content" in data and "role" in data:
            content = data.get("content", "")
            if isinstance(content, str):
                return scrub_pii(content)
        return REDACTED

    def _masking_mode_filtered(self, data: Any) -> Any:  # noqa: C901
        """Recursively masks sensitive information in the provided data."""
        try:
            if not data or isinstance(data, int | float | bool):
                return data
            if isinstance(data, str):
                return scrub_pii(copy.copy(data))
            elif isinstance(data, ToolMessage) and data.name not in self.allowed_tools:
                data = copy.deepcopy(data)
                data.content = REDACTED
                return data
            elif isinstance(data, BaseMessage):
                data = copy.deepcopy(data)
                data.content = self._get_cleaned_content(data.content)
                return data
            elif isinstance(data, dict) and "content" in data and "role" in data:
                data = copy.deepcopy(data)
                data["content"] = scrub_pii(data["content"]) if data["role"] != "tool" else REDACTED
                return data
            elif isinstance(data, dict):
                result = {}
                for key, value in data.items():
                    result[key] = self._masking_mode_filtered(value)
                return result
            elif isinstance(data, (IK8sClient, K8sClient)):
                return EMPTY_OBJECT
            elif isinstance(data, list):
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
        """Clean the content of a message using regex PII scrubbing."""
        if isinstance(content, str):
            return scrub_pii(content)
        return f"Error while masking message content: content (type: {type(content)}) is not a string."
