"""Shared dashboard logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from routes.config import REPO_DIR

_LOGGER_NAME = "dashboard"
_LOG_FILE = REPO_DIR / "logs" / "dashboard.log"
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3
_CONFIGURED = False


def _configure_logging() -> None:
    """Initialize the shared dashboard logger once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    dashboard_logger = logging.getLogger(_LOGGER_NAME)
    dashboard_logger.setLevel(logging.DEBUG)

    if not any(isinstance(handler, RotatingFileHandler) for handler in dashboard_logger.handlers):
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(_LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        dashboard_logger.addHandler(handler)

    dashboard_logger.propagate = False
    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a configured dashboard logger."""
    _configure_logging()
    if not name or name == _LOGGER_NAME:
        return logging.getLogger(_LOGGER_NAME)
    if name.startswith(f"{_LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")
