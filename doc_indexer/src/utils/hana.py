from hdbcli import dbapi

from utils.logging import get_logger

logger = get_logger(__name__)

_ERR_SQL_INV_TABLE = 259  # HANA error code for invalid/missing table name


def create_hana_connection(url: str, port: int, user: str, password: str) -> dbapi.Connection | None:
    """Create a connection to the Hana Cloud DB."""
    logger.info("Connecting to HANA Cloud", extra={"url": url, "port": port, "user": user})
    try:
        connection = dbapi.connect(
            address=url,
            port=port,
            user=user,
            password=password,
        )
        logger.info("Connected to HANA Cloud", extra={"url": url, "port": port, "user": user})
        return connection
    except dbapi.Error:
        logger.exception("Connection to Hana Cloud failed.", extra={"url": url, "port": port, "user": user})
    except Exception:
        logger.exception(
            "Unknown error while connecting to Hana Cloud.", extra={"url": url, "port": port, "user": user}
        )
    return None


def list_tables(connection: dbapi.Connection, db_user: str) -> list[tuple[str, int, int]]:
    """Return all tables owned by db_user as (name, row_count, size_bytes) tuples."""
    sql = "SELECT TABLE_NAME, RECORD_COUNT, TABLE_SIZE FROM M_TABLES WHERE SCHEMA_NAME = ? ORDER BY TABLE_NAME"
    with connection.cursor() as cursor:
        cursor.execute(sql, (db_user,))
        rows: list[tuple[str, int, int]] = cursor.fetchall()
        return rows


def drop_table(connection: dbapi.Connection, db_user: str, table_name: str) -> None:
    """Drop a table from HANA if it exists. Silently ignores missing tables (error 259)."""
    sql = f'DROP TABLE "{db_user}"."{table_name}"'
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()
        logger.info(f"Dropped table {table_name}.")
    except dbapi.ProgrammingError as e:
        if getattr(e, "errorcode", None) == _ERR_SQL_INV_TABLE:
            logger.warning(f"Table {table_name} does not exist, nothing to drop.")
            return
        logger.exception(f"Error dropping table {table_name}.")
        raise
    except Exception:
        logger.exception(f"Error dropping table {table_name}.")
        raise


def rename_table(
    connection: dbapi.Connection,
    db_user: str,
    old_name: str,
    new_name: str,
    ignore_missing: bool = False,
) -> None:
    """Rename a table in HANA.

    HANA DDL (RENAME TABLE) auto-commits, so no explicit commit is needed.

    Args:
        connection: Active HANA DB connection.
        db_user: Schema / DB user that owns the table.
        old_name: Current table name.
        new_name: Target table name.
        ignore_missing: When True, silently ignore HANA error 259 (table does not exist).
    """
    sql = f'RENAME TABLE "{db_user}"."{old_name}" TO "{db_user}"."{new_name}"'
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        logger.info(f"Renamed table {old_name} to {new_name}.")
    except dbapi.ProgrammingError as e:
        if getattr(e, "errorcode", None) == _ERR_SQL_INV_TABLE and ignore_missing:
            logger.warning(f"Table {old_name} does not exist, nothing to rename.")
            return
        logger.exception(f"Error renaming table {old_name} to {new_name}.")
        raise
    except Exception:
        logger.exception(f"Error renaming table {old_name} to {new_name}.")
        raise
