"""Centralized prompt assembly for minion agents.

Purpose: Centralized prompt assembly for minion agents.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Centralized prompt assembly for minion agents. NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic."""

from .boot_prompt import build_boot_prompt
from .inbox_prompt import build_inbox_prompt
from .system_prompt import build_system_prompt
from .terminal_prompt import build_terminal_prompt
from .watcher_prompt import build_watcher_prompt

__all__ = [
    "build_boot_prompt",
    "build_inbox_prompt",
    "build_system_prompt",
    "build_terminal_prompt",
    "build_watcher_prompt",
]
