"""Diagnostics endpoints — DB stats and system health for network API.

Purpose: Expose diagnostic information about the network coordinator and
         connected project DBs so leads can monitor system health.
Rationale: CLI parity — `minion db stats` provides DB diagnostics locally.
           Network API needs equivalent endpoints for remote monitoring.
           GET /alerts already exists in overview.py; this module adds
           GET /db/stats for DB-level diagnostics.
Responsibility: GET /db/stats — aggregate DB statistics across coordinator
                and all discovered project DBs.
Organization: Single handler that queries the coordinator DB and iterates
              discovered projects to collect table row counts and DB sizes.

Pseudo-logic:
  1. Query coordinator DB (network.db) for table row counts
  2. Discover all registered projects
  3. For each project DB, collect row counts and file size
  4. Return aggregated stats as JSON
"""

from __future__ import annotations

import os
import traceback


def register(router) -> None:
    """Register diagnostics endpoints with the router dispatch table."""
    router.add_get("/db/stats", handle_db_stats)


def handle_db_stats(handler, db_path: str, **kwargs) -> None:
    """GET /db/stats — aggregate DB statistics for coordinator and project DBs.

    Returns: {
        "coordinator": {
            "path": "/path/to/network.db",
            "size_bytes": 12345,
            "tables": {"agents": 5, "messages": 42}
        },
        "projects": [
            {
                "name": "minion-factory",
                "path": "/path/to/project",
                "db_size_bytes": 67890,
                "tables": {"agents": 3, "tasks": 15, "messages": 100, ...}
            }
        ]
    }

    Pseudo-logic:
      1. Get coordinator DB size and table counts
      2. Discover all registered projects
      3. For each project, get DB size and table counts from project DB
      4. Return aggregated results
    """
    try:
        from minion.network.server import _get_server_db, _DB_LOCK
        from minion.network.discovery import discover_projects
        from minion.network.project_db import get_project_db

        # PSEUDO: coordinator DB stats
        coordinator_stats = {"path": db_path, "size_bytes": 0, "tables": {}}
        try:
            coordinator_stats["size_bytes"] = os.path.getsize(db_path)
        except OSError:
            pass

        with _DB_LOCK:
            conn = _get_server_db(db_path)
            try:
                # PSEUDO: get all table names from sqlite_master
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
                for (table_name,) in tables:
                    try:
                        count = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]").fetchone()[0]
                        coordinator_stats["tables"][table_name] = count
                    except Exception:
                        coordinator_stats["tables"][table_name] = -1  # broad catch: table may not be queryable
            finally:
                conn.close()

        # PSEUDO: project DB stats
        project_stats = []
        projects = discover_projects(db_path, _DB_LOCK)
        for proj in projects:
            proj_info = {
                "name": proj["name"],
                "path": proj["path"],
                "db_size_bytes": 0,
                "tables": {},
            }
            # PSEUDO: find the project's .work/minion.db
            db_file = os.path.join(proj["path"], ".work", "minion.db")
            try:
                proj_info["db_size_bytes"] = os.path.getsize(db_file)
            except OSError:
                pass

            pconn = get_project_db(proj["path"])
            if pconn:
                try:
                    tables = pconn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                    for (table_name,) in tables:
                        try:
                            count = pconn.execute(f"SELECT COUNT(*) FROM [{table_name}]").fetchone()[0]
                            proj_info["tables"][table_name] = count
                        except Exception:
                            proj_info["tables"][table_name] = -1  # broad catch: table may not be queryable
                except Exception:
                    pass  # broad catch: project DB may be in unexpected state

            project_stats.append(proj_info)

        handler._json_response(200, {
            "coordinator": coordinator_stats,
            "projects": project_stats,
            "project_count": len(project_stats),
        })

    except Exception as e:  # broad catch: top-level handler returns 500 on any failure
        handler._json_response(500, {"error": str(e), "traceback": traceback.format_exc()})
