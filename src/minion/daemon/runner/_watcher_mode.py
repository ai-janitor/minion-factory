"""Watcher mode — legacy direct-DB message watching."""
from __future__ import annotations

import signal
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from threading import Event
    from ..config import SwarmConfig, AgentConfig
    from ..watcher import CommsWatcher


class WatcherModeMixin:
    """Legacy watcher mode: direct DB access for message polling."""

    config: SwarmConfig
    agent_cfg: AgentConfig
    agent_name: str
    _stop_event: Event
    _watcher: Any
    consecutive_failures: int
    last_error: str | None

    def _get_watcher(self) -> Any:
        """Lazy-init watcher for legacy watcher mode only."""
        if self._watcher is None:
            from ..watcher import CommsWatcher
            self._watcher = CommsWatcher(self.agent_name, self.config.comms_db)
        return self._watcher

    def _run_watcher_mode(self) -> None:
        """Legacy watcher mode: direct DB access."""
        watcher = self._get_watcher()
        watcher.start()
        watcher.register_agent(
            role=self.agent_cfg.role,
            description=f"minion-swarm daemon agent ({self.agent_cfg.zone})",
            status="online",
        )

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._log(f"starting daemon for {self.agent_name}")
        self._log(f"provider: {self.agent_cfg.provider} (resume_ready={self.resume_ready})")
        self._log(f"mode: watcher (DB: {self.config.comms_db})")
        self._write_state("idle")

        try:
            while not self._stop_event.is_set():
                message = watcher.pop_next_message()

                if message is None:
                    watcher.set_agent_status("idle")
                    self._write_state("idle")
                    watcher.wait_for_update(timeout=5.0)
                    continue

                watcher.set_agent_status("working")
                self._write_state(
                    "working",
                    current_message_id=message.id,
                    from_agent=message.from_agent,
                    received_at=message.timestamp,
                )
                self._log(f"processing message {message.id} from {message.from_agent}")

                prompt = self._build_watcher_prompt(message)
                ok = self._process_prompt(prompt)

                if ok:
                    watcher.set_agent_status("online")
                    self._write_state("idle", last_message_id=message.id)
                    continue

                self._write_state(
                    "error",
                    failures=self.consecutive_failures,
                    last_error=self.last_error,
                    failed_message_id=message.id,
                )

                backoff = min(
                    self.agent_cfg.retry_backoff_sec * (2 ** (self.consecutive_failures - 1)),
                    self.agent_cfg.retry_backoff_max_sec,
                )
                self._log(f"failure #{self.consecutive_failures}; backing off {backoff}s ({self.last_error or 'unknown'})")

                if self.consecutive_failures >= 3:
                    self._alert_lead_watcher(watcher)

                self._stop_event.wait(timeout=float(backoff))

        finally:
            watcher.set_agent_status("offline")
            self._write_state("stopped")
            watcher.stop()
            self._log("daemon stopped")

    def _build_watcher_prompt(self, message: Any) -> str:
        """Build prompt with message content baked in (watcher mode).

        Note: agent_cfg.system is passed via --system-prompt by the
        provider, so we exclude it here to avoid duplication.
        """
        max_prompt_chars = self.agent_cfg.max_prompt_chars

        history_snapshot = None
        if self.inject_history_next_turn and len(self.buffer) > 0:
            history_snapshot = self.buffer.snapshot()
            self.inject_history_next_turn = False

        from minion.prompts import build_watcher_prompt as _build_watcher
        prompt = _build_watcher(
            docs_dir=self.config.docs_dir,
            agent=self.agent_name,
            role=self.agent_cfg.role or "coder",
            message_section=self._build_incoming_section(message),
            history_snapshot=history_snapshot,
            capabilities=self.agent_cfg.capabilities,
        )

        if len(prompt) > max_prompt_chars:
            prompt = prompt[:max_prompt_chars]
            self._log("hard-truncated prompt to max_prompt_chars")

        return prompt

    def _build_incoming_section(self, message: Any) -> str:
        return "\n".join(
            [
                "Incoming message:",
                f"- id: {message.id}",
                f"- from: {message.from_agent}",
                f"- timestamp: {message.timestamp}",
                f"- broadcast: {message.is_broadcast}",
                "",
                message.content,
            ]
        )

    # Defined in other mixins
    def _log(self, message: str) -> None: ...
    def _write_state(self, status: str, **extra: Any) -> None: ...
    def _process_prompt(self, prompt: str) -> bool: ...
    def _alert_lead_watcher(self, watcher: Any) -> None: ...
    def _handle_signal(self, signum: int, _frame: Any) -> None: ...
