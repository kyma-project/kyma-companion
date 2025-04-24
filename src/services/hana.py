import logging
from collections.abc import Generator

from hdbcli import dbapi

from utils.settings import (
    DATABASE_PASSWORD,
    DATABASE_PORT,
    DATABASE_URL,
    DATABASE_USER,
)


def get_hana_connection() -> Generator[dbapi.Connection, None, None]:
    """Create a connection to the Hana Cloud DB."""

    conn = dbapi.connect(
        address=str(DATABASE_URL),
        port=DATABASE_PORT,
        user=str(DATABASE_USER),
        password=str(DATABASE_PASSWORD),
    )

    try:
        yield conn
    except dbapi.Error as e:
        logging.exception(f"Connection to Hana Cloud failed: {e}")
        return None
    except Exception as e:
        logging.exception(f"Unknown error occurred: {e}")
        return None
    finally:
        conn.close()
