"""Codex.

Purpose: Codex module.
Rationale: Extracted into own module for single-responsibility provider configuration.
Responsibility: Codex. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source.
F-051: _classify_error delegates to shared classify_provider_error() with Codex config.
"""
from __future__ import annotations

import logging
import os
import re
from typing import List, Optional

from ._shared_error_classifier import ProviderErrorConfig, classify_provider_error
from .cli_provider_protocol import BaseProvider

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# F-051: Codex-specific error config — declarative, not procedural
# ---------------------------------------------------------------------------


def _codex_json_extractor(data: dict) -> Optional[str]:
    """Extract error summary from Codex's JSON error structure.

    Codex errors have: {"error": str|dict, "message": str} at top level.
    """
    err_msg = data.get("error") or data.get("message") or ""
    if isinstance(err_msg, str) and err_msg:
        return f"CODEX_ERROR — {err_msg[:120]}"
    if isinstance(err_msg, dict):
        return f"CODEX_ERROR — {err_msg.get('message', '')[:120]}"
    return None


_CODEX_ERROR_CONFIG = ProviderErrorConfig(
    prefix="CODEX_ERROR",
    json_extractor=_codex_json_extractor,
    regex_patterns=[
        # Pattern: "capacity exhausted", "rate limit", "overloaded" in raw text
        (
            re.compile(r'(capacity\s+exhausted|rate\s*limit|overloaded)', re.IGNORECASE),
            lambda m: f"CODEX_ERROR — {m.group(1)}",
        ),
    ],
)


class CodexProvider(BaseProvider):
    """OpenAI Codex CLI provider."""

    def build_command(self, prompt: str, use_resume: bool = False) -> List[str]:
        cmd = ["codex", "exec"]
        if use_resume:
            cmd.extend(["resume", "--last"])
        cmd.append("--json")
        # Backlog #327: codex refuses to run when project_dir is not a git repo
        # ("Not inside a trusted directory and --skip-git-repo-check was not
        # specified."). Daemons often boot under /tmp/* test dirs that aren't
        # repos. The flag is a no-op inside a real repo, so always pass it.
        cmd.append("--skip-git-repo-check")
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

        F-051: Delegates to shared classify_provider_error() with Codex-specific
        config (JSON extractor for error/message fields, regex fallback for
        capacity/rate-limit patterns). Falls back to generic extract_error_summary.
        """
        return classify_provider_error(line, _CODEX_ERROR_CONFIG)

    # _append_error_log inherited from BaseProvider
