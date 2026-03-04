"""Fully Qualified Name resolution for network agents.

Purpose: Resolve agent references (short name or full path) to specific agents
         in the network coordinator DB using composite key (machine_id, project_path, name).
Rationale: With composite PK, agents can share the same short name across different
           machines/projects. This module provides 3-tier resolution so callers can
           use either full FQN paths or short names with intelligent disambiguation.
Responsibility: Parse FQN strings, query network DB for matches, return unique match
                or error with all candidates for ambiguous lookups.
Organization: Standalone functions — build_fqn() for display, resolve_agent() for lookup.

Resolution tiers (for short names):
  1. Same machine_id + same project_path as sender → exact match
  2. Same machine_id, any project_path → if unique, use it; if ambiguous, error
  3. Any machine_id → if unique globally, use it; if ambiguous, error with suggestions

Implementation order: 2nd (after db_schema, before handler updates).
"""

from __future__ import annotations

import os
import sqlite3
import threading


def build_fqn(machine_id: str, project_path: str, name: str) -> str:
    """Build a fully qualified name: machine_id/project_basename/name.

    Args:
        machine_id: Machine identifier (hostname or 'unknown').
        project_path: Full project path or 'unknown'.
        name: Agent short name.

    Returns:
        FQN string like 'macbook/minion-factory/cloud'.
    """
    # PSEUDO: basename = os.path.basename(project_path.rstrip("/")) or "unknown"
    # PSEUDO: return f"{machine_id}/{basename}/{name}"
    pp = project_path or "unknown"
    basename = os.path.basename(pp.rstrip("/")) if pp != "unknown" else "unknown"
    mid = machine_id or "unknown"
    return f"{mid}/{basename}/{name}"


def parse_fqn(fqn: str) -> tuple[str, str, str] | None:
    """Parse a full FQN string into (machine_id, project_basename, name).

    Returns None if the string is not a valid FQN (doesn't contain '/').
    Note: project_basename is the short name — the full project_path must
    be resolved from the DB.

    Args:
        fqn: String like 'macbook/minion-factory/cloud'.

    Returns:
        Tuple of (machine_id, project_basename, name) or None if not a FQN.
    """
    # PSEUDO: if "/" not in fqn: return None (it's a short name)
    # PSEUDO: parts = fqn.split("/")
    # PSEUDO: if len(parts) != 3: return None (malformed)
    # PSEUDO: return (parts[0], parts[1], parts[2])
    if "/" not in fqn:
        return None
    parts = fqn.split("/")
    if len(parts) != 3:
        return None
    return (parts[0], parts[1], parts[2])


def resolve_agent(
    db_path: str,
    agent_ref: str,
    sender_machine_id: str | None = None,
    sender_project_path: str | None = None,
    db_lock: threading.Lock | None = None,
) -> dict:
    """Resolve an agent reference to a unique agent in the network DB.

    Accepts either:
    - Full FQN path: 'macbook/minion-factory/cloud' → exact match
    - Short name: 'cloud' → 3-tier resolution

    Args:
        db_path: Path to network coordinator DB.
        agent_ref: Agent name or FQN string.
        sender_machine_id: Sender's machine_id for tier-1/2 resolution.
        sender_project_path: Sender's project_path for tier-1 resolution.
        db_lock: Optional threading lock for DB access.

    Returns:
        Dict with either:
        - {"status": "resolved", "name": str, "machine_id": str, "project_path": str, "fqn": str}
        - {"status": "not_found", "error": str}
        - {"status": "ambiguous", "error": str, "matches": list[dict]}
    """
    # PSEUDO: parsed = parse_fqn(agent_ref)
    # PSEUDO: if parsed: do exact FQN match
    # PSEUDO: else: do 3-tier short name resolution
    parsed = parse_fqn(agent_ref)

    def _query(sql, params):
        if db_lock:
            with db_lock:
                return _execute(db_path, sql, params)
        return _execute(db_path, sql, params)

    if parsed:
        # Full FQN match — exact lookup
        # PSEUDO: SELECT WHERE machine_id = ? AND project_path LIKE '%/project_basename' AND name = ?
        machine_id, project_basename, name = parsed
        rows = _query(
            "SELECT name, machine_id, project_path FROM agents "
            "WHERE machine_id = ? AND name = ?",
            (machine_id, name),
        )
        # Filter by project_basename
        matches = [r for r in rows if os.path.basename(r["project_path"].rstrip("/")) == project_basename]
        if len(matches) == 1:
            m = matches[0]
            return {
                "status": "resolved",
                "name": m["name"],
                "machine_id": m["machine_id"],
                "project_path": m["project_path"],
                "fqn": build_fqn(m["machine_id"], m["project_path"], m["name"]),
            }
        if not matches:
            return {"status": "not_found", "error": f"No agent matching FQN '{agent_ref}'"}
        return _ambiguous_error(agent_ref, matches)

    # Short name — 3-tier resolution
    name = agent_ref

    # Tier 1: same machine_id + same project_path
    if sender_machine_id and sender_project_path:
        rows = _query(
            "SELECT name, machine_id, project_path FROM agents "
            "WHERE name = ? AND machine_id = ? AND project_path = ?",
            (name, sender_machine_id, sender_project_path),
        )
        if len(rows) == 1:
            m = rows[0]
            return {
                "status": "resolved",
                "name": m["name"],
                "machine_id": m["machine_id"],
                "project_path": m["project_path"],
                "fqn": build_fqn(m["machine_id"], m["project_path"], m["name"]),
            }

    # Tier 2: same machine_id, any project_path
    if sender_machine_id:
        rows = _query(
            "SELECT name, machine_id, project_path FROM agents "
            "WHERE name = ? AND machine_id = ?",
            (name, sender_machine_id),
        )
        if len(rows) == 1:
            m = rows[0]
            return {
                "status": "resolved",
                "name": m["name"],
                "machine_id": m["machine_id"],
                "project_path": m["project_path"],
                "fqn": build_fqn(m["machine_id"], m["project_path"], m["name"]),
            }
        if len(rows) > 1:
            return _ambiguous_error(name, rows)

    # Tier 3: global — any machine_id
    rows = _query(
        "SELECT name, machine_id, project_path FROM agents WHERE name = ?",
        (name,),
    )
    if len(rows) == 1:
        m = rows[0]
        return {
            "status": "resolved",
            "name": m["name"],
            "machine_id": m["machine_id"],
            "project_path": m["project_path"],
            "fqn": build_fqn(m["machine_id"], m["project_path"], m["name"]),
        }
    if len(rows) > 1:
        return _ambiguous_error(name, rows)

    return {"status": "not_found", "error": f"Agent '{name}' not registered on network"}


def _execute(db_path: str, sql: str, params: tuple) -> list[dict]:
    """Execute a query and return list of dicts."""
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


def _ambiguous_error(ref: str, matches: list[dict]) -> dict:
    """Build an ambiguous resolution error with match suggestions."""
    # PSEUDO: build list of FQNs from matches for user disambiguation
    suggestions = [
        build_fqn(m["machine_id"], m["project_path"], m["name"])
        for m in matches
    ]
    return {
        "status": "ambiguous",
        "error": f"Agent '{ref}' is ambiguous — {len(matches)} matches. Use full FQN.",
        "matches": suggestions,
    }
