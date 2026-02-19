import json
import logging
import logging.config
import sys
from logging import Formatter, Logger, LogRecord, getLogger

from tenacity import RetryCallState

from utils.settings import LOG_FORMAT, LOG_LEVEL


class PrettyJSONFormatter(Formatter):
    """Custom formatter that outputs pretty-printed JSON for development."""

    def format(self, record: LogRecord) -> str:
        """Format log record as pretty-printed JSON."""
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "client"):
            log_data["client"] = record.client

        # Pretty print with indentation and colors for readability
        return json.dumps(log_data, indent=2, sort_keys=False)


# Flag to track if logging has been configured
_logging_configured = False


# Configure logging programmatically
def _configure_logging() -> None:
    """Configure logging based on LOG_LEVEL and LOG_FORMAT settings.

    Can be called multiple times safely - only configures once unless force=True.
    """
    global _logging_configured  # noqa: PLW0603

    # Prevent duplicate configuration
    if _logging_configured:
        return

    _logging_configured = True

    # Determine formatter based on LOG_FORMAT
    format_type = LOG_FORMAT.lower()

    formatter: Formatter
    if format_type == "json":
        try:
            from pythonjsonlogger.json import JsonFormatter

            formatter = JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        except ImportError:
            # Use sys.stderr since logging isn't configured yet
            sys.stderr.write(
                "WARNING: LOG_FORMAT=json specified but python-json-logger not installed. "
                "Run 'poetry install' to enable JSON logging. Using standard format.\n"
            )
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    elif format_type == "pretty":
        # Pretty-printed JSON for development (no external deps needed)
        formatter = PrettyJSONFormatter()
    else:
        # Standard human-readable format
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    root_logger.addHandler(console_handler)

    # Disable uvicorn.access logger (handled by middleware)
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers.clear()  # Clear handlers properly
    uvicorn_access.setLevel(logging.CRITICAL)
    uvicorn_access.propagate = False

    # Configure other uvicorn loggers to use our handler
    for logger_name in ["uvicorn", "uvicorn.error"]:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = [console_handler]
        uvicorn_logger.propagate = False


# Initialize logging when module is imported
_configure_logging()


def get_logger(name: str) -> Logger:
    """Returns a logger instance that inherits from root logger configuration."""
    # Ensure logging is configured (lazy initialization)
    _configure_logging()
    return getLogger(name)


def reconfigure_logging() -> None:
    """Force reconfiguration of logging (useful for testing or hot reload)."""
    global _logging_configured  # noqa: PLW0603
    _logging_configured = False
    _configure_logging()


def after_log(retry_state: RetryCallState) -> None:
    """Log retry attempts with appropriate log levels for tenacity retry.

    Args:
        retry_state (RetryCallState): Current state of the retry operation
    """
    module_name = retry_state.fn.__module__ if retry_state.fn and retry_state.fn.__module__ else "tenancy.retry"
    func_name = retry_state.fn.__name__ if retry_state.fn and retry_state.fn.__name__ else "None"
    logger = get_logger(f"{module_name}.{func_name}")
    # Log at INFO level for the first attempt, and WARNING for subsequent attempts
    if retry_state.attempt_number < 1:
        logger.info(f"Attempt {retry_state.attempt_number}")
    else:
        logger.warning(f"Attempt {retry_state.attempt_number}")
