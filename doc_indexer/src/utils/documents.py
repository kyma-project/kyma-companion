from langchain.schema import Document
from langchain_community.document_loaders import DirectoryLoader, TextLoader

from utils.logging import get_logger

logger = get_logger(__name__)


def load_documents(docs_path: str) -> list[Document]:
    try:
        loader = DirectoryLoader(docs_path, loader_cls=TextLoader, recursive=True)
        docs = loader.load()
        return docs
    except FileNotFoundError:
        logger.exception("Directory %s not found", docs_path)
        raise
    except Exception:
        logger.exception("Error while loading documents from %s", docs_path)
        raise
