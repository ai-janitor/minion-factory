from __future__ import annotations

from typing import List, Optional

from .base import BaseProvider


class ClaudeProvider(BaseProvider):
    """Claude Code CLI provider."""

    def build_command(self, prompt: str, use_resume: bool = False) -> List[str]:
        cmd = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        # Replace the default system prompt entirely so daemon agents don't
        # inherit user CLAUDE.md, ~/.claude/rules/, or Claude CLI defaults.
        # Only our assembled prompt + persona goes in.
        system = self.agent_cfg.system.strip() if self.agent_cfg.system else ""
        if system:
            cmd.extend(["--system-prompt", system])
        # Session continuity: --resume <id> targets a specific session,
        # --continue resumes the last session (watcher mode only).
        # They're mutually exclusive.
        if use_resume and self.session_id:
            cmd.extend(["--resume", self.session_id])
        elif not self.use_poll:
            cmd.append("--continue")
        if self.agent_cfg.allowed_tools:
            cmd.extend(["--allowed-tools", self.agent_cfg.allowed_tools])
        if self.agent_cfg.permission_mode:
            cmd.extend(["--permission-mode", self.agent_cfg.permission_mode])
        if self.agent_cfg.model:
            cmd.extend(["--model", self.agent_cfg.model])
        return cmd

    def prompt_guardrails(self) -> str:
        # Claude follows instructions well — minimal guardrails needed
        return ""

    @property
    def supports_resume(self) -> bool:
        return True

    @property
    def resume_label(self) -> str:
        return "claude --resume"

    @staticmethod
    def extract_session_id(line: str) -> Optional[str]:
        """Parse session UUID from a stream-json result event."""
        try:
            import json
            data = json.loads(line.strip())
            if isinstance(data, dict) and data.get("type") == "result":
                sid = data.get("session_id") or data.get("sessionId")
                if sid and isinstance(sid, str):
                    return sid
        except (json.JSONDecodeError, ValueError):
            pass
        return None
