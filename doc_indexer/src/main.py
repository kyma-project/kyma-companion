from indexing.indexer import MarkdownIndexer

from utils.hana import create_hana_connection
from utils.models import (
    create_embedding_factory,
    openai_embedding_creator,
)
from utils.settings import (
    DATABASE_PASSWORD,
    DATABASE_PORT,
    DATABASE_URL,
    DATABASE_USER,
    DOCS_PATH,
    DOCS_TABLE_NAME,
    EMBEDDING_MODEL_DEPLOYMENT_ID,
)


def main() -> None:
    """Entry function to run the indexer."""
    # init embedding model
    create_embedding = create_embedding_factory(openai_embedding_creator)
    embeddings_model = create_embedding(EMBEDDING_MODEL_DEPLOYMENT_ID)
    # setup connection to Hana Cloud DB
    hana_conn = create_hana_connection(
        DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD
    )

    indexer = MarkdownIndexer(DOCS_PATH, embeddings_model, hana_conn, DOCS_TABLE_NAME)
    indexer.index()


if __name__ == "__main__":
    main()
