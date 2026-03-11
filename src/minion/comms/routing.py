"""Global agent routing — who_global, deregister_global, prune_global.
Manages agent presence and cleanup in the coordinator DB (cross-repo registry).
Includes task-protection logic to prevent pruning agents with active work.

Purpose: Global agent routing — who_global, deregister_global, prune_global.
Rationale: Extracted into own module for single-responsibility agent communication.
Responsibility: Global agent routing — who_global, deregister_global, prune_global. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import datetime
import os
import sqlite3

from minion.db import connect, get_coordinator_db


def who_global() -> dict[str, object]:
    """List all agents across all projects from the coordinator DB.

    Big-O: O(A * log(A)) where A = total agents across all projects (full table scan + ORDER BY).
    Space: O(A) for the result list. Typically A < 100.
    """
    try:
        coord = get_coordinator_db()
        try:
            rows = coord.execute("SELECT * FROM agents ORDER BY last_active DESC, last_seen DESC").fetchall()
            agents = [dict(row) for row in rows]
            return {"agents": agents, "source": "coordinator"}
        finally:
            coord.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError) as exc:
        return {"error": f"Coordinator DB not available: {exc}"}


def _remove_roster_file(agent_name: str, project_path: str) -> None:
    """Remove an agent's roster file from a project's .work/.minion-agents/."""
    roster_file = os.path.join(project_path, ".work", ".minion-agents", agent_name)
    if os.path.exists(roster_file):
        os.remove(roster_file)


def deregister_global(agent_name: str) -> dict[str, object]:
    """Remove an agent from the coordinator DB. Lead-only."""
    # Precondition assertions — backlog #63
    assert agent_name, "agent_name must not be empty"

    try:
        coord = get_coordinator_db()
        try:
            row = coord.execute(
                "SELECT name, project_path, last_active FROM agents WHERE name = ?",
                (agent_name,),
            ).fetchone()
            if not row:
                return {"error": f"Agent '{agent_name}' not found in coordinator DB."}
            info = dict(row)
            coord.execute("DELETE FROM agents WHERE name = ?", (agent_name,))
            coord.commit()
            _remove_roster_file(agent_name, info["project_path"])
            return {
                "status": "deregistered",
                "agent": agent_name,
                "was_in_project": info["project_path"],
                "last_active": info.get("last_active") or "never",
            }
        finally:
            coord.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError) as exc:
        return {"error": f"Coordinator DB error: {exc}"}


def _agent_has_active_tasks(agent_name: str, project_path: str) -> bool:
    """Check if an agent has open/assigned/in_progress tasks in their project's local DB."""
    local_db = os.path.join(project_path, ".work", "minion.db")
    if not os.path.exists(local_db):
        return False
    try:
        conn = connect(local_db, timeout=2)
        row = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status IN ('open', 'assigned', 'in_progress', 'fixed')",
            (agent_name,),
        ).fetchone()
        conn.close()
        return row[0] > 0
    except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError):
        return False


def prune_global(stale_minutes: int = 30) -> dict[str, object]:
    """Remove agents from coordinator DB that haven't been active in N minutes.

    Agents with active tasks (open/assigned/in_progress/fixed) in their project
    are protected from pruning regardless of staleness.

    Big-O: O(S * T) where S = stale agent candidates, T = task count per agent's project DB.
    For each candidate, opens remote DB and runs COUNT query. DELETE is O(S) batch.
    Filesystem cleanup O(S) for roster file removal. Typically S < 10.
    """
    # Precondition assertions — backlog #63
    if not isinstance(stale_minutes, int):
        raise TypeError(f"stale_minutes must be int, got {type(stale_minutes).__name__}")
    if stale_minutes < 1:
        raise ValueError(f"stale_minutes must be >= 1, got {stale_minutes}")

    cutoff = (datetime.datetime.now() - datetime.timedelta(minutes=stale_minutes)).isoformat()
    try:
        coord = get_coordinator_db()
        try:
            # Find stale agents: last_active older than cutoff, or NULL last_active
            rows = coord.execute(
                "SELECT name, project_path, last_active FROM agents WHERE last_active IS NULL OR last_active < ?",
                (cutoff,),
            ).fetchall()
            candidates = [dict(r) for r in rows]
            if not candidates:
                return {"status": "no stale agents", "threshold_minutes": stale_minutes}

            # Protect agents with active tasks
            stale = []
            protected = []
            for agent in candidates:
                if _agent_has_active_tasks(agent["name"], agent.get("project_path", "")):
                    protected.append(agent["name"])
                else:
                    stale.append(agent)

            if not stale:
                result: dict[str, object] = {"status": "no stale agents", "threshold_minutes": stale_minutes}
                if protected:
                    result["protected"] = protected
                return result

            names = [a["name"] for a in stale]
            coord.execute(
                f"DELETE FROM agents WHERE name IN ({','.join('?' * len(names))})",
                names,
            )
            coord.commit()
            # Clean up roster files in each pruned agent's project
            for agent in stale:
                _remove_roster_file(agent["name"], agent["project_path"])
            result = {
                "status": "pruned",
                "threshold_minutes": stale_minutes,
                "removed": stale,
            }
            if protected:
                result["protected"] = protected
            return result
        finally:
            coord.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError, OSError) as exc:
        return {"error": f"Coordinator DB error: {exc}"}
