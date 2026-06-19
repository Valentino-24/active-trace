"""Structured JSON logging configuration.

Replaces the root logger's formatter with a JSON formatter
that emits one line per event with timestamp, level, and message fields.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Each record produces: {"timestamp": "...", "level": "...", "message": "...", ...extras}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        # Include exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include extra fields passed via extra={}
        for key, value in record.__dict__.items():
            if key not in (
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "message",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "taskName",
            ):
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


def setup_logging(*, level: int = logging.INFO) -> None:
    """Configure the root logger with JSON formatting.

    Args:
        level: Logging level (default logging.INFO).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Remove existing handlers and attach the JSON one
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
