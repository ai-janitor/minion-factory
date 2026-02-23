"""Class-based authorization, constants, and gate functions."""

from __future__ import annotations

import os
import sys
from typing import Callable, TypeVar

import click

# ---------------------------------------------------------------------------
# Agent classes — loaded from task-flows/agent-classes.yaml
# Lazy-loaded to avoid circular imports (auth ↔ tasks ↔ comms ↔ auth)
# ---------------------------------------------------------------------------

def _agent_classes():
    from minion.tasks.agent_classes import (
        get_valid_classes,
        get_valid_capabilities,
        get_class_capabilities,
        get_class_models,
    )
    return get_valid_classes, get_valid_capabilities, get_class_capabilities, get_class_models


def _load_valid_classes() -> set[str]:
    return _agent_classes()[0]()


def _load_class_capabilities() -> dict[str, set[str]]:
    return _agent_classes()[2]()


def _load_class_models() -> dict[str, set[str]]:
    return _agent_classes()[3]()


# Hardcoded fallback — kept in sync with agent-classes.yaml
# Used at module level by TOOL_CATALOG before lazy load fires
VALID_CLASSES: set[str] = {"lead", "coder", "builder", "oracle", "recon", "planner", "auditor"}
VALID_CAPABILITIES: set[str] = set()
CLASS_CAPABILITIES: dict[str, set[str]] = {}
CLASS_MODEL_WHITELIST: dict[str, set[str]] = {}

# Capability constants kept as string aliases for existing code
CAP_MANAGE = "manage"
CAP_CODE = "code"
CAP_BUILD = "build"
CAP_REVIEW = "review"
CAP_TEST = "test"
CAP_INVESTIGATE = "investigate"
CAP_PLAN = "plan"
CAP_MONITOR = "monitor"
CAP_MEMORY = "memory"
CAP_ENGINEER = "engineer"


_REGISTRY_LOADED = False

def _ensure_loaded() -> None:
    """Populate module-level dicts from YAML on first use."""
    global VALID_CLASSES, VALID_CAPABILITIES, CLASS_CAPABILITIES, CLASS_MODEL_WHITELIST, _REGISTRY_LOADED
    if _REGISTRY_LOADED:
        return
    fns = _agent_classes()
    VALID_CLASSES = fns[0]()
    VALID_CAPABILITIES = fns[1]()
    CLASS_CAPABILITIES = fns[2]()
    CLASS_MODEL_WHITELIST = fns[3]()
    _REGISTRY_LOADED = True


def classes_with(capability: str) -> set[str]:
    """Return all classes that have a given capability."""
    _ensure_loaded()
    if capability not in VALID_CAPABILITIES:
        raise ValueError(f"Unknown capability {capability!r}. Valid: {sorted(VALID_CAPABILITIES)}")
    return {cls for cls, caps in CLASS_CAPABILITIES.items() if capability in caps}

# ---------------------------------------------------------------------------
# Staleness thresholds (seconds) — enforced on send()
# ---------------------------------------------------------------------------

CLASS_STALENESS_SECONDS: dict[str, int] = {
    "coder": 5 * 60,
    "builder": 5 * 60,
    "recon": 5 * 60,
    "lead": 15 * 60,
    "oracle": 30 * 60,
    "planner": 15 * 60,
    "auditor": 5 * 60,
}

# ---------------------------------------------------------------------------
# Battle plan / task / raid log enums
# ---------------------------------------------------------------------------

BATTLE_PLAN_STATUSES = {"active", "superseded", "completed", "abandoned", "obsolete"}

RAID_LOG_PRIORITIES = {"low", "normal", "high", "critical"}

TASK_STATUSES = {
    "open", "assigned", "in_progress", "fixed", "verified",
    "closed", "abandoned", "stale", "obsolete",
}
# VALID_TRANSITIONS removed — all transition logic lives in DAG YAML flows

# ---------------------------------------------------------------------------
# Trigger words (brevity codes)
# ---------------------------------------------------------------------------

