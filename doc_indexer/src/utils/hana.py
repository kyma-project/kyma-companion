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


def drop_table(connection: dbapi.Connection, db_user: str, table_name: str) -> None:
    """Drop a table from HANA if it exists. Silently ignores missing tables (error 259)."""
    ERR_SQL_INV_TABLE = 259
    sql = f'DROP TABLE "{db_user}"."{table_name}"'
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()
        logger.info(f"Dropped table {table_name}.")
    except dbapi.ProgrammingError as e:
        if e.args and e.args[0] == ERR_SQL_INV_TABLE:
            logger.warning(f"Table {table_name} does not exist, nothing to drop.")
            return
        logger.exception(f"Error dropping table {table_name}.")
        raise
    except Exception:
        logger.exception(f"Error dropping table {table_name}.")
        raise
