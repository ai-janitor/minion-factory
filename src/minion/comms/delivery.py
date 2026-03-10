"""Cross-repo message delivery — write message file + DB INSERT to remote project.
Looks up target agent in the coordinator DB, writes message content to the
target project's inbox directory, and inserts metadata into the target's local DB.

Purpose: Cross-repo message delivery — write message file + DB INSERT to remote project.
Rationale: Extracted into own module for single-responsibility agent communication.
Responsibility: Cross-repo message delivery — write message file + DB INSERT to remote project. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import datetime
import logging
import os
import sqlite3

from minion.db import connect, get_coordinator_db
from minion.fs import atomic_write_file

log = logging.getLogger(__name__)


def route_cross_repo(
    to_agent: str, from_agent: str, message: str, now: str
) -> dict[str, object] | None:
    """Deliver message to a remote project's local DB via coordinator lookup.

    Returns a result dict if cross-repo delivery succeeded, None if agent not found globally.
    """
    # Precondition assertions — backlog #63
    assert to_agent, "to_agent must not be empty"
    assert from_agent, "from_agent must not be empty"
    assert message, "message must not be empty"
    assert now, "timestamp must not be empty"

    try:
        coord = get_coordinator_db()
        try:
            row = coord.execute(
                "SELECT project_path FROM agents WHERE name = ?", (to_agent,)
            ).fetchone()
        finally:
            coord.close()
    except Exception:
        return None

    if not row:
        return None

    project_path = row["project_path"]
    if not project_path:
        return None  # agent exists globally but has no project binding
    remote_db_path = os.path.join(project_path, ".work", "minion.db")
    if not os.path.exists(remote_db_path):
        return None

    # Write message content to target project's inbox
    remote_inbox = os.path.join(project_path, ".work", "inbox", to_agent)
    os.makedirs(remote_inbox, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    fname = f"{ts}-{from_agent[:20]}-msg.md"
    content_file = os.path.join(remote_inbox, fname)
    atomic_write_file(content_file, message)

    # Insert message metadata into target project's DB
    db_indexed = False
    try:
        remote_conn = connect(remote_db_path)
        # Ensure messages table exists (target may not have run full init)
        remote_conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                from_agent   TEXT NOT NULL,
                to_agent     TEXT NOT NULL,
                content_file TEXT,
                timestamp    TEXT,
                read_flag    INTEGER DEFAULT 0,
                is_cc        INTEGER DEFAULT 0,
                cc_original_to TEXT
            )
        """)
        remote_conn.execute(
            "INSERT INTO messages (from_agent, to_agent, content_file, timestamp, read_flag, is_cc) VALUES (?, ?, ?, ?, 0, 0)",
            (from_agent, to_agent, content_file, now),
        )
        remote_conn.commit()
        remote_conn.close()
        db_indexed = True
    except Exception as exc:
        log.warning("cross-repo DB insert failed: %s: %s", type(exc).__name__, exc)
        # File delivered even if DB insert fails

    result = {
        "timestamp": now,
        "status": "sent",
        "from": from_agent,
        "to": to_agent,
        "routed_via": "coordinator",
        "target_project": project_path,
    }
    if not db_indexed:
        result["warning"] = "Message file delivered but DB insert failed. Target may need 'minion init'."
    return result