TRIGGER_WORDS: dict[str, str] = {
    "fenix_down": "Dump all knowledge to disk before context death. Revival protocol.",
    "moon_crash": "Emergency shutdown. Everyone fenix_down NOW. No new task assignments.",
    "halt": "Finish current work, save state (fenix_down), stand down. Graceful pause — not an emergency. You will be resumed later.",
    "sitrep": "Request status report from target agent.",
    "rally": "All agents focus on the specified target/zone.",
    "retreat": "Pull back from current approach, reassess.",
    "hot_zone": "Area is dangerous/complex, proceed with caution.",
    "stand_down": "Stop work, prepare to deregister.",
    "recon": "Investigate before acting. Gather intel first.",
}

# ---------------------------------------------------------------------------
# Briefing files per class (cold_start onboarding)
# ---------------------------------------------------------------------------

CLASS_BRIEFING_FILES: dict[str, list[str]] = {
    "lead": [".work/CODE_MAP.md", ".work/CODE_OWNERS.md", ".work/traps/"],
    "coder": [".work/CODE_MAP.md", ".work/traps/"],
    "builder": [".work/CODE_MAP.md", ".work/traps/"],
    "oracle": [".work/CODE_MAP.md", ".work/CODE_OWNERS.md", ".work/intel/", ".work/traps/"],
    "recon": [".work/CODE_MAP.md", ".work/intel/", ".work/traps/"],
    "planner": [".work/CODE_MAP.md", ".work/CODE_OWNERS.md", ".work/traps/"],
    "auditor": [".work/CODE_MAP.md", ".work/traps/"],
}

# ---------------------------------------------------------------------------
# Tool catalog — command → (allowed_classes, description)
# ---------------------------------------------------------------------------

