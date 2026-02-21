"""Polling — inbox polling, work checking, standdown/wake logic."""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional, TYPE_CHECKING

from minion.defaults import ENV_DB_PATH, ENV_DOCS_DIR

from ..triggers import handle_stand_down, handle_standdown, handle_wake_from_standdown

if TYPE_CHECKING:
    from threading import Event
    from ..config import SwarmConfig, AgentConfig
    from minion.providers.base import BaseProvider


class PollingMixin:
    """Methods for polling inbox, checking work availability, standdown/wake."""

    config: SwarmConfig
    agent_cfg: AgentConfig
    agent_name: str
    _stop_event: Event
    _stood_down: bool
    _last_task_id: int | None
    resume_ready: bool
    _provider: BaseProvider

    def _poll_inbox(self) -> Optional[Dict[str, Any]]:
        """Run minion poll as a subprocess. Returns poll data dict or None.
        Sets stop_event if stand_down detected (exit code 3).
        """
        try:
            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
            env[ENV_DB_PATH] = str(self.config.comms_db)
            env[ENV_DOCS_DIR] = str(self.config.docs_dir)
            proc = subprocess.run(
                ["minion", "poll", "--agent", self.agent_name, "--interval", "5", "--timeout", "30"],
                capture_output=True,
                text=True,
                env=env,
            )
            if proc.returncode == 3:
                handle_stand_down(self.agent_name, self._log, self._stop_event)
                return None
            if proc.returncode == 0 and proc.stdout.strip():
                try:
                    return json.loads(proc.stdout.strip())
                except json.JSONDecodeError:
                    self._log(f"POLL ERROR: non-JSON output: {proc.stdout[:200]}")
                    return None
            if proc.returncode not in (0, 1):
                # 0=content, 1=timeout — anything else is unexpected
                stderr_tail = (proc.stderr or "")[:300] if hasattr(proc, "stderr") else ""
                self._log(f"POLL ERROR: exit code {proc.returncode} stderr={stderr_tail}")
            return None
        except FileNotFoundError:
            self._log("FATAL: 'minion' binary not found in PATH — daemon cannot poll")
            self._stop_event.set()
            return None
        except Exception as exc:
            self._log(f"POLL ERROR: {type(exc).__name__}: {exc}")
            self._stop_event.wait(timeout=5.0)
            return None

    def _check_available_work(self) -> bool:
        """Quick DB check: does this agent have any claimable tasks?"""
        try:
            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
            env[ENV_DB_PATH] = str(self.config.comms_db)
            env[ENV_DOCS_DIR] = str(self.config.docs_dir)
            proc = subprocess.run(
                ["minion", "check-work", "--agent", self.agent_name],
                capture_output=True, text=True, timeout=10, env=env,
            )
            return proc.returncode == 0
        except Exception as exc:
            self._log(f"check-work failed: {exc}, assuming work exists")
            return True  # fail-open: don't stand down if check fails

    def _standdown(self, generation: int) -> None:
        """Agent has no work — stand down or self-dismiss based on config."""
        if self.agent_cfg.self_dismiss:
            from ..triggers import handle_self_dismiss

            def _clear_session() -> None:
                self.resume_ready = False
                self._provider.session_id = None

            self._stood_down = handle_self_dismiss(
                self.agent_name, generation, self._last_task_id,
                self._log, self._write_state, self._alert_lead_poll,
                _clear_session,
            )
        else:
            self._stood_down = handle_standdown(
                self.agent_name, generation, self._last_task_id,
                self._log, self._write_state, self._alert_lead_poll,
            )

    def _wake_from_standdown(self, poll_data: Dict[str, Any]) -> None:
        """Wake from stood-down state. Resume if same task, fresh if new."""
        self._stood_down = False

        def _clear_session() -> None:
            self.resume_ready = False
            self._provider.session_id = None

        handle_wake_from_standdown(
            self.agent_name, poll_data, self._last_task_id,
            self._log, _clear_session,
        )

    def _comms_name(self) -> str:
        """Poll mode is the default. Watcher mode only for explicit legacy paths."""
        db = str(self.config.comms_db)
        if ".minion-comms" in db:
            return "legacy"
        return "minion-comms"

    # Defined in other mixins
    def _log(self, message: str) -> None: ...
    def _write_state(self, status: str, **extra: Any) -> None: ...
    def _alert_lead_poll(self, message: str) -> None: ...
