import os
import uuid

import pytest
from utils.hana import create_hana_connection
from utils.utils import sanitize_table_name

from utils.settings import (
    DATABASE_PASSWORD,
    DATABASE_PORT,
    DATABASE_URL,
    DATABASE_USER,
    EMBEDDING_MODEL_NAME,
    get_embedding_model_config,
)
from utils.utils import sanitize_table_name


@pytest.fixture(scope="module")
def require_credentials():
    """Fail fast if the config was not loaded or the embedding model is not configured."""
    try:
        get_embedding_model_config(EMBEDDING_MODEL_NAME)
    except Exception as e:
        pytest.fail(f"Credentials not available: {e}")


@pytest.fixture(scope="module")
def hana_conn(require_credentials):
    conn = create_hana_connection(DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD)
    if not conn:
        pytest.fail("Failed to create Hana DB connection.")
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def e2e_table_name() -> str:
    # In CI, DOCS_TABLE_NAME is set to kc_pr_<PR number> so orphaned tables
    # can be traced back to the PR that created them. Locally we always use a
    # UUID to ensure uniqueness and avoid dirty state from crashed runs.
    ci_table_name = os.getenv("DOCS_TABLE_NAME", "")
    base = ci_table_name if ci_table_name.startswith("kc_pr_") else f"test_e2e_{uuid.uuid4().hex}"
    return sanitize_table_name(f"{base}_e2e")
