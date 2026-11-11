import logging
from logging.config import dictConfig


def configure_logging(*, debug: bool) -> None:
    """Configure application logging without changing third-party logger handlers."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {"format": "%(asctime)s level=%(levelname)s logger=%(name)s %(message)s"}
            },
            "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default"}},
            "loggers": {
                "app": {
                    "handlers": ["console"],
                    "level": logging.DEBUG if debug else logging.INFO,
                    "propagate": False,
                }
            },
        }
    )
