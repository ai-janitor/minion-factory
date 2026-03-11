"""Gemini.

Purpose: Gemini module.
Rationale: Extracted into own module for single-responsibility provider configuration.
Responsibility: Gemini. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source.
F-051: _classify_error delegates to shared classify_provider_error() with Gemini config.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from ._shared_error_classifier import ProviderErrorConfig, classify_provider_error
from .cli_provider_protocol import BaseProvider

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# F-051: Gemini-specific error config — declarative, not procedural
# ---------------------------------------------------------------------------


def _gemini_json_extractor(data: dict) -> Optional[str]:
    """Extract error summary from Gemini's JSON error structure.

    Gemini errors have: {"error": {"code": int, "status": str, "message": str}}
    """
    err = data.get("error", {})
    if isinstance(err, dict):
        code = err.get("code", "")
        status = err.get("status", "")
        msg = err.get("message", "")[:120]
        if code or status:
            return f"{status or 'ERROR'} ({code}) — {msg}"
    return None


_GEMINI_ERROR_CONFIG = ProviderErrorConfig(
    prefix="GEMINI",
    json_extractor=_gemini_json_extractor,
    regex_patterns=[
        # Pattern: "code": 429, "status": "RESOURCE_EXHAUSTED" in raw text
        (
            re.compile(r'"code"\s*:\s*(\d{3})'),
            lambda m: (
                f"{_extract_status_from_line(m.string) or 'ERROR'} ({m.group(1)})"
                f" — {_extract_msg_from_line(m.string)}"
            ),
        ),
    ],
)


def _extract_status_from_line(line: str) -> str:
    """Helper: extract "status" field value from raw text."""
    status_m = re.search(r'"status"\s*:\s*"([^"]+)"', line)
    return status_m.group(1) if status_m else ""


def _extract_msg_from_line(line: str) -> str:
    """Helper: extract "message" field value from raw text (up to 120 chars)."""
    msg_m = re.search(r'"message"\s*:\s*"([^"]{1,120})', line)
    return msg_m.group(1) if msg_m else ""


class GeminiProvider(BaseProvider):
    """Gemini CLI provider."""

    def build_command(self, prompt: str, use_resume: bool = False) -> List[str]:
        cmd = ["gemini", "--prompt", prompt, "--output-format", "stream-json"]
        if use_resume:
            cmd.extend(["--resume", "latest"])
        if self.agent_cfg.permission_mode:
            mode_map = {"bypassPermissions": "yolo", "acceptEdits": "auto_edit", "plan": "plan"}
            gemini_mode = mode_map.get(self.agent_cfg.permission_mode, self.agent_cfg.permission_mode)
            cmd.extend(["--approval-mode", gemini_mode])
        if self.agent_cfg.allowed_tools:
            for tool in self.agent_cfg.allowed_tools.replace(",", " ").split():
                cmd.extend(["--allowed-tools", tool])
        if self.agent_cfg.model:
            cmd.extend(["--model", self.agent_cfg.model])
        return cmd

    def prompt_guardrails(self) -> str:
        name = self.agent_name
        return "\n".join([
            f"CRITICAL IDENTITY: You are {name}. Not gemini-benchmarker, not any other name. You are {name}.",
            f"When running minion commands, always use --name {name} or --agent {name}. Never substitute another name.",
            "",
            "EXECUTION DISCIPLINE:",
            "- Run ONLY the commands listed. Do not explore, search, or investigate on your own.",
            "- After completing the listed commands, STOP. Do not look for tasks, read files, or take initiative.",
            "- Wait for messages to arrive via the daemon polling loop. You will be invoked again when there is work.",
            "- One response = one task. No chaining, no speculative exploration.",
        ])

    # filter_log_line inherited from BaseProvider — uses _classify_error hook

    @property
    def supports_resume(self) -> bool:
        return True

    @property
    def resume_label(self) -> str:
        return "gemini --resume latest"

    def _classify_error(self, line: str) -> Optional[str]:
        """Extract error code and short message from Gemini's verbose error output.

        F-051: Delegates to shared classify_provider_error() with Gemini-specific
        config (JSON extractor for error.code/status/message, regex fallback for
        raw text patterns). Falls back to generic extract_error_summary.
        """
        return classify_provider_error(line, _GEMINI_ERROR_CONFIG)

    # _append_error_log inherited from BaseProvider
