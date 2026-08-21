"""OpenAI embeddings adapter for SAP AI Core."""

from langchain_openai import OpenAIEmbeddings

from aicore.client import AICoreClient


class OpenAIEmbeddingsAdapter:
    """Wraps OpenAIEmbeddings with SAP AI Core deployment URL and bearer token."""

    def __init__(self, client: AICoreClient, deployment_id: str, model_name: str) -> None:
        deployment_url = client.get_deployment_url(deployment_id)
        token = client.get_token()
        self._embeddings = OpenAIEmbeddings(
            base_url=f"{deployment_url}",
            api_key=token,  # type: ignore[arg-type]
            model=model_name,
        )

    @property
    def embeddings(self) -> OpenAIEmbeddings:
        """Return the underlying OpenAIEmbeddings instance."""
        return self._embeddings
