"""Prompt building — boot, inbox, watcher prompts."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import SwarmConfig, AgentConfig
    from ..buffer import RollingBuffer
    from minion.providers.base import BaseProvider


class PromptMixin:
    """Methods for assembling prompts sent to the agent."""

    config: SwarmConfig
    agent_cfg: AgentConfig
    agent_name: str
    inject_history_next_turn: bool
    buffer: RollingBuffer
    _provider: BaseProvider

    def _build_boot_prompt(self) -> str:
        """Prompt for the first invocation — agent registers and sets up.

        Note: agent_cfg.system is passed via --system-prompt by the
        provider, so we exclude it here to avoid duplication.
        """
        from minion.prompts import build_boot_prompt as _build_boot
        return _build_boot(
            docs_dir=self.config.docs_dir,
            agent=self.agent_name,
            role=self.agent_cfg.role or "coder",
            guardrails=self._build_provider_section(),
            capabilities=self.agent_cfg.capabilities,
        )

    def _build_inbox_prompt(self, poll_data: Dict[str, Any]) -> str:
        """Prompt with messages/tasks already inline — no need to fetch.

        Note: agent_cfg.system is passed via --system-prompt by the
        provider, so we exclude it here to avoid duplication.
        """
        history_snapshot = None
        if self.inject_history_next_turn and len(self.buffer) > 0:
            history_snapshot = self.buffer.snapshot()
            self.inject_history_next_turn = False

        from minion.prompts import build_inbox_prompt as _build_inbox
        return _build_inbox(
            docs_dir=self.config.docs_dir,
            agent=self.agent_name,
            role=self.agent_cfg.role or "coder",
            poll_data=poll_data,
            guardrails=self._build_provider_section(),
            history_snapshot=history_snapshot,
            capabilities=self.agent_cfg.capabilities,
        )

    @staticmethod
    def _strip_on_startup(text: str) -> str:
        """Remove ON STARTUP block from system prompt for subsequent invocations."""
        # Match "ON STARTUP ..." through to the next blank line or end of string
        return re.sub(
            r"ON STARTUP[^\n]*\n(?:[ \t]+\d+\..*\n)*(?:[ \t]+Then .*\n?)?",
            "",
            text,
        ).strip()

    def _build_provider_section(self) -> str:
        """Provider-specific prompt guardrails — delegated to provider module."""
        return self._provider.prompt_guardrails()