TOOL_CATALOG: dict[str, tuple[set[str], str]] = {
    "register":              (VALID_CLASSES, "Register an agent into the session"),
    "deregister":            (VALID_CLASSES, "Remove an agent from the registry"),
    "rename":                ({"lead"}, "Rename an agent (zone reassignment)"),
    "set-status":            (VALID_CLASSES, "Set your current status text"),
    "set-context":           (VALID_CLASSES, "Update context summary and HP metrics"),
    "who":                   (VALID_CLASSES, "List all registered agents"),
    "send":                  (VALID_CLASSES, "Send a message to an agent or broadcast"),
    "check-inbox":           (VALID_CLASSES, "Check and clear unread messages"),
    "list-history":          (VALID_CLASSES, "Return last N messages across all agents"),
    "purge-inbox":           (VALID_CLASSES, "Delete old messages from inbox"),
    "set-battle-plan":       ({"lead"}, "Set the active battle plan for the session"),
    "get-battle-plan":       (VALID_CLASSES, "Get battle plan by status"),
    "update-battle-plan-status": ({"lead"}, "Update a battle plan's status"),
    "log-raid":              (VALID_CLASSES, "Append an entry to the raid log"),
    "list-raid-log":         (VALID_CLASSES, "Read the raid log"),
    "task create":           ({"lead"}, "Create a new task with spec file"),
    "task assign":           ({"lead"}, "Assign a task to an agent"),
    "task update":           (VALID_CLASSES, "Update task status, progress, or files"),
    "task list":             (VALID_CLASSES, "List tasks with filters"),
    "task get":              (VALID_CLASSES, "Get full detail for a single task"),
    "task pull":             (VALID_CLASSES, "Claim a specific task by ID"),
    "task result":           (VALID_CLASSES, "Write a result file and submit it for a task"),
    "task review":           (VALID_CLASSES, "Write a review verdict and advance the task phase"),
    "task test":             (VALID_CLASSES, "Write a test report and advance the task phase"),
    "task block":            (VALID_CLASSES, "Block a task with a reason"),
    "task done":             (VALID_CLASSES, "Fast-close a task completed outside the DAG"),
    "task spec":             (VALID_CLASSES, "Read the spec file contents for a task"),
    "task define":           ({"lead"}, "Create a task spec file and task record in one command"),
    "task close":            ({"lead"}, "Close a completed task"),
    "claim-file":            ({"coder", "builder", "planner"}, "Claim a file for exclusive editing"),
    "release-file":          ({"coder", "builder", "planner"}, "Release a file claim"),
    "list-claims":           (VALID_CLASSES, "List active file claims"),
    "party-status":          ({"lead"}, "Full raid health dashboard"),
    "check-activity":        (VALID_CLASSES, "Check an agent's activity level"),
    "check-freshness":       ({"lead"}, "Check file freshness vs agent's last context"),
    "sitrep":                (VALID_CLASSES, "Fused COP: agents + tasks + claims + flags"),
    "update-hp":             ({"lead"}, "Daemon-only: write observed HP to SQLite"),
    "cold-start":            (VALID_CLASSES, "Bootstrap into a session, get onboarding"),
    "fenix-down":            (VALID_CLASSES, "Dump session knowledge before context death"),
    "debrief":               ({"lead"}, "File a session debrief"),
    "end-session":           ({"lead"}, "End the current session"),
    "list-triggers":         (VALID_CLASSES, "Return the trigger word codebook"),
    "clear-moon-crash":      ({"lead"}, "Clear emergency flag, resume assignments"),
    "list-crews":            ({"lead"}, "List available crew YAML files"),
    "spawn-party":           (VALID_CLASSES, "Spawn daemon workers in tmux panes (auto-registers lead)"),
    "halt":                  ({"lead"}, "Graceful pause — agents finish work, fenix_down, stand down"),
    "stand-down":            ({"lead"}, "Dismiss the party"),
    "retire-agent":          ({"lead"}, "Signal a single daemon to exit gracefully"),
    "recruit":               ({"lead"}, "Add an ad-hoc agent into a running crew"),
    "interrupt":             ({"lead"}, "Interrupt an agent's current invocation"),
    "resume":                ({"lead"}, "Send a resume message to an interrupted agent"),
    "hand-off-zone":         (VALID_CLASSES, "Direct zone handoff between agents"),
    "tools":                 (VALID_CLASSES, "List available tools for your class"),
    "task lineage":          (VALID_CLASSES, "Show task DAG history and who worked each stage"),
    "task reopen":           ({"lead"}, "Reopen a terminal task back to an earlier phase"),
    "task complete-phase":   (VALID_CLASSES, "Complete your phase — DAG routes to next stage"),
    "req create":            ({"lead", "planner"}, "Create a requirement folder with README and register it"),
    "req decompose":         ({"lead", "planner"}, "Decompose a requirement into children from a spec file"),
    "req itemize":           ({"lead", "planner"}, "Write itemized-requirements.md from a spec file"),
    "req findings":          (VALID_CLASSES, "Write findings.md from a spec file"),
    "poll":                  (VALID_CLASSES, "Poll for messages and tasks (replaces poll.sh)"),
    "list-flows":            (VALID_CLASSES, "List available task flow types"),
    "mission list":          (VALID_CLASSES, "List available mission templates"),
    "mission suggest":       ({"lead"}, "Show resolved slots and eligible characters for a mission"),
    "mission spawn":         ({"lead"}, "Resolve mission, draft party, and spawn"),
}


def get_tools_for_class(agent_class: str) -> list[dict[str, str]]:
    """Return tools available to a given class."""
    result = []
    for cmd, (classes, desc) in sorted(TOOL_CATALOG.items()):
        if agent_class in classes:
            result.append({"command": f"minion {cmd}", "description": desc})
    return result


# ---------------------------------------------------------------------------
# Authorization helpers
# ---------------------------------------------------------------------------

def get_agent_class() -> str:
    """Read MINION_CLASS from env, default to 'lead'."""
    return os.environ.get("MINION_CLASS", "lead")


F = TypeVar("F", bound=Callable[..., object])


def require_class(*allowed: str) -> Callable[[F], F]:
    """Decorator that gates a CLI command to specific agent classes.

    Checks MINION_CLASS env var. If the caller's class is not in *allowed*,
    prints an error and exits 1.
    """
    def decorator(func: F) -> F:
        import functools

        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> object:
            cls = get_agent_class()
            if cls not in allowed:
                click.echo(
                    f"BLOCKED: Class '{cls}' cannot run this command. "
                    f"Requires: {', '.join(sorted(allowed))}",
                    err=True,
                )
                sys.exit(1)
            return func(*args, **kwargs)
        return wrapper  # type: ignore[return-value]
    return decorator
