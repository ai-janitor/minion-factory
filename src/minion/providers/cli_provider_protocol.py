"""Cli Provider Protocol.

Purpose: Cli Provider Protocol module.
Rationale: Extracted into own module for single-responsibility provider configuration.
Responsibility: Cli Provider Protocol. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional


class BaseProvider(ABC):
    """Common interface for all agent CLI providers (claude, gemini, codex, opencode)."""

    def __init__(self, agent_name: str, agent_cfg, use_poll: bool) -> None:
        self.agent_name = agent_name
        self.agent_cfg = agent_cfg
        self.use_poll = use_poll
        self.session_id: str | None = None

    @abstractmethod
    def build_command(self, prompt: str, use_resume: bool = False) -> List[str]:
        ...

    @abstractmethod
    def prompt_guardrails(self) -> str:
        ...

    def _classify_error(self, line: str) -> Optional[str]:
        """Classify a verbose error line into a short summary.

        Override in subclasses to add provider-specific error patterns (JSON
        structure, status codes, etc.). Return None if the line is not a
        recognized error. Falls back to _extract_error_summary for generic
        large-output detection.

        This is the provider-specific hook called by filter_log_line.
        """
        return self._extract_error_summary(line)

    def filter_log_line(self, line: str, error_log: Path) -> str:
        """Parse raw output line, return cleaned version for tmux pane.

        Shared structure: if line is long, classify the error, log it, and
        return a short summary. Subclasses override _classify_error for
        provider-specific patterns — not this method.
        """
        stripped = line.rstrip("\n")
        if not stripped or len(stripped) <= 500:
            return line

        summary = self._classify_error(stripped)
        if summary:
            self._append_error_log(error_log, stripped)
            return f"[{self.agent_name}] {summary}. Full error: {error_log}\n"
        return line

    @property
    def supports_resume(self) -> bool:
        return True

    @property
    def resume_label(self) -> str:
        return ""

    # shared helpers

    @staticmethod
    def _append_error_log(error_log: Path, content: str) -> None:
        """Append a timestamped error entry to the provider error log file.

        Shared by all providers that override filter_log_line to capture verbose
        errors. Extracted here to avoid duplication across codex.py and gemini.py.
        """
        from datetime import datetime
        try:
            error_log.parent.mkdir(parents=True, exist_ok=True)
            with open(error_log, "a") as f:
                f.write(f"\n--- {datetime.now().isoformat()} ---\n")
                f.write(content)
                f.write("\n")
        except OSError as exc:
            import sys
            print(f"WARNING: failed to write error log {error_log}: {exc}", file=sys.stderr)

    @staticmethod
    def _extract_error_summary(line: str, max_normal: int = 500) -> Optional[str]:
        """If line exceeds max_normal chars, try to extract a short error summary."""
        if len(line) <= max_normal:
            return None
        # Try JSON error extraction
        try:
            import json
            data = json.loads(line)
            if isinstance(data, dict):
                code = data.get("error", {}).get("code") or data.get("code") or data.get("status")
                msg = data.get("error", {}).get("message") or data.get("message") or ""
                if code or msg:
                    return f"{code or 'ERROR'}: {msg[:120]}"
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        # Try HTTP status code pattern
        m = re.search(r'\b([45]\d{2})\b', line[:200])
        if m:
            return f"HTTP {m.group(1)} (response truncated, {len(line)} chars)"
        return f"Large output ({len(line)} chars)"
