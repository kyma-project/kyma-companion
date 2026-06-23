import logging
import sys
from logging import Logger as LoggerType
from logging import getLogger

from pythonjsonlogger.json import JsonFormatter

from utils.settings import LOG_LEVEL

_logging_configured = False


def _configure_logging() -> None:
    global _logging_configured  # noqa: PLW0603
    if _logging_configured:
        return
    _logging_configured = True

    formatter = JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    root.handlers.clear()
    root.addHandler(handler)


_configure_logging()


def get_logger(name: str) -> LoggerType:
    """Return a logger that inherits from the root logger configuration."""
    _configure_logging()
    return getLogger(name)
