
from langchain_core.pydantic_v1 import BaseModel
from langchain_core.tools import tool

from rag.retriever import HanaDBRetriever
from utils.hana import create_hana_connection
from utils.models.factory import ModelType, ModelFactory
from utils.settings import DATABASE_PASSWORD, DATABASE_PORT, DATABASE_URL, DATABASE_USER, DOC_TABLE_NAME
from langchain_core.embeddings import Embeddings

# setup connection to Hana Cloud DB

class SearchKymaDocArgs(BaseModel):
    """Arguments for the search_kyma_doc tool."""

    query: str

def create_search_kyma_doc_tool(embedding_model: Embeddings):
  hana_conn = create_hana_connection(
    DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD
  )
  retriever = HanaDBRetriever(embedding_model, hana_conn, DOC_TABLE_NAME)
  
  @tool(infer_schema=False, args_schema=SearchKymaDocArgs)
  def search_kyma_doc_tool(query: str) -> str:
      """Search through Kyma documentation for relevant information.
      Provide a search query to find information about Kyma concepts, features, or components."""
      
      docs = retriever.retrieve(query)
      
      if len(docs) == 0:
          return "No relevant documentation found."
      
      docs_str = "\n".join([doc.page_content for doc in docs])
      return docs_str
    
  return search_kyma_doc_tool
