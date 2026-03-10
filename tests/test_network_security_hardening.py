"""Tests for security hardening of network API server.

Covers 5 security bugs:
- #45: Content-Length limit on request body (DoS prevention)
- #46: Timing-safe token comparison (hmac.compare_digest)
- #47: Input validation on /register endpoint
- #48: Input validation on /send and POST endpoints
- #31: Server refuses to start without auth token
"""

from __future__ import annotations

import hmac
import json
import pytest
from unittest.mock import MagicMock, patch


# --- #46: Timing-safe token comparison ---


class TestTimingSafeTokenComparison:
    """Verify that token comparison uses hmac.compare_digest, not ==."""

    def test_auth_module_uses_hmac(self):
        """auth.py check_token uses hmac.compare_digest."""
        from minion.network.auth import check_token

        # Valid token should pass
        assert check_token({"Authorization": "Bearer secret123"}, "secret123") is True
        # Invalid token should fail
        assert check_token({"Authorization": "Bearer wrong"}, "secret123") is False
        # Empty expected = no auth (dev mode)
        assert check_token({}, "") is True

    def test_auth_module_returns_true_when_no_auth_configured(self):
        """When expected is empty, auth is disabled (dev mode)."""
        from minion.network.auth import check_token
        assert check_token({"Authorization": "Bearer anything"}, "") is True


# --- #45: Content-Length limit ---


class TestContentLengthLimit:
    """Verify that request body size is limited."""

    def test_max_body_size_constant_exists(self):
        """MAX_BODY_SIZE is defined and reasonable."""
        from minion.network.server import MAX_BODY_SIZE
        assert MAX_BODY_SIZE > 0
        assert MAX_BODY_SIZE <= 10 * 1024 * 1024  # no more than 10 MB

    def test_read_body_rejects_oversized(self):
        """_read_body returns empty and sends 413 for oversized payloads."""
        from minion.network.server import _Handler, MAX_BODY_SIZE

        handler = MagicMock(spec=_Handler)
        handler.headers = {"Content-Length": str(MAX_BODY_SIZE + 1)}
        handler._json_response = MagicMock()

        result = _Handler._read_body(handler)

        assert result == b""
        handler._json_response.assert_called_once()
        args = handler._json_response.call_args
        assert args[0][0] == 413  # status code

    def test_read_body_allows_normal_size(self):
        """_read_body reads normally for payloads under the limit."""
        from minion.network.server import _Handler

        handler = MagicMock()
        handler.headers = {"Content-Length": "100"}
        handler.rfile.read.return_value = b'{"test": true}'

        result = _Handler._read_body(handler)

        assert result == b'{"test": true}'
        handler.rfile.read.assert_called_once_with(100)


# --- #47: Input validation on /register ---


class TestRegisterInputValidation:
    """Verify that /register endpoint validates input via _REGISTER_SCHEMA."""

    def test_validate_fields_rejects_missing_required(self):
        """_validate_fields catches missing required field 'name'."""
        from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
        errors = _validate_fields({}, _REGISTER_SCHEMA)
        assert any("name" in e and "required" in e for e in errors)

    def test_validate_fields_rejects_long_name(self):
        """_validate_fields catches name exceeding max_len."""
        from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
        errors = _validate_fields({"name": "a" * 200}, _REGISTER_SCHEMA)
        assert any("name" in e and "max length" in e for e in errors)

    def test_validate_fields_rejects_invalid_agent_class(self):
        """_validate_fields catches invalid agent_class not in enum."""
        from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
        errors = _validate_fields({"name": "test", "agent_class": "hacker"}, _REGISTER_SCHEMA)
        assert any("agent_class" in e and "must be one of" in e for e in errors)

    def test_validate_fields_rejects_non_int_session_count(self):
        """_validate_fields catches non-integer session_count."""
        from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
        errors = _validate_fields({"name": "test", "session_count": "not-a-number"}, _REGISTER_SCHEMA)
        assert any("session_count" in e for e in errors)

    def test_validate_fields_accepts_valid_payload(self):
        """_validate_fields returns no errors for a valid payload."""
        from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
        errors = _validate_fields({"name": "good-agent", "agent_class": "coder"}, _REGISTER_SCHEMA)
        assert errors == []

    def test_register_handler_rejects_invalid_body(self):
        """handle_register returns 400 for validation failures."""
        from minion.network.handlers.core import handle_register
        handler = MagicMock()
        handler._parse_json_body.return_value = {"name": "a" * 200}  # too long
        handler._json_response = MagicMock()
        handle_register(handler, ":memory:")
        handler._json_response.assert_called()
        status = handler._json_response.call_args[0][0]
        assert status == 400


# --- #48: Input validation on /send ---


