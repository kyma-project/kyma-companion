from hdbcli import dbapi

from utils.logging import get_logger

logger = get_logger(__name__)


def create_hana_connection(url: str, port: int, user: str, password: str) -> dbapi.Connection | None:
    """Create a connection to the Hana Cloud DB."""
    try:
        connection = dbapi.connect(
            address=url,
            port=port,
            user=user,
            password=password,
        )
        return connection
    except dbapi.Error:
        logger.exception("Connection to Hana Cloud failed.")
    except Exception:
        logger.exception("Unknown error occurred.")
    return None
