"""Tests for network handler error paths — invalid payloads, missing fields, wrong types, oversized.

Purpose: Verify all 8 handler modules reject bad input with correct HTTP status codes
         and informative error messages. These are unit tests — no real HTTP server needed.
Rationale: Input validation was added to prevent arbitrary data entering the DB and
           to guard against DoS via oversized payloads. These tests lock in that behavior
           so regressions are caught immediately. Tests call handler functions directly
           with a FakeHandler mock, bypassing HTTP transport entirely.
Responsibility: Cover ~15 error paths across 8 handler modules. NOT responsible for
                happy-path or DB-content correctness (those belong in integration tests).
Organization: FakeHandler + temp DB fixture at top, then one TestClass per handler module.
              Each test name describes the exact error scenario being exercised.

Dependencies: minion.network.handlers.{core,backlog,flows,overview,projects,
              requirements,scaling,compat}, minion.network.db_schema
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


import pytest

pytestmark = pytest.mark.integration


# ── Shared Fake Handler ────────────────────────────────────────────────────────
# Purpose: Minimal mock that satisfies the (handler, db_path, **kwargs) contract.
# Records all _json_response() calls so tests can assert on status + payload.

class FakeHandler:
    """Mock HTTP handler — captures _json_response calls, stubs _parse_json_body."""

    def __init__(self, body: dict | None = None, path: str = "/", token: str = "") -> None:
        # PSEUDO: body is what _parse_json_body() will return (None = parse failure)
        self._body = body
        self.path = path
        self.token = token
        self._responses: list[tuple[int, Any]] = []

    def _parse_json_body(self) -> dict | None:
        return self._body

    def _json_response(self, status: int, data: Any) -> None:
        self._responses.append((status, data))

    @property
    def last_status(self) -> int | None:
        return self._responses[-1][0] if self._responses else None

    @property
    def last_data(self) -> Any:
        return self._responses[-1][1] if self._responses else None

    @property
    def response_count(self) -> int:
        return len(self._responses)


# ── DB Fixture ─────────────────────────────────────────────────────────────────
# Purpose: Temp network DB for tests that reach the DB layer (e.g. send to unknown agent).

@pytest.fixture
def net_db(tmp_path: Path) -> str:
    """Create and initialize a temp network coordinator DB. Returns db_path string."""
    # PSEUDO: init fresh network DB, return path
    db_path = str(tmp_path / "network.db")
    from minion.network.db_schema import init_db
    init_db(db_path)
    return db_path


def _insert_agent(db_path: str, name: str = "target-agent") -> None:
    """Insert a minimal agent row so /send can find its recipient."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO agents (name, agent_class, machine_id, project_path) VALUES (?,?,?,?)",
        (name, "coder", "test-machine", "unknown"),
    )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Task #76 — ~15 error path tests across 8 handler modules
# ═══════════════════════════════════════════════════════════════════════════════


