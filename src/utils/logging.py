import logging.config
import os
from logging import Logger
from pathlib import Path

import yaml

level = os.getenv("LOG_LEVEL", "INFO")

config_path = Path(__file__).parent.parent.parent / 'config' / 'logging.yaml'

with open(config_path) as f:
    config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)


def get_logger(name: str) -> Logger:  # noqa: D103
    logger = logging.getLogger(name)
    # dummy change
    logger.setLevel(level)
    return logger
