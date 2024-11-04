import logging
import os
import sys

from decouple import Config, RepositoryEnv, config
from dotenv import find_dotenv, load_dotenv


def is_running_pytest() -> bool:
    """Check if the code is running with pytest.
    This is needed to identify if tests are running.
    """
    return "pytest" in sys.modules


project_root = os.path.dirname(os.path.abspath(__file__))

if is_running_pytest():
    # Use .test.env for tests
    env_path = find_dotenv(".env.test")
    if env_path and os.path.exists(env_path):
        config = Config(RepositoryEnv(env_path))
        load_dotenv(env_path)
    else:
        logging.warning("No .test.env file found. Using .env test file.")
        load_dotenv()
else:
    load_dotenv()


LOG_LEVEL = config("LOG_LEVEL", default="INFO")
EMBEDDING_MODEL_DEPLOYMENT_ID = config("EMBEDDING_MODEL_DEPLOYMENT_ID")
EMBEDDING_MODEL_NAME = config("EMBEDDING_MODEL_NAME")

TMP_DIR = config("TMP_DIR", default=os.path.join(project_root, "tmp"))
DOCS_SOURCES_FILE_PATH = config(
    "DOCS_SOURCES_FILE_PATH", default=os.path.join(project_root, "docs_sources.json")
)
DOCS_PATH = config("DOCS_PATH", default="data/output")
DOCS_TABLE_NAME = config("DOCS_TABLE_NAME", default="kyma_docs")
CHUNKS_BATCH_SIZE = config("CHUNKS_BATCH_SIZE", cast=int, default=200)

DATABASE_URL = config("DATABASE_URL")
DATABASE_PORT = config("DATABASE_PORT", cast=int)
DATABASE_USER = config("DATABASE_USER")
DATABASE_PASSWORD = config("DATABASE_PASSWORD")
