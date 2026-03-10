from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List, Optional

from .base import BaseProvider


class CodexProvider(BaseProvider):
    """OpenAI Codex CLI provider."""

    def build_command(self, prompt: str, use_resume: bool = False) -> List[str]:
        cmd = ["codex", "exec"]
        if use_resume:
            cmd.extend(["resume", "--last"])
        cmd.append("--json")
        if self.agent_cfg.permission_mode == "bypassPermissions":
            cmd.extend([
                "--sandbox", "workspace-write",
                "--add-dir", os.path.expanduser("~/.minion_work"),
                "-c", "shell_environment_policy.inherit=all",
            ])
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

    # filter_log_line inherited from BaseProvider — uses _classify_error hook

    @property
    def supports_resume(self) -> bool:
        return True

    @property
    def resume_label(self) -> str:
        return "codex resume --last"

    def _classify_error(self, line: str) -> Optional[str]:
        """Extract short error summary from Codex verbose output.

        Codex-specific patterns: JSON error/message fields, capacity exhausted,
        rate limit. Falls back to base _extract_error_summary for generic cases.
        """
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                err_msg = data.get("error") or data.get("message") or ""
                if isinstance(err_msg, str) and err_msg:
                    return f"CODEX_ERROR — {err_msg[:120]}"
                if isinstance(err_msg, dict):
                    return f"CODEX_ERROR — {err_msg.get('message', '')[:120]}"
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

        # Pattern: "capacity exhausted", "rate limit", etc.
        m = re.search(r'(capacity\s+exhausted|rate\s*limit|overloaded)', line, re.IGNORECASE)
        if m:
            return f"CODEX_ERROR — {m.group(1)}"

        return self._extract_error_summary(line)

    # _append_error_log inherited from BaseProvider
