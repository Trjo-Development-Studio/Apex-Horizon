"""Logging configuration.

Design Bible V15.12 requires detailed internal logs covering errors, warnings,
important simulation events, and debug information, without interrupting
gameplay. Logs are written to a rotating file so a long playthrough cannot fill
the disk, and a brief summary is mirrored to the console for development.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import log_dir

LOG_FILE_NAME = "apex_horizon.log"
# Bound total log usage at roughly 5 MB across the current file plus two backups.
MAX_LOG_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 2

FILE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
CONSOLE_FORMAT = "%(levelname)-8s %(name)s: %(message)s"

_configured = False


def configure_logging(
    *,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    directory: Path | None = None,
) -> Path | None:
    """Set up file and console logging. Returns the log file path, if any.

    Safe to call more than once; subsequent calls are ignored so that importing
    a module never reconfigures logging behind the caller's back. If the log
    directory cannot be created the game continues with console logging only —
    losing logs is never a reason to prevent the player from playing.
    """
    global _configured
    if _configured:
        return None

    root = logging.getLogger()
    root.setLevel(min(console_level, file_level))

    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    root.addHandler(console)

    log_path: Path | None = None
    target_dir = directory or log_dir()
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        log_path = target_dir / LOG_FILE_NAME
        file_handler = RotatingFileHandler(
            log_path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
        root.addHandler(file_handler)
    except OSError:
        log_path = None
        root.warning("Could not open log file in %s; logging to console only.", target_dir)

    _configured = True
    return log_path


def get_logger(name: str) -> logging.Logger:
    """Return the logger for a module, e.g. ``get_logger(__name__)``."""
    return logging.getLogger(name)


def reset_logging_for_tests() -> None:
    """Undo configuration so tests can exercise setup repeatedly."""
    global _configured
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    _configured = False
