import logging.config
from logging import Logger, getLogger
from pathlib import Path

import yaml

from utils.settings import LOG_LEVEL

config_path = Path(__file__).parent.parent.parent / "config" / "logging.yml"

with open(config_path) as f:
    config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)


def get_logger(name: str) -> Logger:
    """Returns a preconfigured logger instance."""
    logger = getLogger(name)
    logger.setLevel(LOG_LEVEL)
    return logger
