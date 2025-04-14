import logging

from hdbcli import dbapi


def create_hana_connection(
    url: str, port: int, user: str, password: str
) -> dbapi.Connection | None:
    """Create a connection to the Hana Cloud DB."""
    try:
        connection = dbapi.connect(
            address=url,
            port=port,
            user=user,
            password=password,
        )
        return connection
    except dbapi.Error as e:
        logging.exception(f"Connection to Hana Cloud failed: {e}")
    except Exception as e:
        logging.exception(f"Unknown error occurred: {e}")
    return None
