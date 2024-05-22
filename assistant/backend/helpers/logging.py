import logging.config
from logging import LogRecord

from contextvars import ContextVar

from asgi_correlation_id import correlation_id


correlation_id_context = ContextVar("correlation_id", default="-")

HANDLER_CLASS = "logging.StreamHandler"


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: LogRecord) -> bool:
        if correlation_id.get() is None:
            record.correlation_id = correlation_id_context.get()
        else:
            record.correlation_id = correlation_id.get() or "-"
        return True


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation_id": {
            "()": "asgi_correlation_id.CorrelationIdFilter",
            "uuid_length": 36,
            "default_value": "-",
        }
    },
    "formatters": {
        "verbose": {
            "format": "[%(correlation_id)s] %(levelname)s: %(pathname)s:%(lineno)d - %(message)s",
            "dateformat": "%Y-%m-%d %H:%M:%S",
        },
        "standard": {
            "format": "[%(correlation_id)s] %(levelname)s: %(message)s",
            "dateformat": "%Y-%m-%d %H:%M:%S",
        },
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "[%(correlation_id)s] %(levelprefix)s: %(message)s",
            "use_colors": "None",
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '[%(correlation_id)s] %(levelprefix)s: %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
    },
    "handlers": {
        "standard": {
            "level": "INFO",
            "formatter": "standard",
            "class": HANDLER_CLASS,
            "stream": "ext://sys.stdout",
        },
        "verbose": {
            "level": "ERROR",
            "formatter": "verbose",
            "class": HANDLER_CLASS,
            "stream": "ext://sys.stderr",
        },
        "default": {
            "formatter": "default",
            "class": HANDLER_CLASS,
            "stream": "ext://sys.stderr",
            "filters": ["correlation_id"],
        },
        "access": {
            "formatter": "access",
            "class": HANDLER_CLASS,
            "stream": "ext://sys.stdout",
            "filters": ["correlation_id"],
        },
    },
    "loggers": {
        "default": {
            "handlers": ["verbose", "standard"],
            "propagate": False,
        },
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO", "handlers": ["default"], "propagate": False},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}


class LogUtil:
    @staticmethod
    def init_logger():
        logging.config.dictConfig(LOGGING_CONFIG)

    @staticmethod
    def get_logger(name: str = None):
        if name is None:
            logger = logging.getLogger("default")
        else:
            logger = logging.getLogger(name)

        logger.addFilter(CorrelationIdFilter())
        return logger