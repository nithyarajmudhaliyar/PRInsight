"""
Logging configuration for PRInsight.

MVP approach: standard Python logging with a clean, human-readable console
format. All application modules use logging.getLogger(__name__) to
automatically create child loggers under the 'app' namespace.

Future migration path:
    - Swap StreamHandler for a JSONFormatter for structured logging.
    - Add a custom Filter that reads request_id from a contextvars.ContextVar.
    - Swap for OpenTelemetry SDK exporter.
    Application code (logger.info(...) calls) never changes.
"""

import logging
import sys


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure the root 'app' logger and its descendants.

    Args:
        log_level: The minimum log level. Accepts standard level names
                   (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure the root 'app' logger so every module under app/
    # that uses logging.getLogger(__name__) inherits this configuration.
    logger = logging.getLogger("app")
    logger.setLevel(level)

    # Avoid duplicate handlers if setup_logging is called more than once
    # (e.g., during testing).
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        logger.addHandler(handler)

    # Prevent log messages from propagating to the root logger, which
    # would cause duplicate output with Uvicorn's default logging.
    logger.propagate = False
