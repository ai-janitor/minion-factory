"""DB operations — invocation log, child PID tracking, session ID, compaction log.

All DB connections use the canonical db.connection.connect() for consistent
WAL mode, row_factory, and busy_timeout settings.

Purpose: DB operations — invocation log, child PID tracking, session ID, compaction log.
Rationale: Extracted into own module for single-responsibility daemon transport.
Responsibility: DB operations — invocation log, child PID tracking, session ID, compaction log. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""
from __future__ import annotations

import os
import sqlite3
from typing import Any, TYPE_CHECKING

from minion.db.connection import connect as _daemon_connect
from ._constants import utc_now_iso, _get_rss_bytes, AgentRunResult

if TYPE_CHECKING:
    from ..config import SwarmConfig, AgentConfig


class DBMixin:
    """Methods for direct SQLite writes (agent runtime, invocations, compaction).

    All DB operations follow the same connect-execute-commit-close pattern.
    The _db_execute helper centralizes this to avoid repeating connection
    boilerplate across every method.
    """

    config: SwarmConfig
    agent_cfg: AgentConfig
    agent_name: str
    _child_pid: int | None
    _generation: int
    _invocation_row_id: int | None

    def _db_execute(self, callback, *, timeout: int = 5, row_factory=None,
                    caller: str = "db_execute"):
        """Open a SQLite connection, run callback(conn), commit, close.

        Centralizes the connect -> PRAGMA -> execute -> commit -> close pattern
        that was repeated 10+ times across this mixin. The callback receives
        the open connection and can execute any SQL. Returns whatever the
        callback returns.

        On error: logs a warning with the caller name and returns None.
        """
        conn = None
        try:
            conn = _daemon_connect(str(self.config.comms_db), timeout=timeout)
            if row_factory:
                conn.row_factory = row_factory
            result = callback(conn)
            conn.commit()
            return result
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError, OSError) as exc:
            self._log(f"WARNING: {caller} failed: {exc}")
            return None
        finally:
            if conn:
                conn.close()

    def _write_agent_runtime(self, crew: str | None = None) -> None:
        """Write the long-lived daemon-run wrapper PID + crew to agents.

        Backlog #336: previously wrote self._child_pid, which is None at boot
        and the per-invocation claude subprocess PID later. That made
        sitrep's liveness probe fail because the recorded PID either was
        NULL or pointed at a dead claude process. The agents.pid column
        is the operator-facing "is this daemon running" PID, so it must
        be the wrapper process (us, os.getpid()), not transient children.
        Per-invocation child PIDs still get tracked in invocation_log via
        _insert_invocation_start().
        """
        import os as _os
        wrapper_pid = _os.getpid()
        def _do(conn):
            conn.execute(
                "UPDATE agents SET pid = ?, crew = ? WHERE name = ?",
                (wrapper_pid, crew, self.agent_name),
            )
        self._db_execute(_do, caller="_write_agent_runtime")

    def _update_child_pid_in_db(self) -> None:
        """Update RSS for the current child invocation.

        Backlog #336: this used to also overwrite agents.pid with the child
        PID, which clobbered the long-lived wrapper PID written by
        _write_agent_runtime() and broke sitrep liveness. Now it only
        refreshes rss_bytes — child PIDs live exclusively in invocation_log.
        """
        rss = _get_rss_bytes(self._child_pid)
        def _do(conn):
            conn.execute(
                "UPDATE agents SET rss_bytes = ? WHERE name = ?",
                (rss, self.agent_name),
            )
        self._db_execute(_do, caller="_update_child_pid_in_db")

    def _insert_invocation_start(self) -> int | None:
        """INSERT a row into invocation_log when child spawns. Returns row id."""
        def _do(conn):
            cur = conn.execute(
                """INSERT INTO invocation_log
                   (agent_name, pid, model, generation, rss_bytes, started_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    self.agent_name,
                    self._child_pid,
                    self.agent_cfg.model,
                    self._generation,
                    _get_rss_bytes(self._child_pid),
                    utc_now_iso(),
                ),
            )
            return cur.lastrowid
        return self._db_execute(_do, caller="_insert_invocation_start")

    def _finalize_invocation(self, result: AgentRunResult) -> None:
        """UPDATE the invocation_log row with end-of-run data."""
        row_id = getattr(self, "_invocation_row_id", None)
        if not row_id:
            return
        rss = _get_rss_bytes(self._child_pid)
        def _do(conn):
            conn.execute(
                """UPDATE invocation_log SET
                   rss_bytes = ?, input_tokens = ?, output_tokens = ?,
                   exit_code = ?, timed_out = ?, interrupted = ?,
                   compacted = ?, ended_at = ?
                   WHERE id = ?""",
                (
                    rss,
                    result.input_tokens,
                    result.output_tokens,
                    result.exit_code,
                    int(result.timed_out),
                    int(result.interrupted),
                    int(result.compaction_detected),
                    utc_now_iso(),
                    row_id,
                ),
            )
        self._db_execute(_do, caller="_finalize_invocation")
        self._invocation_row_id = None

    def _check_interrupt(self) -> bool:
        """Check agent_interrupt table. Returns True if flag is set, and clears it."""
        def _do(conn):
            cur = conn.cursor()
            cur.execute("SELECT agent_name FROM agent_interrupt WHERE agent_name = ?", (self.agent_name,))
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM agent_interrupt WHERE agent_name = ?", (self.agent_name,))
                return True
            return False
        result = self._db_execute(_do, timeout=2, caller="_check_interrupt")
        return result if result is not None else False

    def _log_compaction(self, tokens_pre: int, tokens_post: int) -> None:
        """INSERT a compaction event into compaction_log."""
        rss = _get_rss_bytes(self._child_pid)
        def _do(conn):
            conn.execute(
                """INSERT INTO compaction_log
                   (agent_name, model, pid, rss_pre_bytes, tokens_pre, tokens_post, generation, compacted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.agent_name,
                    self.agent_cfg.model,
                    os.getpid(),
                    rss,
                    tokens_pre,
                    tokens_post,
                    self._generation,
                    utc_now_iso(),
                ),
            )
        self._db_execute(_do, caller="_log_compaction")

    def _update_session_id(self, session_id: str) -> None:
        """Store session_id on provider and in DB."""
        self._provider.session_id = session_id
        def _do(conn):
            conn.execute(
                "UPDATE agents SET session_id = ? WHERE name = ?",
                (session_id, self.agent_name),
            )
        self._db_execute(_do, caller="_update_session_id")

    def _has_pending_halt(self) -> bool:
        """Check if there's a HALT message waiting in the inbox."""
        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT content FROM messages WHERE to_agent = ? AND read_flag = 0",
                (self.agent_name,),
            )
            for row in cur.fetchall():
                content = (row[0] or "").upper()
                if "HALT:" in content or "HALT " in content:
                    return True
            return False
        result = self._db_execute(_do, caller="_has_pending_halt")
        return result if result is not None else False

    def _fetch_fenix_records(self) -> list[dict[str, Any]]:
        """Fetch and consume unconsumed fenix_down records for this agent."""
        def _do(conn):
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM fenix_down_records WHERE agent_name = ? AND consumed = 0 ORDER BY created_at DESC",
                (self.agent_name,),
            )
            records = [dict(row) for row in cur.fetchall()]
            if records:
                ids = [r["id"] for r in records]
                placeholders = ",".join(["?"] * len(ids))
                cur.execute(f"UPDATE fenix_down_records SET consumed = 1 WHERE id IN ({placeholders})", ids)
            return records
        result = self._db_execute(_do, row_factory=sqlite3.Row, caller="_fetch_fenix_records")
        return result if result is not None else []

    # Defined in other mixins
    def _log(self, message: str) -> None: ...
