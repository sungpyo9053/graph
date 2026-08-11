import logging
from typing import cast

import structlog
from structlog.stdlib import BoundLogger

from src.config import settings


def configure_logging() -> None:
    logging.basicConfig(level=settings().log_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


def logger() -> BoundLogger:
    return cast(BoundLogger, structlog.get_logger())
