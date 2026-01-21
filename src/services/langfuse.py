from typing import Any, Protocol

import scrubadub
from aiohttp import BasicAuth
from langchain_core.messages import BaseMessage, ToolMessage
from langfuse.callback import CallbackHandler

from agents.common.state import GraphInput
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

REDACTED = "REDACTED"


class ILangfuseService(Protocol):
    """Service interface"""

    def handler(self) -> CallbackHandler:
        """Returns the callback handler"""
        ...

    def masking_production_data(self, data: str) -> str:
        """
        masking_production_data removes sensitive information from traces
        if Kyma-Companion runs in production mode (LANGFUSE_DEBUG_MODE=false).
        """
        ...


def get_langfuse_metadata(user_id: str, session_id: str) -> dict:
    """
    Returns metadata for Langfuse traces.
    Args:
        user_id (str): The user ID.
        session_id (str): The session ID.
    """
    return {
        "langfuse_session_id": session_id,
        "langfuse_user_id": user_id,
    }


class LangfuseService(metaclass=SingletonMeta):
    """
    A class to interact with the Langfuse API.

    Attributes:
        base_url (str): The base URL for the Langfuse API, set to LANGFUSE_HOST.
        public_key (str): The public key used for authentication, set to LANGFUSE_PUBLIC_KEY.
        secret_key (str): The secret key used for authentication, set to LANGFUSE_SECRET_KEY.
        auth (BasicAuth): An authentication object created using the public and secret keys.
        masking_mode (str): Data masking options, set LANGFUSE_MASKING_MODE.
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
        self.masking_mode = LANGFUSE_MASKING_MODE
        self.data_scrubber = scrubadub.Scrubber()
        self.data_scrubber.remove_detector(scrubadub.detectors.UrlDetector)

    @property
    def handler(self) -> CallbackHandler:
        """Returns the callback handler"""
        return self._handler

    def masking_production_data(self, data: Any) -> Any:
        """
        Removes sensitive information from traces.

        Args:
            data (dict): The data containing sensitive information.

        Returns:
            dict: The data with sensitive information removed.
        """
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
            elif isinstance(data, ToolMessage):
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
