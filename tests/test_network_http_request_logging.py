"""Tests for structured JSON HTTP request logging in network server.

Purpose: Verify that _Handler emits structured JSON log lines with the
required fields (ts, level, source, method, path, status_code, duration_ms,
client, message) and that log_message is suppressed (no stderr output).

Rationale: Backlog #43 — server previously suppressed all HTTP logs. Now it
emits structured JSON consistent with daemon runner log format.
"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def _make_handler():
    """Create a minimal _Handler instance for unit testing log methods."""
    from minion.network.server import _Handler

    handler = object.__new__(_Handler)
    # Minimal attrs needed for logging
    handler.client_address = ("127.0.0.1", 54321)
    handler._response_status = 0
    handler._request_start = 0.0
    return handler


class TestLogMessage:
    """log_message should be suppressed — no output."""

    def test_log_message_suppressed(self, capsys):
        """log_message produces no output (logging moved to _log_request)."""
        handler = _make_handler()
        handler.log_message("GET /health 200")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestLogRequest:
    """_log_request emits structured JSON with required fields."""

    def test_emits_valid_json(self, capsys):
        """_log_request prints a single valid JSON line to stdout."""
        handler = _make_handler()
        handler._log_request("GET", "/health", 200, 1.23)
        captured = capsys.readouterr()
        line = captured.out.strip()
        data = json.loads(line)
        assert isinstance(data, dict)

    def test_required_fields_present(self, capsys):
        """All required structured fields are present in the log line."""
        handler = _make_handler()
        handler._log_request("POST", "/api/send", 200, 5.67)
        data = json.loads(capsys.readouterr().out.strip())

        required = {"ts", "level", "source", "method", "path", "status_code",
                     "duration_ms", "client", "message"}
        assert required.issubset(data.keys()), f"Missing: {required - data.keys()}"

    def test_field_values(self, capsys):
        """Field values match what was passed to _log_request."""
        handler = _make_handler()
        handler._log_request("GET", "/api/who", 200, 3.14)
        data = json.loads(capsys.readouterr().out.strip())

        assert data["method"] == "GET"
        assert data["path"] == "/api/who"
        assert data["status_code"] == 200
        assert data["duration_ms"] == 3.14
        assert data["client"] == "127.0.0.1"
        assert data["level"] == "INFO"
        assert data["source"] == "network.http"

    def test_message_field_format(self, capsys):
        """message field contains human-readable summary."""
        handler = _make_handler()
        handler._log_request("POST", "/api/send", 201, 12.5)
        data = json.loads(capsys.readouterr().out.strip())

        assert "POST" in data["message"]
        assert "/api/send" in data["message"]
        assert "201" in data["message"]

    def test_404_logged(self, capsys):
        """404 responses are logged with correct status code."""
        handler = _make_handler()
        handler._log_request("GET", "/nonexistent", 404, 0.5)
        data = json.loads(capsys.readouterr().out.strip())
        assert data["status_code"] == 404

    def test_ts_format(self, capsys):
        """Timestamp follows ISO-like format YYYY-MM-DDTHH:MM:SS."""
        handler = _make_handler()
        handler._log_request("GET", "/health", 200, 1.0)
        data = json.loads(capsys.readouterr().out.strip())
        # Should match pattern like 2026-03-10T19:14:28
        ts = data["ts"]
        assert len(ts) == 19
        assert ts[4] == "-" and ts[7] == "-" and ts[10] == "T"


class TestSendResponseCapture:
    """send_response override captures status code for logging."""

    def test_captures_status_code(self):
        """send_response stores the code in _response_status."""
        from minion.network.server import _Handler

        handler = object.__new__(_Handler)
        handler.client_address = ("127.0.0.1", 54321)
        handler._response_status = 0
        handler._headers_buffer = []
        # Mock wfile to avoid actual I/O
        handler.wfile = BytesIO()
        handler.request_version = "HTTP/1.1"
        handler.requestline = "GET /test HTTP/1.1"

        handler.send_response(201)
        assert handler._response_status == 201
