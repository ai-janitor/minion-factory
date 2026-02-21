"""State I/O — read/write agent state JSON, load resume flag, respawn reset."""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Optional, TYPE_CHECKING

from ._constants import utc_now_iso, _get_rss_bytes

if TYPE_CHECKING:
    from pathlib import Path
    from ..config import SwarmConfig, AgentConfig
    from ..buffer import RollingBuffer


class StateMixin:
    """Methods for reading/writing agent state to disk and DB."""

    config: SwarmConfig
    agent_cfg: AgentConfig
    agent_name: str
    state_path: Path
    resume_ready: bool
    consecutive_failures: int
    last_error: Optional[str]
    inject_history_next_turn: bool
    _stood_down: bool
    _child_pid: int | None
    _stop_event: threading.Event
    _session_input_tokens: int
    _session_output_tokens: int
    _tool_overhead_tokens: int
    _context_window: int
    _invocation: int
    _last_task_id: int | None
    buffer: RollingBuffer

    def _load_resume_ready(self) -> bool:
        if not self.state_path.exists():
            return False
        try:
            payload = json.loads(self.state_path.read_text())
        except (OSError, json.JSONDecodeError, TypeError):
            return False
        return bool(payload.get("resume_ready", False))

    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text())
        except (OSError, json.JSONDecodeError, TypeError):
            return {}

    def _write_state(self, status: str, **extra: Any) -> None:
        payload = {
            "agent": self.agent_name,
            "provider": self.agent_cfg.provider,
            "pid": os.getpid(),
            "status": status,
            "updated_at": utc_now_iso(),
            "consecutive_failures": self.consecutive_failures,
            "resume_ready": self.resume_ready,
            "stood_down": self._stood_down,
        }
        payload.update(extra)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(payload, indent=2))

        # Piggyback RSS update — measure child if alive, else last known
        if self._child_pid:
            import sqlite3
            try:
                rss = _get_rss_bytes(self._child_pid)
                conn = sqlite3.connect(str(self.config.comms_db), timeout=5)
                conn.execute("PRAGMA busy_timeout=5000")
                conn.execute(
                    "UPDATE agents SET rss_bytes = ? WHERE name = ?",
                    (rss, self.agent_name),
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

    def _reset_for_respawn(self) -> None:
        """Reset daemon state for a fresh generation after context death."""
        from ..buffer import RollingBuffer

        self._stop_event.clear()
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._tool_overhead_tokens = 0
        self._context_window = 0
        self._invocation = 0
        self.resume_ready = False
        self.consecutive_failures = 0
        self.last_error = None
        self.buffer = RollingBuffer(self.agent_cfg.max_history_tokens)
        self.inject_history_next_turn = False
        self._stood_down = False
        self._last_task_id = None
