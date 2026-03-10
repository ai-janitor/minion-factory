"""Lifecycle endpoints — cold-start, refresh, fenix-down for network API.

Purpose: Expose agent lifecycle operations (cold_start, refresh, fenix_down)
         as network API endpoints so remote agents can bootstrap, refresh state,
         and dump knowledge without needing CLI access to the local project DB.
Rationale: CLI parity — these are the most critical agent operations and were
           missing from the network API. Remote daemon agents need these to
           function autonomously.
Responsibility: POST /lifecycle/cold-start, POST /lifecycle/refresh,
                POST /lifecycle/fenix-down. Each delegates to the corresponding
                function in minion.lifecycle after resolving the project DB.
Organization: Each handler parses JSON body, validates required fields,
              delegates to the core lifecycle function, returns JSON result.

Pseudo-logic for each endpoint:
  1. Parse JSON body from request
  2. Extract agent_name (required) and project_path (required for DB resolution)
  3. Validate required fields present
  4. Set up project-local DB context (cd to project_path or use -C equivalent)
  5. Call the core lifecycle function (cold_start / refresh / fenix_down)
  6. Return JSON: {"status": "ok", ...result} or {"error": "..."}
  7. Handle exceptions: 400 for bad input, 404 for agent not found, 500 for internal
"""

from __future__ import annotations

import os
import traceback


def register(router) -> None:
    """Register lifecycle endpoints with the router dispatch table."""
    router.add_post("/lifecycle/cold-start", handle_cold_start)
    router.add_post("/lifecycle/refresh", handle_refresh)
    router.add_post("/lifecycle/fenix-down", handle_fenix_down)


def _with_project_db(project_path: str):
    """Context helper: temporarily set MINION_PROJECT_DIR so lifecycle functions
    find the correct .work/minion.db.

    Returns the old value for restoration.
    """
    # PSEUDO: save old MINION_PROJECT_DIR, set new one, return old
    old = os.environ.get("MINION_PROJECT_DIR")
    os.environ["MINION_PROJECT_DIR"] = project_path
    return old


def _restore_project_db(old_value):
    """Restore previous MINION_PROJECT_DIR after lifecycle call."""
    # PSEUDO: if old was None, delete env var; else restore it
    if old_value is None:
        os.environ.pop("MINION_PROJECT_DIR", None)
    else:
        os.environ["MINION_PROJECT_DIR"] = old_value


def handle_cold_start(handler, db_path: str, **kwargs) -> None:
    """POST /lifecycle/cold-start — bootstrap agent into a session.

    Body: {"agent_name": "...", "project_path": "/path/to/project"}
    Returns: cold_start result dict with operational state snapshot.

    Pseudo-logic:
      1. Parse JSON body
      2. Validate agent_name and project_path present
      3. Set MINION_PROJECT_DIR to project_path
      4. Call lifecycle.cold_start(agent_name)
      5. Restore MINION_PROJECT_DIR
      6. Return result as JSON
    """
    body = handler._parse_json_body()
    if not body:
        return

    agent_name = body.get("agent_name", "").strip() if isinstance(body.get("agent_name"), str) else ""
    project_path = body.get("project_path", "").strip() if isinstance(body.get("project_path"), str) else ""

    if not agent_name:
        handler._json_response(400, {"error": "agent_name is required"})
        return
    if not project_path:
        handler._json_response(400, {"error": "project_path is required"})
        return

    old = _with_project_db(project_path)
    try:
        from minion.lifecycle import cold_start
        result = cold_start(agent_name)
        if "error" in result:
            handler._json_response(404, result)
        else:
            handler._json_response(200, {"status": "ok", **result})
    except Exception as e:
        handler._json_response(500, {"error": str(e), "traceback": traceback.format_exc()})
    finally:
        _restore_project_db(old)


def handle_refresh(handler, db_path: str, **kwargs) -> None:
    """POST /lifecycle/refresh — lightweight mid-session state refresh.

    Body: {"agent_name": "...", "project_path": "/path/to/project"}
    Returns: refresh result dict with current operational state.

    Pseudo-logic:
      1. Parse JSON body
      2. Validate agent_name and project_path present
      3. Set MINION_PROJECT_DIR to project_path
      4. Call lifecycle.refresh(agent_name)
      5. Restore MINION_PROJECT_DIR
      6. Return result as JSON
    """
    body = handler._parse_json_body()
    if not body:
        return

    agent_name = body.get("agent_name", "").strip() if isinstance(body.get("agent_name"), str) else ""
    project_path = body.get("project_path", "").strip() if isinstance(body.get("project_path"), str) else ""

    if not agent_name:
        handler._json_response(400, {"error": "agent_name is required"})
        return
    if not project_path:
        handler._json_response(400, {"error": "project_path is required"})
        return

    old = _with_project_db(project_path)
    try:
        from minion.lifecycle import refresh
        result = refresh(agent_name)
        if "error" in result:
            handler._json_response(404, result)
        else:
            handler._json_response(200, {"status": "ok", **result})
    except Exception as e:
        handler._json_response(500, {"error": str(e), "traceback": traceback.format_exc()})
    finally:
        _restore_project_db(old)


def handle_fenix_down(handler, db_path: str, **kwargs) -> None:
    """POST /lifecycle/fenix-down — dump session knowledge before context death.

    Body: {"agent_name": "...", "project_path": "/path/to/project",
           "files": "file1,file2", "manifest": "optional manifest text"}
    Returns: fenix-down result dict.

    Pseudo-logic:
      1. Parse JSON body
      2. Validate agent_name, project_path, and files present
      3. Set MINION_PROJECT_DIR to project_path
      4. Call lifecycle.fenix_down(agent_name, files, manifest)
      5. Restore MINION_PROJECT_DIR
      6. Return result as JSON
    """
    body = handler._parse_json_body()
    if not body:
        return

    agent_name = body.get("agent_name", "").strip() if isinstance(body.get("agent_name"), str) else ""
    project_path = body.get("project_path", "").strip() if isinstance(body.get("project_path"), str) else ""
    files = body.get("files", "").strip() if isinstance(body.get("files"), str) else ""
    manifest = body.get("manifest", "").strip() if isinstance(body.get("manifest"), str) else ""

    if not agent_name:
        handler._json_response(400, {"error": "agent_name is required"})
        return
    if not project_path:
        handler._json_response(400, {"error": "project_path is required"})
        return
    if not files:
        handler._json_response(400, {"error": "files is required (comma-separated file paths)"})
        return

    old = _with_project_db(project_path)
    try:
        from minion.lifecycle import fenix_down
        result = fenix_down(agent_name, files, manifest)
        if "error" in result:
            handler._json_response(404, result)
        else:
            handler._json_response(200, {"status": "ok", **result})
    except Exception as e:
        handler._json_response(500, {"error": str(e), "traceback": traceback.format_exc()})
    finally:
        _restore_project_db(old)
