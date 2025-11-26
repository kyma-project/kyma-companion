import time

import httpx
from langchain_core.documents import Document

from services.metrics import CustomMetrics
from utils.logging import get_logger

logger = get_logger(__name__)


class DocumentGroundingRetriever:
    """Retriever for Document Grounding"""

    def __init__(
        self,
        api_url: str,
        client_id: str,
        client_secret: str,
        token_url: str,
        resource_group: str,
        data_repository_type: str = "help.sap.com",
        filter_id: str = "default",
    ):
        """
        Initialize the external API retriever.

        Args:
            api_url: Base URL for the AI API
            client_id: OAuth client ID
            client_secret: OAuth client secret
            token_url: URL to obtain access token
            resource_group: AI-Resource-Group header value
            data_repository_type: Type of data repository
            filter_id: Filter identifier for the search
        """
        self.api_url = api_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.resource_group = resource_group
        self.data_repository_type = data_repository_type
        self.filter_id = filter_id
        self._access_token: str | None = None
        self._token_expiry: float | None = None

    async def _get_access_token(self) -> str:
        """Get OAuth access token using client credentials."""
        # Check if we have a valid cached token
        if (
            self._access_token
            and self._token_expiry
            and time.time() < self._token_expiry
        ):
            return self._access_token

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

            self._access_token = token_data["access_token"]
            # Cache token with 5 minute buffer before expiry
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = time.time() + expires_in - 300

            return self._access_token

    def _parse_response_to_documents(self, response_data: dict) -> list[Document]:
        """
        Convert API response to LangChain Document objects.

        Args:
            response_data: The API response JSON

        Returns:
            List of Document objects
        """
        documents = []

        for result in response_data.get("results", []):
            for filter_result in result.get("results", []):
                data_repo = filter_result.get("dataRepository", {})

                for doc in data_repo.get("documents", []):
                    # Extract document-level metadata
                    doc_metadata = {}
                    for meta in doc.get("metadata", []):
                        key = meta.get("key")
                        value = meta.get("value", [])
                        if value:
                            doc_metadata[key] = value[0] if len(value) == 1 else value

                    # Process each chunk as a separate Document
                    for chunk in doc.get("chunks", []):
                        chunk_content = chunk.get("content", "")
                        chunk_metadata = doc_metadata.copy()

                        # Add chunk-specific metadata
                        chunk_metadata["chunk_id"] = chunk.get("id")
                        for meta in chunk.get("metadata", []):
                            key = meta.get("key")
                            value = meta.get("value", [])
                            if value:
                                chunk_metadata[key] = (
                                    value[0] if len(value) == 1 else value
                                )

                        # Add data repository info
                        chunk_metadata["data_repository_id"] = data_repo.get("id")
                        chunk_metadata["data_repository_title"] = data_repo.get("title")

                        documents.append(
                            Document(
                                page_content=chunk_content, metadata=chunk_metadata
                            )
                        )

        return documents

    async def aretrieve(self, query: str, top_k: int = 5) -> list[Document]:
        """
        Retrieve relevant documents based on the query using external API.

        Args:
            query: The search query
            top_k: Maximum number of chunks to retrieve

        Returns:
            List of Document objects
        """
        start_time = time.perf_counter()

        try:
            # Get access token
            access_token = await self._get_access_token()

            # Prepare request
            url = f"{self.api_url}/lm/document-grounding/retrieval/search"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "AI-Resource-Group": self.resource_group,
                "Content-Type": "application/json",
            }

            body = {
                "query": "Kyma " + query,
                "filters": [
                    {
                        "id": self.filter_id,
                        "searchConfiguration": {"maxChunkCount": top_k},
                        "dataRepositories": ["*"],
                        "dataRepositoryType": self.data_repository_type,
                        "dataRepositoryMetadata": [],
                        "documentMetadata": [],
                        "chunkMetadata": [],
                    }
                ],
            }

            # Make API call
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
                response_data = response.json()

            # Convert to Document objects
            docs = self._parse_response_to_documents(response_data)

            # Record success latency
            await CustomMetrics().record_hanadb_latency(
                time.perf_counter() - start_time, True
            )

            logger.info(f"Retrieved {len(docs)} documents for query: {query}")
            return docs

        except Exception as e:
            logger.exception(f"Error retrieving documents for query: {query}")
            await CustomMetrics().record_hanadb_latency(
                time.perf_counter() - start_time, False
            )
            raise e
