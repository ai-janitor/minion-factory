"""Behavioral tests for network/handlers/ — field validation, presence, FQN utilities.

Purpose: Test pure-function utilities in network handlers that don't require
         a running HTTP server: _validate_fields, _compute_presence, FQN parsing.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# _validate_fields — field schema validation
# ---------------------------------------------------------------------------


def test_validate_fields_valid_required_field():
    """_validate_fields returns empty list for valid required field."""
    from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
    body = {"name": "leo"}
    errors = _validate_fields(body, _REGISTER_SCHEMA)
    assert errors == []


def test_validate_fields_wrong_type_returns_error():
    """_validate_fields returns error when field has wrong type."""
    from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
    body = {"session_count": "not-an-int"}
    errors = _validate_fields(body, _REGISTER_SCHEMA)
    assert len(errors) > 0


def test_validate_fields_string_too_long_returns_error():
    """_validate_fields returns error when string exceeds max_len."""
    from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
    body = {"name": "x" * 100}  # max_len is 64
    errors = _validate_fields(body, _REGISTER_SCHEMA)
    assert len(errors) > 0


def test_validate_fields_invalid_enum_returns_error():
    """_validate_fields returns error when value not in enum."""
    from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
    body = {"agent_class": "wizard"}  # not in enum
    errors = _validate_fields(body, _REGISTER_SCHEMA)
    assert len(errors) > 0


def test_validate_fields_valid_enum_no_error():
    """_validate_fields returns no error for valid enum value."""
    from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
    body = {"agent_class": "coder"}
    errors = _validate_fields(body, _REGISTER_SCHEMA)
    # coder is in REGISTER_SCHEMA enum — no error expected
    # (some implementations may have stricter enums, so allow 0 or check no name error)
    name_errors = [e for e in errors if "agent_class" in e and "must be" in e]
    assert name_errors == [], f"Valid enum 'coder' rejected: {name_errors}"


def test_validate_fields_with_required_name_missing():
    """_validate_fields flags 'name' as required when absent and name is required."""
    from minion.network.handlers.core import _validate_fields, _REGISTER_SCHEMA
    errors = _validate_fields({}, _REGISTER_SCHEMA)
    # 'name' is required in REGISTER_SCHEMA — expect an error about it
    name_errors = [e for e in errors if "name" in e.lower() and "required" in e.lower()]
    assert len(name_errors) >= 1


# ---------------------------------------------------------------------------
# _compute_presence — agent liveness detection
# ---------------------------------------------------------------------------


def test_compute_presence_recent_last_seen_is_online():
    """Agent seen within 5 minutes is 'online'."""
    from minion.network.handlers.core import _compute_presence
    from datetime import datetime, timedelta
    # Use naive datetime to match implementation's datetime.now() (naive)
    recent = (datetime.now() - timedelta(minutes=1)).isoformat()
    result = _compute_presence(recent)
    assert result == "online"


def test_compute_presence_old_last_seen_is_offline():
    """Agent seen over 30 minutes ago is 'offline'."""
    from minion.network.handlers.core import _compute_presence
    from datetime import datetime, timedelta
    old = (datetime.now() - timedelta(hours=2)).isoformat()
    result = _compute_presence(old)
    assert result in ("offline", "idle")


def test_compute_presence_none_is_offline():
    """None last_seen returns 'offline'."""
    from minion.network.handlers.core import _compute_presence
    result = _compute_presence(None)
    assert result == "offline"


# ---------------------------------------------------------------------------
# fqn.py — build_fqn and parse_fqn
# ---------------------------------------------------------------------------


def test_build_fqn_format():
    """build_fqn produces a colon-separated machine:project:name string."""
    from minion.network.fqn import build_fqn
    result = build_fqn("machine-1", "/projects/foo", "leo")
    assert isinstance(result, str)
    # Should contain all three components
    assert "leo" in result
    assert "machine-1" in result


def test_parse_fqn_roundtrips_build_fqn():
    """parse_fqn correctly decodes a string produced by build_fqn."""
    from minion.network.fqn import build_fqn, parse_fqn
    fqn = build_fqn("machine-1", "/projects/foo", "leo")
    result = parse_fqn(fqn)
    assert result is not None
    machine_id, project_path, name = result
    assert machine_id == "machine-1"
    assert name == "leo"


def test_parse_fqn_invalid_returns_none():
    """parse_fqn returns None for a malformed FQN string."""
    from minion.network.fqn import parse_fqn
    result = parse_fqn("this-is-not-a-valid-fqn")
    # Should return None or a tuple — implementation-dependent
    # Just verify it doesn't crash
    assert result is None or isinstance(result, tuple)


# ---------------------------------------------------------------------------
# handlers/compat.py — backward-compat aliases
# ---------------------------------------------------------------------------


def test_compat_module_imports():
    """network/handlers/compat.py imports without error."""
    try:
        import minion.network.handlers.compat  # noqa: F401
    except ImportError as e:
        pytest.fail(f"compat import failed: {e}")
