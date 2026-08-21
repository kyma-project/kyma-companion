"""OpenAI chat model adapter for SAP AI Core."""

from typing import Any

from langchain_openai import ChatOpenAI

from aicore.client import AICoreClient


class OpenAIAdapter:
    """Wraps ChatOpenAI with SAP AI Core deployment URL and bearer token."""

    def __init__(self, client: AICoreClient, deployment_id: str, model_name: str, **kwargs: Any) -> None:
        deployment_url = client.get_deployment_url(deployment_id)
        token = client.get_token()
        self._llm = ChatOpenAI(
            base_url=f"{deployment_url}/chat/completions",
            api_key=token,  # type: ignore[arg-type]
            model=model_name,
            **kwargs,
        )

    @property
    def llm(self) -> ChatOpenAI:
        """Return the underlying ChatOpenAI instance."""
        return self._llm