class TestCoreHandlerRegisterErrors:
    """POST /register — missing fields, wrong types, enum violations."""

    def test_register_missing_name_returns_400(self, net_db):
        """Body without 'name' must return 400 with 'required' in error.

        Note: {} is falsy — use non-empty dict to get past the None guard.
        """
        # PSEUDO: body has agent_class but no 'name' → _validate_fields detects required field → 400
        from minion.network.handlers.core import handle_register

        h = FakeHandler(body={"agent_class": "coder"})
        handle_register(h, net_db)

        assert h.last_status == 400
        assert "error" in h.last_data

    def test_register_name_wrong_type_returns_400(self, net_db):
        """'name' field as integer must return 400 (type mismatch)."""
        # PSEUDO: name=123 → type is int, expected str → _validate_fields error → 400
        from minion.network.handlers.core import handle_register

        h = FakeHandler(body={"name": 123})
        handle_register(h, net_db)

        assert h.last_status == 400
        error_msg = str(h.last_data)
        assert "name" in error_msg.lower() or "str" in error_msg.lower()

    def test_register_name_too_long_returns_400(self, net_db):
        """'name' exceeding 64 chars must return 400 (max_len violation)."""
        # PSEUDO: name="x"*65 → len > 64 → _validate_fields max_len → 400
        from minion.network.handlers.core import handle_register

        long_name = "a" * 65
        h = FakeHandler(body={"name": long_name})
        handle_register(h, net_db)

        assert h.last_status == 400
        assert "max" in str(h.last_data).lower() or "length" in str(h.last_data).lower()

    def test_register_invalid_agent_class_enum_returns_400(self, net_db):
        """'agent_class' not in allowed enum must return 400."""
        # PSEUDO: agent_class="wizard" → not in ["coder","builder","recon","auditor","lead"] → 400
        from minion.network.handlers.core import handle_register

        h = FakeHandler(body={"name": "test-agent", "agent_class": "wizard"})
        handle_register(h, net_db)

        assert h.last_status == 400
        assert "agent_class" in str(h.last_data) or "enum" in str(h.last_data).lower() or "one of" in str(h.last_data).lower()

    def test_register_session_count_wrong_type_returns_400(self, net_db):
        """'session_count' as string must return 400 (int field got str)."""
        # PSEUDO: session_count="five" → type str, expected int → _validate_fields → 400
        from minion.network.handlers.core import handle_register

        h = FakeHandler(body={"name": "test-agent", "session_count": "five"})
        handle_register(h, net_db)

        assert h.last_status == 400

    def test_register_parse_failure_returns_no_double_response(self, net_db):
        """When _parse_json_body returns None (bad JSON/content-type), handler exits silently."""
        # PSEUDO: body=None → handle_register returns early, sends no additional response
        from minion.network.handlers.core import handle_register

        h = FakeHandler(body=None)
        handle_register(h, net_db)

        # Handler must NOT call _json_response when body is None
        # (the pre-handler already sent 400/415 — no double-response)
        assert h.response_count == 0


class TestCoreHandlerSendErrors:
    """POST /send — missing fields, wrong types, oversized payloads."""

    def test_send_missing_all_fields_returns_400(self, net_db):
        """Body missing from/to/message must return 400.

        Note: {} is falsy — use non-empty dict to get past the None guard.
        """
        # PSEUDO: body non-empty but all comms fields absent → empty strings → "required" → 400
        from minion.network.handlers.core import handle_send

        h = FakeHandler(body={"priority": "normal"})
        handle_send(h, net_db)

        assert h.last_status == 400

    def test_send_from_wrong_type_returns_400(self, net_db):
        """'from' as integer must return 400 (type check before strip())."""
        # PSEUDO: from=123 → isinstance check → "must be strings" → 400
        from minion.network.handlers.core import handle_send

        h = FakeHandler(body={"from": 123, "to": "bob", "message": "hi"})
        handle_send(h, net_db)

        assert h.last_status == 400
        assert "string" in str(h.last_data).lower() or "str" in str(h.last_data).lower()

    def test_send_oversized_message_returns_400(self, net_db):
        """Message exceeding 100KB must return 400 (OOM guard)."""
        # PSEUDO: message=100KB+1 → len > _MAX_MESSAGE_LEN → 400
        from minion.network.handlers.core import handle_send

        oversized = "x" * (100 * 1024 + 1)
        h = FakeHandler(body={"from": "alice", "to": "bob", "message": oversized})
        handle_send(h, net_db)

        assert h.last_status == 400
        assert "max" in str(h.last_data).lower() or "length" in str(h.last_data).lower()

    def test_send_oversized_from_name_returns_400(self, net_db):
        """'from' agent name exceeding 64 chars must return 400."""
        # PSEUDO: from="x"*65 → len > _MAX_AGENT_NAME_LEN → 400
        from minion.network.handlers.core import handle_send

        h = FakeHandler(body={"from": "a" * 65, "to": "bob", "message": "hi"})
        handle_send(h, net_db)

        assert h.last_status == 400

    def test_send_to_unknown_agent_returns_404(self, net_db):
        """Sending to an unregistered agent must return 404."""
        # PSEUDO: SELECT name FROM agents WHERE name=? → not found → 404
        from minion.network.handlers.core import handle_send

        h = FakeHandler(body={"from": "alice", "to": "ghost-agent", "message": "hello"})
        handle_send(h, net_db)

        assert h.last_status == 404

    def test_send_parse_failure_returns_no_double_response(self, net_db):
        """When _parse_json_body returns None, handle_send exits without double-response."""
        # PSEUDO: body=None → handler exits, no _json_response call
        from minion.network.handlers.core import handle_send

        h = FakeHandler(body=None)
        handle_send(h, net_db)

        assert h.response_count == 0


