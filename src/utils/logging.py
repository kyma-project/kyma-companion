import logging.config
from logging import Logger, getLogger
from pathlib import Path

import yaml
from tenacity import RetryCallState

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
