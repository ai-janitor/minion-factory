"""Centralized prompt assembly for minion agents."""

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
