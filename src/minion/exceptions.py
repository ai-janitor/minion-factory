"""Exception hierarchy and Result TypedDict — minion error convention.

Purpose: Provide a shared exception base class and document the two-track
         error strategy used throughout minion-factory.
Rationale: Before this module, code used both `raise ValueError(...)` and
           `return {"error": "..."}` with no convention. Two patterns for
           two contexts: exceptions for internal library code, dicts at the
           CLI boundary where JSON output is required.
Responsibility: Define MinionError and subclasses, define Result TypedDict,
                document when to use each pattern.
Organization: Exceptions first (MinionError base → subclasses), then Result TypedDict.

Convention — when to raise vs when to return a dict:
  RAISE MinionError (or subclass) when:
    - You are internal library code (tasks/, db/, comms/, crew/, etc.)
    - The caller is another Python module, not the CLI
    - The error is unrecoverable at that layer
    - Examples: DB constraint violation, missing required arg, permission denied

  RETURN {"status": "error", "message": "..."} (Result dict) when:
    - You are at the CLI boundary (cli/*_cmds.py, top-level Click handlers)
    - The output is consumed by minion output() → JSON / human / compact
    - You want the error to appear in structured CLI output, not a traceback
    - Examples: agent not found, task already closed, invalid status transition

  Rule of thumb: if the function is called from a Click command, return a dict.
                 If called from another library function, raise.
"""

from __future__ import annotations

from typing import Any, TypedDict


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class MinionError(Exception):
    """Base class for all minion-factory exceptions.

    Catch this to handle any minion-specific error without importing subclasses.
    All subclasses should carry a human-readable message as their first arg.
    """


class MinionNotFoundError(MinionError):
    """Resource not found — agent, task, backlog item, DB row, file.

    Raise when a lookup returns nothing and the caller cannot proceed.
    Example: agent 'leo' not in registry, task #99 does not exist.
    """


class MinionPermissionError(MinionError):
    """Auth / class restriction violation.

    Raise when an agent's class does not have permission to run a command.
    Example: coder tries to run a lead-only command.
    """


class MinionConfigError(MinionError):
    """Bad configuration — missing env var, invalid path, malformed YAML.

    Raise during startup/config parsing when a required value is absent
    or unparseable and execution cannot continue.
    """


class MinionStateError(MinionError):
    """Invalid state transition — DAG violation, wrong task status, etc.

    Raise when an operation is rejected because the current state does not
    allow it. Example: trying to close a task that is already closed.
    """


class MinionDBError(MinionError):
    """Database operation failed in a way the caller must handle.

    Wraps sqlite3 errors that propagate up past the DB layer.
    Internal DB helpers should catch sqlite3.Error and re-raise as MinionDBError
    when the caller needs to distinguish DB failures from other errors.
    """


# ---------------------------------------------------------------------------
# Result TypedDict — for dict-return pattern at CLI boundary
# ---------------------------------------------------------------------------

class Result(TypedDict, total=False):
    """Structured return type for CLI-boundary functions.

    Functions that return dicts for JSON output should type their return
    as Result or dict[str, Any]. The "status" key is always present:
      - "ok" / "success" / operation-specific strings → success path
      - "error" → failure path (triggers sys.exit(1) in output())

    The "message" key carries the human-readable summary.
    All other keys are operation-specific.

    Example:
        def register_agent(name: str) -> Result:
            if already_exists:
                return {"status": "error", "message": f"Agent {name} already registered"}
            ...
            return {"status": "registered", "agent": name}
    """
    status: str
    message: str
    error: str
    agent: str
    task_id: int
    data: Any
