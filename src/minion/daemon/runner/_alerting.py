"""Alerting — send alerts to lead agent via CLI or watcher."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, TYPE_CHECKING

from minion.defaults import ENV_CLASS, ENV_DB_PATH, ENV_DOCS_DIR

if TYPE_CHECKING:
    from ..config import SwarmConfig, AgentConfig


class AlertingMixin:
    """Methods for alerting the lead agent about failures."""

    config: SwarmConfig
    agent_cfg: AgentConfig
    agent_name: str
    consecutive_failures: int
    last_error: str | None

    def _alert_lead_poll(self, message: str) -> None:
        """Send alert to lead via minion CLI (poll mode — no direct DB access)."""
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        env[ENV_CLASS] = "lead"
        env[ENV_DB_PATH] = str(self.config.comms_db)
        env[ENV_DOCS_DIR] = str(self.config.docs_dir)
        try:
            result = subprocess.run(
                ["minion", "send", "--from", self.agent_name, "--to", "commander",
                 "--message", message],
                capture_output=True, text=True, timeout=10, env=env,
            )
            if result.returncode != 0:
                # Fall back to any lead
                r2 = subprocess.run(
                    ["minion", "send", "--from", self.agent_name, "--to", "lead",
                     "--message", message],
                    capture_output=True, text=True, timeout=10, env=env,
                )
                if r2.returncode != 0:
                    print(f"ALERT SEND FAILED: both commander and lead unreachable. stderr={r2.stderr[:200]}", file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"ALERT SEND FAILED: {exc}", file=sys.stderr, flush=True)
        self._log(f"ALERT: {message}")
        print(f"\U0001f6a8 [{self.agent_name}] {message}", file=sys.stderr, flush=True)

    def _alert_lead_watcher(self, watcher: Any) -> None:
        lead = watcher.find_lead_agent() or "lead"
        content = (
            f"minion-swarm alert: agent {self.agent_name} has {self.consecutive_failures} "
            f"consecutive failures. Last error: {self.last_error or 'unknown'}."
        )
        try:
            watcher.send_message(self.agent_name, lead, content)
            self._log(f"alerted lead '{lead}' about repeated failures")
        except Exception as exc:
            self._log(f"ALERT ERROR: failed to message lead '{lead}': {type(exc).__name__}: {exc}")

    # Defined in other mixins
    def _log(self, message: str) -> None: ...
