import logging

from utils.settings import LOG_LEVEL


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: The name of the logger, typically __name__ from the calling module

    Returns:
        A configured logger instance
    """
    logging.basicConfig(
        level=LOG_LEVEL.upper(),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    return logging.getLogger(name)
