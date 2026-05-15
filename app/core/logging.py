"""Logging configuration — call configure_logging() once at each process entrypoint."""

import json
import logging
import os
import time

# Standard LogRecord fields — extras added via extra={} are everything else.
_SKIP_FIELDS = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "msg", "args"}


class _JsonFormatter(logging.Formatter):
    converter = time.gmtime  # always emit UTC timestamps

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        obj: dict[str, object] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }
        for key, value in record.__dict__.items():
            if key not in _SKIP_FIELDS and not key.startswith("_"):
                obj[key] = value
        if record.exc_info:
            obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(obj, default=str)


class _TextFormatter(logging.Formatter):
    _FMT = "%(asctime)s %(levelname)-8s %(name)s  %(message)s"
    _DATE = "%Y-%m-%dT%H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt=self._DATE)


def configure_logging() -> None:
    """Configure root logger. JSON unless LOG_FORMAT=text. Level from LOG_LEVEL (default INFO)."""
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    use_json = os.getenv("LOG_FORMAT", "json").lower() != "text"

    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter() if use_json else _TextFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
