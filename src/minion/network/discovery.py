"""Project discovery from network DB agent project_paths.

Purpose: Discover all projects that have registered agents on the network,
         providing the bridge between the network coordinator DB and per-project
         .work/minion.db files.
Rationale: The network DB's agents table stores project_path for each agent.
           Multiple agents may share the same project_path. This module deduplicates
           and provides project name resolution (last path component).
Responsibility: Query distinct project_paths from network DB, resolve project names,
                verify DB existence.
Organization: Standalone functions — no class needed for this simple lookup.

Implementation order: 2nd (after db_schema, alongside project_db — no mutual dependency).
"""

from __future__ import annotations

import os
import threading

from minion.db.connection import connect


def discover_projects(db_path: str, db_lock: threading.Lock | None = None) -> list[dict]:
    """Discover all projects from registered agent project_paths.

    Queries the network coordinator DB for distinct project_paths, deduplicates,
    and returns project metadata.

    Args:
        db_path: Path to the network coordinator SQLite DB (~/.minion/network.db).
        db_lock: Optional lock for DB access (the server's _DB_LOCK).

    Returns:
        List of dicts: [{"name": "minion-factory", "path": "/Users/.../minion-factory",
                         "has_db": True, "agent_count": 3}, ...]
    """
    # PSEUDO: SELECT project_path, COUNT(*) FROM agents WHERE project_path IS NOT NULL GROUP BY project_path
    # PSEUDO: for each row: name = basename(path), has_db = exists(.work/minion.db)
    # PSEUDO: return list of {name, path, has_db, agent_count}
    def _query():
        conn = connect(db_path)
        rows = conn.execute(
            "SELECT project_path, COUNT(*) as agent_count "
            "FROM agents WHERE project_path IS NOT NULL "
            "GROUP BY project_path"
        ).fetchall()
        conn.close()
        return rows

    if db_lock:
        with db_lock:
            rows = _query()
    else:
        rows = _query()

    projects = []
    for row in rows:
        path = row["project_path"]
        name = os.path.basename(path.rstrip("/"))
        has_db = os.path.exists(os.path.join(path, ".work", "minion.db"))
        projects.append({
            "name": name,
            "path": path,
            "has_db": has_db,
            "agent_count": row["agent_count"],
        })
    return projects


def resolve_project_path(db_path: str, project_name: str,
                         db_lock: threading.Lock | None = None) -> str | None:
    """Resolve a project name to its absolute path.

    Project name is the last component of project_path (e.g., "minion-factory"
    from "/Users/hung/projects/minion-factory").

    Returns None if no project matches or if the name is ambiguous
    (multiple projects with the same basename from different paths).

    Args:
        db_path: Path to network coordinator DB.
        project_name: Short project name (basename of project_path).
        db_lock: Optional lock for DB access.

    Returns:
        Absolute project_path string, or None if not found/ambiguous.
    """
    # PSEUDO: discover all projects, filter by name, return path if unique match
    projects = discover_projects(db_path, db_lock)
    matches = [p for p in projects if p["name"] == project_name]
    if len(matches) == 1:
        return matches[0]["path"]
    return None
