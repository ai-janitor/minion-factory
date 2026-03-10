"""Opencode.

Purpose: Opencode module.
Rationale: Extracted into own module for single-responsibility provider configuration.
Responsibility: Opencode. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source.
"""
from __future__ import annotations

from typing import List

from .cli_provider_protocol import BaseProvider


class OpencodeProvider(BaseProvider):
    """Opencode CLI provider."""

    def build_command(self, prompt: str, use_resume: bool = False) -> List[str]:
        cmd = ["opencode", "run", "--format", "json"]
        if use_resume:
            cmd.append("--continue")
        if self.agent_cfg.model:
            cmd.extend(["--model", self.agent_cfg.model])
        cmd.append(prompt)
        return cmd

    def prompt_guardrails(self) -> str:
        name = self.agent_name
        return "\n".join([
            f"You are {name}. Run only the commands listed, then stop.",
            "Do not explore the codebase or take initiative beyond the task.",
        ])

    @property
    def supports_resume(self) -> bool:
        return True

    @property
    def resume_label(self) -> str:
        return "opencode --continue"
