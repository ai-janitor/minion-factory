"""Polling — inbox polling, work checking, standdown/wake logic.

Purpose: Polling — inbox polling, work checking, standdown/wake logic.
Rationale: Extracted into own module for single-responsibility daemon transport.
Responsibility: Polling — inbox polling, work checking, standdown/wake logic. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""
from __future__ import annotations

import json
import os
import signal as _signal
import subprocess
import time as _time
from typing import Any, Dict, Optional, TYPE_CHECKING

from minion.defaults import ENV_CLASS, ENV_DB_PATH, ENV_DOCS_DIR

from ..triggers import handle_stand_down, handle_standdown, handle_wake_from_standdown

_SIGTERM = _signal.SIGTERM
_SIGKILL = _signal.SIGKILL


def _monotonic_now() -> float:
    return _time.monotonic()

if TYPE_CHECKING:
    from threading import Event
    from ..config import SwarmConfig, AgentConfig
    from minion.providers.cli_provider_protocol import BaseProvider


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

        Backlog #338: previously used subprocess.run(timeout=60), which blocks
        in C-level waitpid for up to 30-60s while a SIGTERM arrives, defers
        the python signal handler, and forces #310's SIGKILL fallback to fire
        every stand-down. Now uses Popen + a poll loop that wakes on
        _stop_event every 0.5s, terminating the child poll process promptly
        on shutdown so SIGTERM is honored within ~half a second.
        """
        try:
            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
            env[ENV_CLASS] = self.agent_cfg.role or "coder"
            env[ENV_DB_PATH] = str(self.config.comms_db)
            env[ENV_DOCS_DIR] = str(self.config.docs_dir)
            proc = subprocess.Popen(
                ["minion", "poll", "--agent", self.agent_name, "--interval", "5", "--timeout", "30"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                start_new_session=True,  # own pgid so SIGTERM kills the whole tree
            )
        except FileNotFoundError:
            self._log("FATAL: 'minion' binary not found in PATH — daemon cannot poll")
            self._stop_event.set()
            return None
        except (subprocess.SubprocessError, OSError) as exc:
            self._log(f"POLL ERROR: {type(exc).__name__}: {exc}")
            self._stop_event.wait(timeout=5.0)
            return None

        # Wake every 0.5s — long enough that the busy-wait is cheap, short
        # enough that SIGTERM gets seen before #310's SIGKILL fallback fires.
        WALL_BUDGET_SEC = 60
        deadline = _monotonic_now() + WALL_BUDGET_SEC
        try:
            while True:
                if self._stop_event.is_set():
                    self._terminate_poll_subprocess(proc)
                    return None
                rc = proc.poll()
                if rc is not None:
                    break
                if _monotonic_now() >= deadline:
                    self._log("POLL ERROR: subprocess exceeded 60s budget — terminating")
                    self._terminate_poll_subprocess(proc)
                    return None
                # Cooperative wait — short enough to react to stop_event
                self._stop_event.wait(timeout=0.5)

            stdout, stderr = proc.communicate(timeout=5)
        except (subprocess.SubprocessError, OSError) as exc:
            self._log(f"POLL ERROR: {type(exc).__name__}: {exc}")
            self._terminate_poll_subprocess(proc)
            return None

        if proc.returncode == 3:
            handle_stand_down(self.agent_name, self._log, self._stop_event)
            return None
        if proc.returncode == 0 and stdout and stdout.strip():
            try:
                return json.loads(stdout.strip())
            except json.JSONDecodeError:
                self._log(f"POLL ERROR: non-JSON output: {stdout[:200]}")
                return None
        if proc.returncode not in (0, 1):
            # 0=content, 1=timeout — anything else is unexpected
            stderr_tail = (stderr or "")[:300]
            self._log(f"POLL ERROR: exit code {proc.returncode} stderr={stderr_tail}")
        return None

    def _terminate_poll_subprocess(self, proc: "subprocess.Popen[str]") -> None:
        """Best-effort kill of a stuck minion-poll subprocess and its pgroup.

        Backlog #338: when SIGTERM arrives mid-poll, killing only the direct
        child can leave grandchildren behind. Popen was started with
        start_new_session=True so we can SIGTERM the whole pgid in one go,
        then SIGKILL after a short grace period.
        """
        if proc.poll() is not None:
            return
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, _SIGTERM)
        except (OSError, ProcessLookupError):
            try:
                proc.terminate()
            except (OSError, ProcessLookupError):
                pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, _SIGKILL)
            except (OSError, ProcessLookupError):
                try:
                    proc.kill()
                except (OSError, ProcessLookupError):
                    pass

    def _check_available_work(self) -> bool:
        """Quick DB check: does this agent have any claimable tasks?"""
        try:
            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
            env[ENV_CLASS] = self.agent_cfg.role or "coder"
            env[ENV_DB_PATH] = str(self.config.comms_db)
            env[ENV_DOCS_DIR] = str(self.config.docs_dir)
            proc = subprocess.run(
                ["minion", "check-work", "--agent", self.agent_name],
                capture_output=True, text=True, timeout=10, env=env,
            )
            return proc.returncode == 0
        except (subprocess.SubprocessError, OSError, subprocess.TimeoutExpired) as exc:
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
