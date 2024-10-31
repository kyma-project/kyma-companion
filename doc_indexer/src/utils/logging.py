from logging import Formatter, Logger, StreamHandler, getLogger

from utils.settings import LOG_LEVEL


def get_logger(name: str) -> Logger:
    """Returns a preconfigured logger instance."""
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
