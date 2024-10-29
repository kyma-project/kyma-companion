
from langchain_core.pydantic_v1 import BaseModel
from langchain_core.tools import tool

from agents.kyma.tools.retriever import (
    Retriever,
    create_embedding_factory,
    create_hana_connection,
    openai_embedding_creator,
)
from utils.settings import DATABASE_PASSWORD, DATABASE_PORT, DATABASE_URL, DATABASE_USER, EMBEDDING_MODEL_DEPLOYMENT_ID

create_embedding = create_embedding_factory(openai_embedding_creator)
embeddings_model = create_embedding(EMBEDDING_MODEL_DEPLOYMENT_ID)
# setup connection to Hana Cloud DB
hana_conn = create_hana_connection(
    DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD
)
table_name = "kyma_os_docs"

class SearchKymaDocArgs(BaseModel):
    """Arguments for the search_kyma_doc tool."""

    query: str


@tool(infer_schema=False, args_schema=SearchKymaDocArgs)
def search_kyma_doc_tool(query: str) -> str:
    """Search through Kyma documentation for relevant information.
    Provide a search query to find information about Kyma concepts, features, or components."""
    
    retriever = Retriever(embeddings_model, hana_conn, table_name)
    docs = retriever.retrieve(query)
    
    if len(docs) == 0:
        return "No relevant documentation found."
    
    docs_str = "\n".join([doc.page_content for doc in docs])
    return docs_str