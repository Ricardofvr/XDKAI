from __future__ import annotations

import logging
from pathlib import Path

from backend.config.schema import LoggingConfig

from .json_formatter import JsonLogFormatter


def configure_structured_logging(config: LoggingConfig) -> logging.Logger:
    """Initializes root app logger with JSON output to file and optional stdout."""

    logger = logging.getLogger("portable_ai_drive")
    logger.handlers.clear()
    logger.setLevel(getattr(logging, config.level, logging.INFO))
    logger.propagate = False

    log_directory = Path(config.directory)
    log_directory.mkdir(parents=True, exist_ok=True)
    log_file_path = log_directory / config.filename

    formatter = JsonLogFormatter()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if config.to_stdout:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.info(
        "logging_initialized",
        extra={
            "event": "startup_step",
            "step": "logging_initialized",
            "log_level": config.level,
            "log_file": str(log_file_path),
        },
    )

    return logger
