import logging
import logging.config
import sys
from typing import Any

import structlog


def configure_logging(debug: bool = False) -> None:
    """
    Configure the application logging pipeline.

    This function wires together Python's standard logging module and
    structlog so that:
    1. All log records, whether from your code or from libraries like
       SQLAlchemy and uvicorn, are processed through the same pipeline.
    2. In development (debug=True), output is colorized and human-readable.
    3. In production (debug=False), output is JSON that log aggregators
       can parse, index, and query.

    Call this function once at application startup in main.py.
    """

    log_level = logging.DEBUG if debug else logging.INFO

    # Configure Python's standard logging to route through structlog.
    # This ensures library logs (SQLAlchemy, uvicorn, httpx) also
    # appear in the structured format.
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
            },
            "console": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.dev.ConsoleRenderer(colors=True),
            },
        },
        "handlers": {
            "default": {
                "level": log_level,
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "console" if debug else "json",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default"],
                "level": log_level,
                "propagate": True,
            },
            # Suppress SQLAlchemy's verbose connection pool logs
            # unless in debug mode
            "sqlalchemy.engine": {
                "handlers": ["default"],
                "level": logging.INFO if debug else logging.WARNING,
                "propagate": False,
            },
            # Suppress uvicorn's default access log because our
            # middleware produces richer request logs
            "uvicorn.access": {
                "handlers": ["default"],
                "level": logging.WARNING,
                "propagate": False,
            },
        },
    })

    # Configure structlog's processing pipeline.
    # Each processor in the chain receives the log event dict and
    # returns a modified version. The final processor converts it
    # to output (JSON string or colored text).
    shared_processors = [
        # Add the log level name (INFO, ERROR, etc.) to every event
        structlog.stdlib.add_log_level,
        # Add ISO-format timestamp to every event
        structlog.processors.TimeStamper(fmt="iso"),
        # Add module and function name to every event
        structlog.stdlib.add_logger_name,
        # Format exceptions as structured data rather than a traceback string
        structlog.processors.format_exc_info,
        # Allow passing extra key=value pairs to log calls
        structlog.contextvars.merge_contextvars,
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger bound to the given name.

    Usage anywhere in the application:
        from app.core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("vehicle_created", vehicle_id=str(vehicle.id), make=vehicle.make)

    The key=value pairs become searchable fields in your log aggregator.
    """
    return structlog.get_logger(name)