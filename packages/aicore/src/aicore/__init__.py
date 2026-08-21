"""SAP AI Core client and LangChain model adapters."""

from aicore.client import AICoreClient
from aicore.models.anthropic import AnthropicAdapter
from aicore.models.embeddings import OpenAIEmbeddingsAdapter
from aicore.models.gemini import GeminiAdapter
from aicore.models.openai import OpenAIAdapter

__all__ = [
    "AICoreClient",
    "AnthropicAdapter",
    "GeminiAdapter",
    "OpenAIAdapter",
    "OpenAIEmbeddingsAdapter",
]
