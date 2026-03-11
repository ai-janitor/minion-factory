"""Cli Provider Protocol.

Purpose: Cli Provider Protocol module.
Rationale: Extracted into own module for single-responsibility provider configuration.
Responsibility: Cli Provider Protocol. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source.

SU-14: Shared error handling delegated to _shared_error_log and _shared_error_classifier.
BaseProvider methods are thin wrappers for backward compatibility.

ASSUMPTIONS:
- Subclasses MUST implement build_command() and prompt_guardrails(). These are the
  only two abstract methods. All other methods have default implementations.
- filter_log_line() assumes lines longer than 500 chars are likely error output
  (JSON blobs, stack traces). Lines <= 500 chars pass through unmodified. If a
  provider produces long non-error output (e.g., base64 data), it will be
  misclassified as an error and logged to the error file.
- error_log Path passed to filter_log_line() must be writable. If the path's parent
  directory doesn't exist, _append_error_log will create it. But if the path is on a
  read-only filesystem, errors are silently lost (no exception raised).
- session_id is set externally after construction (by the daemon runner). Providers
  that support --resume use this to continue existing sessions. If session_id is None,
  resume is skipped — a new session starts. Stale session_id values (from a crashed
  session) may cause the provider CLI to error; the daemon handles this by retrying
  without resume.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from ._shared_error_classifier import extract_error_summary
from ._shared_error_log import append_error_log


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

    # shared helpers — SU-14: delegate to standalone modules for reusability

    @staticmethod
    def _append_error_log(error_log: Path, content: str) -> None:
        """Append a timestamped error entry to the provider error log file.

        SU-14: Delegates to _shared_error_log.append_error_log().
        Kept as static method for backward compatibility with subclasses.
        """
        append_error_log(error_log, content)

    @staticmethod
    def _extract_error_summary(line: str, max_normal: int = 500) -> Optional[str]:
        """If line exceeds max_normal chars, try to extract a short error summary.

        SU-14: Delegates to _shared_error_classifier.extract_error_summary().
        Kept as static method for backward compatibility with subclasses.
        """
        return extract_error_summary(line, max_normal)
