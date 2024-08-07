import os
from logging import Logger, getLogger, StreamHandler, Formatter

level = os.getenv("LOG_LEVEL", "INFO")


def get_logger(name: str) -> Logger:  # noqa: D103
    logger = getLogger(name)
    formatter = Formatter(
        fmt="{asctime} - {levelname} - {name} - {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler = StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.setLevel(level)
    return logger
