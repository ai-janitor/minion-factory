"""Agent daemon runner — assembled from single-concern mixins.

Each mixin file holds one logical concern:
    _constants    — AgentRunResult, token constants, helpers
    _stream       — stream-json parsing, compaction detection
    _hp           — token usage extraction, HP tracking
    _state        — read/write agent state JSON
    _db           — SQLite operations (invocations, PID, session)
    _prompts      — boot/inbox/watcher prompt assembly
    _polling      — inbox polling, standdown/wake logic
    _execution    — subprocess management, prompt processing
    _alerting     — lead agent alerts
    _watcher_mode — legacy direct-DB watcher mode
"""
from __future__ import annotations

import signal
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ._constants import AgentRunResult
from ._stream import StreamMixin
from ._hp import HPMixin
from ._state import StateMixin
from ._db import DBMixin
from ._prompts import PromptMixin
from ._polling import PollingMixin
from ._execution import ExecutionMixin
from ._alerting import AlertingMixin
from ._watcher_mode import WatcherModeMixin

from ..buffer import RollingBuffer
from ..config import SwarmConfig
from ..triggers import handle_signal, detect_halt

from minion.providers import get_provider

__all__ = ["AgentDaemon", "AgentRunResult"]


class AgentDaemon(
    StreamMixin,
    HPMixin,
    StateMixin,
    DBMixin,
    PromptMixin,
    PollingMixin,
    ExecutionMixin,
    AlertingMixin,
    WatcherModeMixin,
):
    def __init__(self, config: SwarmConfig, agent_name: str) -> None:
        if agent_name not in config.agents:
            raise KeyError(f"Unknown agent '{agent_name}' in config")

        self.config = config
        self.agent_cfg = config.agents[agent_name]
        self.agent_name = agent_name

        self.buffer = RollingBuffer(self.agent_cfg.max_history_tokens)

        self.inject_history_next_turn = False
        self.consecutive_failures = 0
        self.last_error: Optional[str] = None

        self._stop_event = threading.Event()
        self._invocation = 0
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._tool_overhead_tokens = 0  # Claude Code system prompt/tools overhead, measured at boot
        self._context_window = 0        # Set from modelUsage.contextWindow in stream-json

        self._child_pid: int | None = None
        self._generation = 0
        self._invocation_row_id: int | None = None
        self._stood_down = False
        self._last_task_id: int | None = None

        self.state_path = self.config.state_dir / f"{self.agent_name}.json"
        self.resume_ready = self._load_resume_ready()

        # watcher mode uses direct DB access for backward compat
        self._use_poll = self._comms_name() == "minion-comms"
        self._watcher: Any = None

        self._provider = get_provider(
            self.agent_cfg.provider, self.agent_name, self.agent_cfg, self._use_poll,
        )
        self._error_log = self.config.logs_dir / f"{self.agent_name}.error.log"

    def run(self) -> None:
        self.config.ensure_runtime_dirs()

        if self._use_poll:
            self._run_poll_mode()
        else:
            self._run_watcher_mode()

    def _run_poll_mode(self) -> None:
        """minion-comms mode: poll.sh + claude invocations. No direct DB access.

        Outer loop handles auto-respawn on context death (phoenix_down).
        Inner loop handles message polling and agent invocations.
        Only SIGTERM/SIGINT or stand_down exits the outer loop.
        """
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # Write PID + crew to DB so observability doesn't depend on state files
        crew_name = self.config.config_path.stem if self.config.config_path else None
        self._write_agent_runtime(crew=crew_name)

        self._log(f"starting daemon for {self.agent_name}")
        self._log(f"provider: {self.agent_cfg.provider} (resume_ready={self.resume_ready})")
        self._log(f"db: {self.config.comms_db}")
        self._log(f"project_dir: {self.config.project_dir}")
        self._log("mode: poll (minion poll)")

        self._generation = 0
        while not self._stop_event.is_set():
            self._generation += 1
            generation = self._generation
            exit_reason = self._poll_generation(generation)
            if exit_reason == "phoenix_down":
                self._log(f"\U0001f504 auto-respawn: generation {generation} died (context exhausted), rebooting as generation {generation + 1}")
                self._reset_for_respawn()
                continue
            break

        self._write_state("stopped")
        self._log("daemon stopped")

    def _poll_generation(self, generation: int) -> str:
        """Run one boot + poll cycle. Returns exit reason: 'phoenix_down', 'signal', or 'stand_down'."""
        self._write_state("idle", generation=generation)

        # Reset stale HP from previous generation
        self._update_hp(0, 0, turn_input=0, turn_output=0)

        # Boot: invoke claude directly to run ON STARTUP instructions
        self._log(f"boot (gen {generation}): invoking agent for ON STARTUP")
        self._write_state("working", generation=generation)
        boot_prompt = self._build_boot_prompt()
        result = self._run_agent(boot_prompt)
        if result.exit_code == 0:
            self.resume_ready = True
            if result.input_tokens > 0:
                self._record_boot_hp(boot_prompt, result)
            self._log(f"boot (gen {generation}): complete")
        else:
            self._log(f"boot (gen {generation}): failed (exit {result.exit_code})")

        self._write_state("idle", generation=generation)

        # Fetch any unconsumed fenix_down records for resume context
        pending_fenix_records = self._fetch_fenix_records()
        if pending_fenix_records:
            self._log(f"found {len(pending_fenix_records)} fenix_down record(s) from prior session")

        while not self._stop_event.is_set():
            print(".", end="", flush=True)
            poll_data = self._poll_inbox()

            if self._stop_event.is_set():
                # Check if we're stopping due to phoenix_down vs signal/stand_down
                state = self._read_state()
                if state.get("status") == "phoenix_down":
                    return "phoenix_down"
                return "signal"

            if not poll_data:
                self._stop_event.wait(timeout=5.0)
                continue

            print(flush=True)  # newline after dots
            # Wake from standdown if needed (decides resume vs fresh)
            if self._stood_down:
                self._wake_from_standdown(poll_data)
            self._write_state("working", generation=generation)

            messages = poll_data.get("messages", [])
            tasks = poll_data.get("tasks", [])
            for msg in messages:
                sender = msg.get("from_agent", "?")
                content = msg.get("content", "")
                preview = content[:200].replace("\n", " ")
                self._log(f"\U0001f4e8 from {sender}: {preview}")
            for task in tasks:
                self._log(f"\U0001f4cb task #{task.get('task_id')}: {task.get('title', '?')}")
            if not messages and not tasks:
                self._log("messages detected, invoking agent")

            # Track which task we're about to work on
            task_ids = [t.get("task_id") for t in tasks if t.get("task_id")]
            if task_ids:
                self._last_task_id = task_ids[0]

            # Inject fenix_down records from prior session into first poll cycle
            if pending_fenix_records:
                poll_data["fenix_down_records"] = pending_fenix_records
                pending_fenix_records = []  # only inject once

            halt_requested = detect_halt(poll_data)

            prompt = self._build_inbox_prompt(poll_data)
            ok = self._process_prompt(prompt)

            if ok:
                self.consecutive_failures = 0
                self.last_error = None
                # Check if _process_prompt triggered phoenix_down
                state = self._read_state()
                if state.get("status") == "phoenix_down":
                    return "phoenix_down"
                # Halt: agent finished its work after seeing halt message — exit cleanly
                if halt_requested:
                    self._log("halt complete — agent finished work and saved state. Exiting.")
                    self._write_state("halted", generation=generation)
                    self._stop_event.set()
                    return "halt"
                # Standdown check: did the agent just finish its last piece of work?
                if not self._check_available_work():
                    self._standdown(generation)
                else:
                    self._write_state("idle", generation=generation)
            else:
                self.consecutive_failures += 1
                self._write_state(
                    "error",
                    failures=self.consecutive_failures,
                    last_error=self.last_error,
                    generation=generation,
                )
                backoff = min(
                    self.agent_cfg.retry_backoff_sec * (2 ** (self.consecutive_failures - 1)),
                    self.agent_cfg.retry_backoff_max_sec,
                )
                self._log(f"failure #{self.consecutive_failures}; backing off {backoff}s ({self.last_error or 'unknown'})")
                if self.consecutive_failures >= 3:
                    self._alert_lead_poll(
                        f"agent {self.agent_name} has {self.consecutive_failures} "
                        f"consecutive failures. Last error: {self.last_error or 'unknown'}"
                    )
                self._stop_event.wait(timeout=float(backoff))

        return "signal"

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        handle_signal(signum, self._log, self._stop_event)

    def _log(self, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] [{self.agent_name}] {message}", flush=True)
