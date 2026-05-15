"""Tests for app/core/logging.py — configure_logging and formatters."""

import io
import json
import logging

import pytest

from app.core.logging import _JsonFormatter, _TextFormatter, configure_logging


@pytest.fixture(autouse=True)
def _reset_root_logger():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.level = original_level


def _format(formatter: logging.Formatter, msg: str, **kwargs) -> str:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in kwargs.items():
        setattr(record, k, v)
    return formatter.format(record)


class TestJsonFormatter:
    def test_standard_fields_present(self):
        out = _format(_JsonFormatter(), "hello")
        parsed = json.loads(out)
        assert set(parsed.keys()) >= {"time", "level", "logger", "message"}
        assert parsed["message"] == "hello"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"

    def test_extra_fields_included(self):
        out = _format(_JsonFormatter(), "count event", count=42)
        parsed = json.loads(out)
        assert parsed["count"] == 42

    def test_exc_info_included(self):
        import sys

        formatter = _JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="failed",
                args=(),
                exc_info=sys.exc_info(),
            )
        out = formatter.format(record)
        parsed = json.loads(out)
        assert "exc_info" in parsed
        assert "ValueError" in parsed["exc_info"]

    def test_output_is_valid_json(self):
        out = _format(_JsonFormatter(), "test message", extra_key="val")
        json.loads(out)  # raises if invalid

    def test_non_serialisable_extra_does_not_raise(self):
        out = _format(_JsonFormatter(), "test", obj=object())
        parsed = json.loads(out)  # must remain valid JSON
        assert "obj" in parsed  # value should be str(obj), not absent


class TestTextFormatter:
    def test_output_contains_message(self):
        out = _format(_TextFormatter(), "world")
        assert "world" in out

    def test_output_is_not_json(self):
        out = _format(_TextFormatter(), "world")
        with pytest.raises((json.JSONDecodeError, ValueError)):
            json.loads(out)


class TestConfigureLogging:
    def test_default_log_level_is_info(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_log_level_from_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        configure_logging()
        assert logging.getLogger().level == logging.WARNING

    def test_default_uses_json_formatter(self, monkeypatch):
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, _JsonFormatter)

    def test_text_format_via_env(self, monkeypatch):
        monkeypatch.setenv("LOG_FORMAT", "text")
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, _TextFormatter)

    def test_json_output_end_to_end(self, monkeypatch):
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        buf = io.StringIO()
        configure_logging()
        root = logging.getLogger()
        root.handlers[0].stream = buf
        logging.getLogger("e2e").info("ping", extra={"x": 1})
        parsed = json.loads(buf.getvalue())
        assert parsed["message"] == "ping"
        assert parsed["x"] == 1

    def test_invalid_log_level_falls_back_to_info(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "NONSENSE")
        configure_logging()  # must not raise
        assert logging.getLogger().level == logging.INFO