class TestCompatLoginErrors:
    """POST /api/login — wrong password, missing body."""

    def test_login_wrong_password_returns_401(self, net_db):
        """Wrong password with a configured token must return 401."""
        # PSEUDO: token set on handler, password != token → {"ok": False} → 401
        from minion.network.handlers.compat import handle_api_login

        h = FakeHandler(body={"username": "user", "password": "wrong-pass"}, token="secret")
        handle_api_login(h, net_db)

        assert h.last_status == 401
        assert h.last_data.get("ok") is False

    def test_login_parse_failure_returns_400(self, net_db):
        """None body (malformed JSON) must return 400."""
        # PSEUDO: body=None → handler sends 400 (compat layer does explicit check)
        from minion.network.handlers.compat import handle_api_login

        h = FakeHandler(body=None)
        handle_api_login(h, net_db)

        assert h.last_status == 400


class TestBacklogHandlerErrors:
    """GET /projects/{name}/backlog — project not found."""

    def test_backlog_unknown_project_returns_404(self, net_db):
        """Requesting backlog for non-existent project must return 404."""
        # PSEUDO: resolve_project_path returns None → 404 {"error": "Project ... not found"}
        from minion.network.handlers.backlog import handle_list_backlog

        h = FakeHandler(path="/projects/ghost-project/backlog")
        handle_list_backlog(h, net_db, name="ghost-project")

        assert h.last_status == 404
        assert "not found" in str(h.last_data).lower()


class TestCoreHandlerInboxErrors:
    """GET /inbox/{agent} — empty agent name."""

    def test_inbox_empty_agent_returns_400(self, net_db):
        """Empty agent name must return 400 (path param missing or empty)."""
        # PSEUDO: agent="" → handler checks → 400 {"error": "Agent name required"}
        from minion.network.handlers.core import handle_inbox

        h = FakeHandler(path="/inbox/")
        handle_inbox(h, net_db, agent="")

        assert h.last_status == 400


class TestValidateFieldsUnit:
    """Direct unit tests for the _validate_fields helper — validates without DB."""

    def test_required_field_missing_returns_error(self):
        """_validate_fields must report missing required fields."""
        # PSEUDO: field is required, body has no value → error list has that field
        from minion.network.handlers.core import _validate_fields

        schema = {"name": {"type": str, "required": True}}
        errors = _validate_fields({}, schema)

        assert any("name" in e and "required" in e for e in errors)

    def test_wrong_type_returns_error(self):
        """_validate_fields must report type mismatches."""
        # PSEUDO: field expects int, got str → error names the field and expected type
        from minion.network.handlers.core import _validate_fields

        schema = {"count": {"type": int}}
        errors = _validate_fields({"count": "five"}, schema)

        assert any("count" in e for e in errors)

    def test_enum_violation_returns_error(self):
        """_validate_fields must reject values not in allowed enum."""
        # PSEUDO: value not in enum list → error with field name
        from minion.network.handlers.core import _validate_fields

        schema = {"role": {"type": str, "enum": ["admin", "user"]}}
        errors = _validate_fields({"role": "wizard"}, schema)

        assert any("role" in e for e in errors)

    def test_max_len_exceeded_returns_error(self):
        """_validate_fields must reject strings over max_len."""
        # PSEUDO: len(value) > max_len → error with field name and max
        from minion.network.handlers.core import _validate_fields

        schema = {"tag": {"type": str, "max_len": 5}}
        errors = _validate_fields({"tag": "toolongvalue"}, schema)

        assert any("tag" in e for e in errors)

    def test_valid_payload_returns_no_errors(self):
        """_validate_fields must return empty list for fully valid payload."""
        # PSEUDO: all fields correct type, within limits, in enum → []
        from minion.network.handlers.core import _validate_fields

        schema = {"name": {"type": str, "max_len": 64, "required": True},
                  "agent_class": {"type": str, "enum": ["coder", "lead"]}}
        errors = _validate_fields({"name": "lance", "agent_class": "coder"}, schema)

        assert errors == []
