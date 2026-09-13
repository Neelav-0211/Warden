import logging
import os
import sys
from typing import Any, cast

import structlog
from structlog.contextvars import bind_contextvars, merge_contextvars


def _configure_logging() -> None:
    environment = os.getenv("ENVIRONMENT", "local")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    renderer: structlog.types.Processor
    if environment == "local":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    logging.basicConfig(stream=sys.stdout, level=log_level, force=True)
    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a configured structured logger with the given name."""

    _configure_logging()
    return cast(
        structlog.stdlib.BoundLogger,
        structlog.get_logger().bind(logger=name),
    )


def bind_context(**kwargs: Any) -> None:
    """Bind values to log records in the current execution context."""

    bind_contextvars(**kwargs)
