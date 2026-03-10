"""Behavioral tests for triggers.py — get_triggers, clear_moon_crash.

Purpose: Verify get_triggers returns the codebook, and clear_moon_crash
         enforces lead-class-only restriction and correctly toggles the flag.
"""

from __future__ import annotations

import pytest

from minion.db import init_db, reset_db_path

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# DB isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    reset_db_path()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_agent(name: str, cls: str) -> None:
    import sqlite3, os
    db_path = os.environ["MINION_DB_PATH"]
    now = "2026-03-09T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, ?, ?, ?)",
        (name, cls, now, now),
    )
    conn.commit()
    conn.close()


def _set_moon_crash(value: str = "1") -> None:
    import sqlite3, os
    db_path = os.environ["MINION_DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO flags (key, value, set_by, set_at) VALUES ('moon_crash', ?, 'sys', '2026-03-09T00:00:00')",
        (value,),
    )
    conn.commit()
    conn.close()


def _get_moon_crash() -> str | None:
    import sqlite3, os
    db_path = os.environ["MINION_DB_PATH"]
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT value FROM flags WHERE key = 'moon_crash'").fetchone()
    conn.close()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# get_triggers — codebook structure
# ---------------------------------------------------------------------------


def test_get_triggers_returns_dict():
    """get_triggers returns a dict with 'triggers' key."""
    from minion.triggers import get_triggers
    result = get_triggers()
    assert isinstance(result, dict)
    assert "triggers" in result


def test_get_triggers_has_known_codes():
    """get_triggers includes standard brevity codes."""
    from minion.triggers import get_triggers
    result = get_triggers()
    triggers = result["triggers"]
    for code in ("fenix_down", "moon_crash", "halt", "sitrep", "stand_down"):
        assert code in triggers, f"Missing trigger code: {code}"


def test_get_triggers_values_are_strings():
    """All trigger descriptions are non-empty strings."""
    from minion.triggers import get_triggers
    for code, desc in get_triggers()["triggers"].items():
        assert isinstance(desc, str) and len(desc) > 0, f"{code}: empty description"


def test_get_triggers_notes_is_list():
    """get_triggers includes 'notes' as a list."""
    from minion.triggers import get_triggers
    result = get_triggers()
    assert "notes" in result
    assert isinstance(result["notes"], list)


# ---------------------------------------------------------------------------
# clear_moon_crash — unregistered agent
# ---------------------------------------------------------------------------


def test_clear_moon_crash_unregistered_agent_returns_error():
    """clear_moon_crash returns error when agent is not registered."""
    from minion.triggers import clear_moon_crash
    result = clear_moon_crash("ghost")
    assert "error" in result
    assert "not registered" in result["error"]


# ---------------------------------------------------------------------------
# clear_moon_crash — wrong class
# ---------------------------------------------------------------------------


def test_clear_moon_crash_non_lead_is_blocked():
    """clear_moon_crash blocks agents that are not lead class."""
    _register_agent("fighter", "coder")
    from minion.triggers import clear_moon_crash
    result = clear_moon_crash("fighter")
    assert "error" in result
    assert "Only lead" in result["error"]


# ---------------------------------------------------------------------------
# clear_moon_crash — noop when not active
# ---------------------------------------------------------------------------


def test_clear_moon_crash_noop_when_not_active():
    """clear_moon_crash returns noop status when moon_crash is not set."""
    _register_agent("atlas", "lead")
    from minion.triggers import clear_moon_crash
    result = clear_moon_crash("atlas")
    assert result["status"] == "noop"


# ---------------------------------------------------------------------------
# clear_moon_crash — clears active flag
# ---------------------------------------------------------------------------


def test_clear_moon_crash_clears_active_flag():
    """clear_moon_crash sets moon_crash flag to '0' when it was active."""
    _register_agent("atlas", "lead")
    _set_moon_crash("1")
    from minion.triggers import clear_moon_crash
    result = clear_moon_crash("atlas")
    assert result["status"] == "cleared"
    assert _get_moon_crash() == "0"
