"""Module-level constants, helpers, and the AgentRunResult dataclass."""
from __future__ import annotations

import os
import platform
import resource
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

from ..contracts import load_contract


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_rss_bytes(pid: int | None = None) -> int:
    """RSS in bytes for a given PID. Falls back to self if pid is None or stale.

    macOS `ps -o rss=` returns KB. Linux `/proc/<pid>/statm` page 1 is pages.
    """
    target = pid or os.getpid()
    try:
        if platform.system() == "Linux":
            with open(f"/proc/{target}/statm") as f:
                pages = int(f.read().split()[1])
            return pages * resource.getpagesize()
        else:
            # macOS / BSD — ps returns KB
            result = subprocess.run(
                ["ps", "-o", "rss=", "-p", str(target)],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip()) * 1024
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    # Fallback: measure self (daemon)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Linux":
        rss *= 1024
    return rss


@dataclass
class AgentRunResult:
    exit_code: int
    timed_out: bool
    compaction_detected: bool
    command_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    interrupted: bool = False


# Load max_console_stream_chars from contract, fallback to 12k
_cfg_defaults = load_contract(
    os.getenv("MINION_DOCS_DIR", os.path.expanduser("~/.minion_work/docs")),
    "config-defaults",
)
MAX_CONSOLE_STREAM_CHARS = (_cfg_defaults or {}).get("max_console_stream_chars", 12_000)

# Claude Code system prompt + tool definitions token costs (approximate).
# Each tool's JSON schema + description consumes context tokens.
# These are injected by Claude Code before the agent's prompt.
CLAUDE_CODE_SYSTEM_TOKENS = 3_500   # Base system prompt (instructions, rules, formatting)
CLAUDE_CODE_TOOL_TOKENS: dict[str, int] = {
    "Bash":             400,
    "Read":             350,
    "Write":            250,
    "Edit":             400,
    "Glob":             200,
    "Grep":             500,
    "WebFetch":         300,
    "WebSearch":        250,
    "Task":             2_500,  # Largest — includes all agent type descriptions
    "NotebookEdit":     300,
    "AskUserQuestion":  500,
    "EnterPlanMode":    800,
    "ExitPlanMode":     300,
    "TaskCreate":       500,
    "TaskUpdate":       500,
    "TaskList":         300,
    "TaskGet":          200,
    "TeamCreate":       1_500,
    "TeamDelete":       100,
    "SendMessage":      800,
    "Skill":            300,
    "TaskOutput":       200,
    "TaskStop":         100,
}
# Total with all tools: ~3500 + ~10550 ≈ 14k. With MCP tools, add per-tool.
# Claude Code also injects CLAUDE.md, rules, MEMORY.md — varies per project.
CLAUDE_CODE_PROJECT_OVERHEAD = 4_000  # Rough estimate for CLAUDE.md + rules
