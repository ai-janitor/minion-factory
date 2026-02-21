"""DB operations — invocation log, child PID tracking, session ID, compaction log."""
from __future__ import annotations

import os
import sqlite3
from typing import Any, TYPE_CHECKING

from ._constants import utc_now_iso, _get_rss_bytes, AgentRunResult

if TYPE_CHECKING:
    from ..config import SwarmConfig, AgentConfig


class DBMixin:
    """Methods for direct SQLite writes (agent runtime, invocations, compaction)."""

    config: SwarmConfig
    agent_cfg: AgentConfig
    agent_name: str
    _child_pid: int | None
    _generation: int
    _invocation_row_id: int | None

    def _write_agent_runtime(self, crew: str | None = None) -> None:
        """Write PID, crew to the agents table. Child PID + RSS written per-invocation."""
        try:
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute(
                "UPDATE agents SET pid = ?, crew = ? WHERE name = ?",
                (self._child_pid, crew, self.agent_name),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self._log(f"WARNING: _write_agent_runtime failed: {exc}")

    def _update_child_pid_in_db(self) -> None:
        """Write the current child PID + its RSS to agents (current state)."""
        try:
            rss = _get_rss_bytes(self._child_pid)
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute(
                "UPDATE agents SET pid = ?, rss_bytes = ? WHERE name = ?",
                (self._child_pid, rss, self.agent_name),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self._log(f"WARNING: _update_child_pid_in_db failed: {exc}")

    def _insert_invocation_start(self) -> int | None:
        """INSERT a row into invocation_log when child spawns. Returns row id."""
        try:
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
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
            row_id = cur.lastrowid
            conn.commit()
            conn.close()
            return row_id
        except Exception as exc:
            self._log(f"WARNING: _insert_invocation_start failed: {exc}")
            return None

    def _finalize_invocation(self, result: AgentRunResult) -> None:
        """UPDATE the invocation_log row with end-of-run data."""
        row_id = getattr(self, "_invocation_row_id", None)
        if not row_id:
            return
        try:
            rss = _get_rss_bytes(self._child_pid)
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
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
            conn.commit()
            conn.close()
        except Exception as exc:
            self._log(f"WARNING: _finalize_invocation failed: {exc}")
        finally:
            self._invocation_row_id = None

    def _check_interrupt(self) -> bool:
        """Check agent_interrupt table. Returns True if flag is set, and clears it."""
        try:
            conn = sqlite3.connect(str(self.config.comms_db), timeout=2)
            conn.execute("PRAGMA busy_timeout=2000")
            cur = conn.cursor()
            cur.execute("SELECT agent_name FROM agent_interrupt WHERE agent_name = ?", (self.agent_name,))
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM agent_interrupt WHERE agent_name = ?", (self.agent_name,))
                conn.commit()
                conn.close()
                return True
            conn.close()
        except Exception:
            pass
        return False

    def _log_compaction(self, tokens_pre: int, tokens_post: int) -> None:
        """INSERT a compaction event into compaction_log."""
        try:
            rss = _get_rss_bytes(self._child_pid)
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
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
            conn.commit()
            conn.close()
        except Exception as exc:
            self._log(f"WARNING: _log_compaction failed: {exc}")

    def _update_session_id(self, session_id: str) -> None:
        """Store session_id on provider and in DB."""
        self._provider.session_id = session_id
        try:
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute(
                "UPDATE agents SET session_id = ? WHERE name = ?",
                (session_id, self.agent_name),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self._log(f"WARNING: _update_session_id failed: {exc}")

    def _fetch_fenix_records(self) -> list[dict[str, Any]]:
        """Fetch and consume unconsumed fenix_down records for this agent."""
        try:
            conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=5000")
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
                conn.commit()
            conn.close()
            return records
        except Exception as exc:
            self._log(f"WARNING: _fetch_fenix_records failed: {exc}")
            return []

    # Defined in other mixins
    def _log(self, message: str) -> None: ...
