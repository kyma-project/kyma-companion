import os
import yaml
from pathlib import Path
import logging.config

level = os.getenv("LOG_LEVEL", "INFO")

config_path = Path(__file__).parent.parent.parent / 'config' / 'logging.yaml'

with open(config_path, "r") as f:
    config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)


def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger
