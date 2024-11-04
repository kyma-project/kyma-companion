from logging import Formatter, Logger, StreamHandler, getLogger

from utils.settings import LOG_LEVEL


def get_logger(name: str) -> Logger:
    """
    Get a configured logger instance.
    Args:
        name: The name of the logger, typically __name__ from the calling module
    Returns:
        A configured logger instance
    """
    logger = getLogger(name)
    formatter = Formatter(
        fmt="{asctime} - {levelname} - {name} : {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler = StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.setLevel(LOG_LEVEL)
    return logger
