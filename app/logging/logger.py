import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

from app.logging.formatters import JSONFormatter


class AppLogger:
    """Wrapper around standard Python logging to enforce structured log payloads."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    @property
    def name(self) -> str:
        return self._logger.name

    def _log(
        self,
        level: int,
        message: str,
        event: Optional[str] = None,
        exc_info: bool = False,
        **extra: Any,
    ) -> None:
        extra_dict = {
            "event": event or "SYSTEM",
            "extra_data": extra if extra else None,
        }
        self._logger.log(level, message, exc_info=exc_info, extra=extra_dict)

    def debug(self, message: str, event: Optional[str] = None, **extra: Any) -> None:
        self._log(logging.DEBUG, message, event=event, **extra)

    def info(self, message: str, event: Optional[str] = None, **extra: Any) -> None:
        self._log(logging.INFO, message, event=event, **extra)

    def warning(self, message: str, event: Optional[str] = None, **extra: Any) -> None:
        self._log(logging.WARNING, message, event=event, **extra)

    def error(self, message: str, event: Optional[str] = None, exc_info: bool = False, **extra: Any) -> None:
        self._log(logging.ERROR, message, event=event, exc_info=exc_info, **extra)

    def critical(self, message: str, event: Optional[str] = None, exc_info: bool = True, **extra: Any) -> None:
        self._log(logging.CRITICAL, message, event=event, exc_info=exc_info, **extra)


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path | str] = None,
    log_filename: str = "terminal.log",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """Initialize system-wide structured logging with rotating file and console handlers."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = JSONFormatter()

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers on multiple setup calls
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Console Handler (stdout/stderr)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler with Rotation (if directory is specified or defaults to logs/)
    if log_dir is not None:
        target_dir = Path(log_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / log_filename

        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> AppLogger:
    """Obtain a structured logger for a specific module."""
    return AppLogger(logging.getLogger(name))

