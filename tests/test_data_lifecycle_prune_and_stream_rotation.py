"""Tests for data lifecycle: DB prune and stream.jsonl rotation.

Purpose: Verify backlog #61 (unbounded DB growth) and #73 (stream.jsonl rotation).
Responsibility: Test prune_old_records() deletes old rows, and _rotate_stream_log() rotates.
"""

from __future__ import annotations

import datetime
import os
import tempfile

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.db]


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Set up a fresh minion DB in a temp directory."""
    db_path = str(tmp_path / ".work" / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)

    from minion.db.connection import reset_db_path, init_db
    reset_db_path()
    init_db()
    return db_path


# ── DB Prune ──────────────────────────────────────────────────────────


def test_prune_deletes_old_messages(fresh_db):
    """Prune removes messages older than max_age_days."""
    from minion.db.connection import get_db
    from minion.db.prune import prune_old_records

    conn = get_db()
    old_ts = (datetime.datetime.now() - datetime.timedelta(days=60)).isoformat()
    new_ts = datetime.datetime.now().isoformat()
    conn.execute(
        "INSERT INTO messages (from_agent, to_agent, timestamp) VALUES (?, ?, ?)",
        ("a", "b", old_ts),
    )
    conn.execute(
        "INSERT INTO messages (from_agent, to_agent, timestamp) VALUES (?, ?, ?)",
        ("a", "b", new_ts),
    )
    conn.commit()
    conn.close()

    result = prune_old_records(max_age_days=30)
    assert result["deleted"]["messages"] == 1
    assert result["total_deleted"] >= 1

    # Verify only the recent message remains
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    conn.close()
    assert count == 1


def test_prune_deletes_old_transition_log(fresh_db):
    """Prune removes old transition_log entries."""
    from minion.db.connection import get_db
    from minion.db.prune import prune_old_records

    conn = get_db()
    old_ts = (datetime.datetime.now() - datetime.timedelta(days=60)).isoformat()
    conn.execute(
        "INSERT INTO transition_log (entity_id, entity_type, to_status, created_at) VALUES (?, ?, ?, ?)",
        (1, "task", "closed", old_ts),
    )
    conn.commit()
    conn.close()

    result = prune_old_records(max_age_days=30)
    assert result["deleted"]["transition_log"] == 1


def test_prune_deletes_old_invocation_log(fresh_db):
    """Prune removes old invocation_log entries."""
    from minion.db.connection import get_db
    from minion.db.prune import prune_old_records

    conn = get_db()
    old_ts = (datetime.datetime.now() - datetime.timedelta(days=60)).isoformat()
    conn.execute(
        "INSERT INTO invocation_log (agent_name, pid, started_at) VALUES (?, ?, ?)",
        ("test-agent", 12345, old_ts),
    )
    conn.commit()
    conn.close()

    result = prune_old_records(max_age_days=30)
    assert result["deleted"]["invocation_log"] == 1


def test_prune_keeps_recent_records(fresh_db):
    """Prune does not delete records newer than max_age_days."""
    from minion.db.connection import get_db
    from minion.db.prune import prune_old_records

    conn = get_db()
    recent_ts = datetime.datetime.now().isoformat()
    conn.execute(
        "INSERT INTO messages (from_agent, to_agent, timestamp) VALUES (?, ?, ?)",
        ("a", "b", recent_ts),
    )
    conn.commit()
    conn.close()

    result = prune_old_records(max_age_days=30)
    assert result["deleted"]["messages"] == 0
    assert result["total_deleted"] == 0


def test_prune_rejects_invalid_days():
    """Prune raises AssertionError for non-positive max_age_days."""
    from minion.db.prune import prune_old_records
    with pytest.raises(AssertionError):
        prune_old_records(max_age_days=0)
    with pytest.raises(AssertionError):
        prune_old_records(max_age_days=-1)


# ── Stream.jsonl Rotation ─────────────────────────────────────────────


def test_rotate_stream_log_rotates_large_file(tmp_path):
    """Stream log is rotated when it exceeds max_bytes."""
    from minion.daemon.runner._execution import _rotate_stream_log

    stream_log = tmp_path / "test.stream.jsonl"
    stream_log.write_text("x" * 1000)

    rotated = _rotate_stream_log(stream_log, max_bytes=500)
    assert rotated is True
    assert not stream_log.exists()
    assert (tmp_path / "test.stream.jsonl.1").exists()


def test_rotate_stream_log_skips_small_file(tmp_path):
    """Stream log is NOT rotated when under max_bytes."""
    from minion.daemon.runner._execution import _rotate_stream_log

    stream_log = tmp_path / "test.stream.jsonl"
    stream_log.write_text("x" * 100)

    rotated = _rotate_stream_log(stream_log, max_bytes=500)
    assert rotated is False
    assert stream_log.exists()


def test_rotate_stream_log_handles_missing_file(tmp_path):
    """Stream log rotation handles missing file gracefully."""
    from minion.daemon.runner._execution import _rotate_stream_log

    stream_log = tmp_path / "nonexistent.stream.jsonl"
    rotated = _rotate_stream_log(stream_log, max_bytes=500)
    assert rotated is False


def test_rotate_stream_log_rejects_invalid_max_bytes(tmp_path):
    """Stream log rotation rejects non-positive max_bytes."""
    from minion.daemon.runner._execution import _rotate_stream_log

    stream_log = tmp_path / "test.stream.jsonl"
    with pytest.raises(AssertionError):
        _rotate_stream_log(stream_log, max_bytes=0)