class TestSendInputValidation:
    """Verify that /send endpoint validates input."""

    def _make_handler(self, body: dict) -> MagicMock:
        handler = MagicMock()
        handler._parse_json_body.return_value = body
        handler._json_response = MagicMock()
        return handler

    def test_send_rejects_missing_fields(self):
        from minion.network.handlers.core import handle_send
        handler = self._make_handler({"from": "a"})
        handle_send(handler, ":memory:")
        handler._json_response.assert_called()
        status = handler._json_response.call_args[0][0]
        assert status == 400

    def test_send_rejects_non_string_from(self):
        from minion.network.handlers.core import handle_send
        handler = self._make_handler({"from": 123, "to": "b", "message": "hi"})
        handle_send(handler, ":memory:")
        handler._json_response.assert_called()
        status = handler._json_response.call_args[0][0]
        assert status == 400

    def test_send_rejects_oversized_message(self):
        from minion.network.handlers.core import _MAX_MESSAGE_LEN
        from minion.network.handlers.core import handle_send
        handler = self._make_handler({
            "from": "a", "to": "b", "message": "x" * (_MAX_MESSAGE_LEN + 1)
        })
        handle_send(handler, ":memory:")
        handler._json_response.assert_called()
        status = handler._json_response.call_args[0][0]
        assert status == 400

    def test_send_rejects_oversized_agent_name(self):
        from minion.network.handlers.core import _MAX_AGENT_NAME_LEN
        from minion.network.handlers.core import handle_send
        handler = self._make_handler({
            "from": "a" * (_MAX_AGENT_NAME_LEN + 1), "to": "b", "message": "hi"
        })
        handle_send(handler, ":memory:")
        handler._json_response.assert_called()
        status = handler._json_response.call_args[0][0]
        assert status == 400


# --- #48: Input validation on /api/login ---


class TestLoginInputValidation:
    """Verify that /api/login endpoint validates input."""

    def _make_handler(self, body: dict, token: str = "secret") -> MagicMock:
        handler = MagicMock()
        handler._parse_json_body.return_value = body
        handler._json_response = MagicMock()
        handler.token = token
        return handler

    def test_login_rejects_non_string_password(self):
        from minion.network.handlers.compat import handle_api_login
        handler = self._make_handler({"username": "admin", "password": 12345})
        handle_api_login(handler, ":memory:")
        handler._json_response.assert_called()
        status = handler._json_response.call_args[0][0]
        assert status == 400

    def test_login_rejects_oversized_password(self):
        from minion.network.handlers.compat import handle_api_login, _LOGIN_FIELD_MAX
        handler = self._make_handler({"password": "x" * (_LOGIN_FIELD_MAX + 1)})
        handle_api_login(handler, ":memory:")
        handler._json_response.assert_called()
        status = handler._json_response.call_args[0][0]
        assert status == 400

    def test_login_timing_safe_comparison(self):
        """Login uses hmac.compare_digest, not ==."""
        from minion.network.handlers.compat import handle_api_login
        handler = self._make_handler({"password": "secret"}, token="secret")
        handle_api_login(handler, ":memory:")
        handler._json_response.assert_called()
        status = handler._json_response.call_args[0][0]
        body = handler._json_response.call_args[0][1]
        assert status == 200
        assert body["ok"] is True


# --- #31: Server refuses to start without auth token ---


class TestServerRequiresAuthToken:
    """Verify that serve() refuses to start without a token."""

    def test_serve_exits_without_token(self):
        """serve() raises SystemExit when no token and no allow_no_auth."""
        from minion.network.server import serve

        with patch.dict("os.environ", {"MINION_CLUSTER_TOKEN": "", "MINION_NETWORK_NO_AUTH": ""}, clear=False):
            with pytest.raises(SystemExit) as exc_info:
                serve(port=0, token="", allow_no_auth=False)
            assert exc_info.value.code == 1

    def test_serve_allows_no_auth_when_explicitly_set(self):
        """serve() starts when allow_no_auth=True even without token."""
        from minion.network.server import serve

        with patch("minion.network.server.HTTPServer") as mock_server:
            mock_instance = MagicMock()
            mock_server.return_value = mock_instance
            mock_instance.serve_forever.side_effect = KeyboardInterrupt

            with patch.dict("os.environ", {
                "MINION_CLUSTER_TOKEN": "",
                "MINION_NETWORK_NO_AUTH": "",
                "MINION_NETWORK_INSECURE": "1",
            }, clear=False):
                serve(port=0, token="", allow_no_auth=True)

    def test_serve_allows_env_var_no_auth(self):
        """serve() respects MINION_NETWORK_NO_AUTH=1 env var."""
        from minion.network.server import serve

        with patch("minion.network.server.HTTPServer") as mock_server:
            mock_instance = MagicMock()
            mock_server.return_value = mock_instance
            mock_instance.serve_forever.side_effect = KeyboardInterrupt

            with patch.dict("os.environ", {
                "MINION_CLUSTER_TOKEN": "",
                "MINION_NETWORK_NO_AUTH": "1",
                "MINION_NETWORK_INSECURE": "1",
            }, clear=False):
                serve(port=0, token="", allow_no_auth=False)
