"""WebSocket server for the web dashboard — live JSON data push.

Purpose: Serve the web dashboard frontend and push live project state via WebSocket.
Rationale: Complements the terminal TUI dashboard with a browser-accessible view.
    Both TUI and web dashboard consume the same query functions from queries.py —
    no duplicated SQL. The web server adds JSON serialization and WebSocket transport.
Responsibility: WebSocket broadcast loop, HTTP static file serving, query serialization.
    NOT responsible for: SQL queries (queries.py), HTML rendering (static/index.html),
    CLI argument parsing (cli/top_level.py).
Organization: Single module with serve() entry point. Uses asyncio + websockets library.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --- Query serialization helpers ---
# sqlite3.Row is not JSON-serializable. dict(row) produces a plain dict.
# These helpers wrap the query functions that return sqlite3.Row lists
# into JSON-safe dict lists, suitable for WebSocket broadcast.


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert a list of sqlite3.Row objects to JSON-safe dicts.

    Pseudo-logic:
    - For each row, call dict(row) to extract column:value pairs
    - Return the list of dicts
    - Safe for json.dumps() since sqlite3 values are str/int/float/None
    """
    return [dict(row) for row in rows]


def _agent_checklist_tally(agent_name: str, work_dir: str) -> str | None:
    """Find and parse checklist tally for an agent.

    Searches .work/checklists/ for lead-<name>.md or <name>.md.
    Returns "done/total" string (e.g. "3/33") or None if no checklist found.
    """
    import re
    if not work_dir or not agent_name:
        return None
    checklists_dir = os.path.join(work_dir, "checklists")
    # Convention: lead-<name>.md first, then <name>.md
    for pattern in [f"lead-{agent_name}.md", f"{agent_name}.md"]:
        fpath = os.path.join(checklists_dir, pattern)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                if not content:
                    return None
                # Try explicit tally format first: [32/33-0NA]
                first_line = content.split("\n", 1)[0]
                m = re.search(r"\[(\d+/\d+-\d+NA)\]", first_line)
                if m:
                    return m.group(1)
                # Fallback: count checkboxes
                done = len(re.findall(r"- \[x\]", content, re.IGNORECASE))
                total = done + len(re.findall(r"- \[ \]", content))
                if total > 0:
                    return f"{done}/{total}"
            except (OSError, UnicodeDecodeError) as e:
                logger.error("Failed to read checklist for %s: %s", agent_name, e)
    return None


def _get_flow_stages(flow_type: str) -> list[dict[str, Any]]:
    """Return ordered list of stage dicts for a task flow type.

    Pseudo-logic:
    - Load the flow definition via load_flow(flow_type)
    - Walk the happy path (same logic as TaskFlow.render_dag) to get ordered stages
    - Return list of dicts with name, description, fail target, and allowed workers
    - On any error (unknown flow type, etc.), return empty list
    """
    try:
        from minion.tasks.loader import load_flow
        flow = load_flow(flow_type)
        # Walk the happy path from first stage — same algorithm as render_dag
        stages: list[dict[str, Any]] = []
        visited: set[str] = set()
        pointed_to = {s.next for s in flow.stages.values() if s.next}
        starts = [name for name in flow.stages if name not in pointed_to]
        cursor = starts[0] if starts else next(iter(flow.stages), None)
        while cursor and cursor not in visited:
            visited.add(cursor)
            stage = flow.stages.get(cursor)
            if stage is None:
                break
            if not stage.skip:
                stages.append({
                    "name": cursor,
                    "description": stage.description or "",
                    "fail": stage.fail,
                })
            cursor = stage.next
        return stages
    except Exception:
        return []


def _compute_phase_durations(transitions: list[dict]) -> dict[str, str]:
    """Compute time spent in each phase from consecutive transition timestamps.

    Purpose: Show how long an agent spent in each DAG phase (#250).
    Rationale: If transitions show assigned->in_progress at 10:00 and in_progress->qe at 10:15,
        then in_progress took 15 minutes. We compute the delta for each to_status phase.

    Pseudo-logic:
    1. Sort transitions by created_at
    2. For each consecutive pair, compute the time delta
    3. The phase that ended is the to_status of the first transition in the pair
    4. Format as human-readable duration string
    5. Return dict mapping phase_name -> duration_string

    Big-O: O(T) where T = number of transitions. NOT on hot path.
    """
    from datetime import datetime
    durations: dict[str, str] = {}
    if len(transitions) < 2:
        return durations

    for i in range(len(transitions) - 1):
        phase = transitions[i].get("to_status", "")
        t_start = transitions[i].get("created_at", "")
        t_end = transitions[i + 1].get("created_at", "")
        if not t_start or not t_end or not phase:
            continue
        try:
            # Parse ISO timestamps — handle both with and without fractional seconds
            fmt_options = ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"]
            dt_start = None
            dt_end = None
            for fmt in fmt_options:
                if dt_start is None:
                    try:
                        dt_start = datetime.fromisoformat(t_start)
                        break
                    except ValueError:
                        continue
            for fmt in fmt_options:
                if dt_end is None:
                    try:
                        dt_end = datetime.fromisoformat(t_end)
                        break
                    except ValueError:
                        continue
            if dt_start is None or dt_end is None:
                continue
            delta = dt_end - dt_start
            total_seconds = int(delta.total_seconds())
            if total_seconds < 0:
                continue
            if total_seconds < 60:
                durations[phase] = f"{total_seconds}s"
            elif total_seconds < 3600:
                minutes = total_seconds // 60
                secs = total_seconds % 60
                durations[phase] = f"{minutes}m {secs}s" if secs else f"{minutes}m"
            else:
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                durations[phase] = f"{hours}h {minutes}m" if minutes else f"{hours}h"
        except (ValueError, TypeError) as e:
            logger.error("Phase duration parse error for %s: %s", phase, e)
            continue

    return durations


def _lineage_to_dict(lineage: dict) -> dict:
    """Convert lineage result (which contains sqlite3.Row objects) to JSON-safe dict.

    Pseudo-logic:
    - lineage["backlog"] is a sqlite3.Row or None → dict() or None
    - lineage["requirements"] is a list of dicts, each containing:
      - "req": sqlite3.Row → dict()
      - "tasks": list of dicts, each containing:
        - "task": sqlite3.Row → dict()
        - "transitions": list of sqlite3.Row → [dict()]
        - "flow_stages": list[str] — ordered stage names from flow definition (#247)
    - Recursively convert all Row objects to dicts
    """
    result: dict[str, Any] = {"backlog": None, "readme_content": None, "artifacts": [], "requirements": [], "checklists": []}
    result["readme_content"] = lineage.get("readme_content")
    result["artifacts"] = lineage.get("artifacts", [])
    result["checklists"] = lineage.get("checklists", [])
    if lineage.get("backlog") is not None:
        bk = lineage["backlog"]
        result["backlog"] = dict(bk) if hasattr(bk, "keys") else bk

    # Cache flow stages per flow_type to avoid redundant disk reads
    flow_stages_cache: dict[str, list[str]] = {}

    # #250: Parse checklists per-stage for detail panel
    from minion.dashboard.queries import parse_checklists_per_stage
    all_checklists = lineage.get("checklists", [])
    stage_checklist_map = parse_checklists_per_stage(all_checklists)

    for req_entry in lineage.get("requirements", []):
        req = req_entry["req"]
        req_dict = dict(req) if hasattr(req, "keys") else req
        tasks = []
        for task_entry in req_entry.get("tasks", []):
            task = task_entry["task"]
            task_dict = dict(task) if hasattr(task, "keys") else task
            transitions = [
                dict(t) if hasattr(t, "keys") else t
                for t in task_entry.get("transitions", [])
            ]
            # Include flow stages for DAG progression rendering (#247)
            flow_type = task_dict.get("flow_type", "chore")
            if flow_type not in flow_stages_cache:
                flow_stages_cache[flow_type] = _get_flow_stages(flow_type)

            # #250: Compute time spent per phase from transition timestamps
            phase_durations = _compute_phase_durations(transitions)

            tasks.append({
                "task": task_dict,
                "transitions": transitions,
                "flow_stages": flow_stages_cache[flow_type],
                # #249: Surface spec, result content in lineage view
                "spec_content": task_entry.get("spec_content"),
                "result_content": task_entry.get("result_content"),
                # #250: Per-stage checklist entries and phase durations
                "stage_checklists": stage_checklist_map,
                "phase_durations": phase_durations,
            })
        result["requirements"].append({
            "req": req_dict,
            "tasks": tasks,
            # #249: Surface requirement README content in lineage view
            "readme_content": req_entry.get("readme_content"),
        })

    return result


# --- Snapshot builder ---
# Assembles a complete JSON snapshot of project state from queries.py functions.
# This is the data payload sent over WebSocket on each broadcast cycle.


def _build_snapshot(db_path: str) -> dict[str, Any]:
    """Build a complete dashboard state snapshot as a JSON-safe dict.

    Pseudo-logic:
    1. Open a fresh read-only SQLite connection (WAL snapshot isolation)
    2. Call each query function from queries.py
    3. Serialize sqlite3.Row results to dicts
    4. Close connection
    5. Return combined snapshot dict with sections: tasks, agents, backlog, activity
    """
    from minion.db.connection import connect
    from minion.dashboard.queries import (
        fetch_tasks,
        fetch_agents,
        fetch_backlog,
        fetch_activity,
        fetch_all_backlog,
        fetch_task_to_backlog_map,
        get_agent_summary,
        get_task_pipeline,
        get_system_stats,
        get_recent_messages,
    )

    conn = connect(db_path, timeout=2)
    conn.execute("PRAGMA query_only = ON")

    try:
        tasks = _rows_to_dicts(fetch_tasks(conn))
        agents = _rows_to_dicts(fetch_agents(conn))
        backlog = _rows_to_dicts(fetch_backlog(conn))
        activity = _rows_to_dicts(fetch_activity(conn))

        # Map all active task IDs + activity task IDs to backlog IDs.
        # Union both sets so the task table and activity feed both resolve backlog origins (#193).
        # Single DB call — no extra round-trip vs the previous activity-only approach.
        all_task_ids = list({row["id"] for row in tasks} | {row["task_id"] for row in activity})
        task_to_backlog = fetch_task_to_backlog_map(conn, all_task_ids)

        # These already return dicts — pass through
        agent_summary = get_agent_summary(conn)
        task_pipeline = get_task_pipeline(conn)
        system_stats = get_system_stats(conn, db_path)
        recent_messages = get_recent_messages(conn)

        # Add checklist tally to each agent
        work_dir = os.path.dirname(db_path)
        for agent in agents:
            agent["checklist_tally"] = _agent_checklist_tally(agent.get("name", ""), work_dir)

        # Derive project name from the DB path:
        # db_path is typically <project-root>/.work/minion.db
        project_root = os.path.dirname(os.path.dirname(db_path))
        project_name = os.path.basename(project_root) or db_path

        # --- Agent tool-call activity from stream.jsonl files ---
        # Resolve logs directory: sibling .minion-swarm/logs/ relative to project root.
        # Call stream tailer to extract recent tool_use events per agent.
        # Gracefully returns empty dict on any error (missing dir, no files, etc.).
        agent_activity: dict[str, list] = {}
        try:
            from minion.dashboard.stream_tailer import tail_agent_activity
            logs_dir = os.path.join(project_root, ".minion-swarm", "logs")
            if os.path.isdir(logs_dir):
                agent_names = [a.get("name", "") for a in agents if a.get("name")]
                agent_activity = tail_agent_activity(logs_dir, agent_names, max_events=5)
        except Exception:
            logger.debug("Failed to read agent activity from stream.jsonl", exc_info=True)

        snapshot = {
            "type": "snapshot",
            "project_name": project_name,
            "db_path": db_path,
            "tasks": tasks,
            "agents": agents,
            "backlog": backlog,
            "activity": activity,
            "task_to_backlog": {str(k): v for k, v in task_to_backlog.items()},
            "agent_summary": agent_summary,
            "task_pipeline": task_pipeline,
            "system_stats": system_stats,
            "recent_messages": recent_messages,
            "agent_activity": agent_activity,
        }
    finally:
        conn.close()

    return snapshot


def _build_lineage(db_path: str, backlog_id: int) -> dict[str, Any]:
    """Build lineage data for a specific backlog item.

    Pseudo-logic:
    1. Open read-only connection
    2. Call fetch_lineage(conn, backlog_id, work_dir) — work_dir enables README reading (#246)
    3. Convert sqlite3.Row objects to dicts via _lineage_to_dict
    4. Return JSON-safe lineage dict
    """
    from minion.db.connection import connect
    from minion.dashboard.queries import fetch_lineage, fetch_agent_contexts

    conn = connect(db_path, timeout=2)
    conn.execute("PRAGMA query_only = ON")

    # Derive work_dir from db_path — the .work/ directory containing minion.db
    work_dir = os.path.dirname(db_path)

    try:
        lineage = fetch_lineage(conn, backlog_id, work_dir=work_dir)

        # #250: Collect all agent names from transitions and fetch their contexts
        agent_names: set[str] = set()
        for req_entry in lineage.get("requirements", []):
            for task_entry in req_entry.get("tasks", []):
                for t in task_entry.get("transitions", []):
                    triggered_by = t["triggered_by"] if hasattr(t, "__getitem__") else getattr(t, "triggered_by", None)
                    if triggered_by:
                        agent_names.add(triggered_by)
        agent_contexts = fetch_agent_contexts(conn, agent_names)
    finally:
        conn.close()

    result = _lineage_to_dict(lineage)
    # #250: Include agent contexts in lineage payload
    result["agent_contexts"] = agent_contexts

    return {"type": "lineage", "data": result}


# --- WebSocket handler ---
# Manages connected clients and handles incoming messages (lineage requests).


# Connected WebSocket clients — broadcast target set
_clients: set = set()


async def _ws_handler(websocket: Any, db_path: str) -> None:
    """Handle a single WebSocket connection.

    Pseudo-logic:
    1. Add client to _clients set
    2. Send initial snapshot immediately
    3. Listen for incoming messages (lineage requests)
    4. On message: parse JSON, if type=="lineage_request", build and send lineage
    5. On disconnect: remove from _clients set
    """
    _clients.add(websocket)
    logger.info("WebSocket client connected (%d total)", len(_clients))

    try:
        # Send initial snapshot immediately on connect
        snapshot = _build_snapshot(db_path)
        await websocket.send(json.dumps(snapshot))

        # Listen for client messages (lineage requests)
        async for message in websocket:
            try:
                msg = json.loads(message)
                if msg.get("type") == "lineage_request":
                    backlog_id = int(msg["backlog_id"])
                    lineage = _build_lineage(db_path, backlog_id)
                    await websocket.send(json.dumps(lineage))
            except Exception as e:
                # Generate a short error ID for correlation — log full details server-side only.
                # Client receives only the generic message + error_id (no stack trace, no file paths).
                error_id = uuid.uuid4().hex[:8]
                logger.error(
                    "Lineage request failed [error_id=%s]: %s: %s",
                    error_id, type(e).__name__, e,
                    exc_info=True,
                )
                try:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Lineage request failed",
                        "error_id": error_id,
                    }))
                except Exception as e2:
                    logger.error("Failed to send error response to client: %s", e2)
    except Exception as e:
        # Log the actual error instead of silently swallowing it
        logger.error("WebSocket handler error: %s: %s", type(e).__name__, e)
    finally:
        _clients.discard(websocket)
        logger.info("WebSocket client disconnected (%d remaining)", len(_clients))


# --- Broadcast loop ---
# Periodically builds a snapshot and pushes it to all connected clients.


async def _broadcast_loop(db_path: str, interval: float = 2.0) -> None:
    """Broadcast dashboard snapshot to all connected clients every `interval` seconds.

    Pseudo-logic:
    1. Sleep for interval
    2. If no clients connected, skip (save CPU/DB)
    3. Build snapshot from DB
    4. JSON-encode
    5. Send to all connected clients concurrently
    6. Log any send failures, remove dead clients
    7. Repeat forever
    """
    while True:
        await asyncio.sleep(interval)
        if not _clients:
            continue

        try:
            snapshot = _build_snapshot(db_path)
            payload = json.dumps(snapshot)
        except Exception as e:
            logger.error("Snapshot build failed: %s", e)
            continue

        # Broadcast to all connected clients
        disconnected = set()
        for client in _clients.copy():
            try:
                await client.send(payload)
            except Exception:
                disconnected.add(client)

        _clients.difference_update(disconnected)


# --- HTTP handler for static files ---
# Serves index.html from the static/ directory alongside this module.
# Uses websockets library's built-in HTTP hook (process_request).


def _get_static_dir() -> Path:
    """Return path to the static/ directory bundled with this package."""
    return Path(__file__).parent / "static"


def _http_handler(connection: Any, request: Any) -> Any:
    """Serve static files via HTTP (process_request hook for websockets v16+).

    Pseudo-logic:
    1. If path is "/" or "/index.html", serve static/index.html as Response
    2. Return Response object for HTTP requests
    3. Return None for WebSocket upgrade requests (proceed with WS handshake)

    websockets v16 signature: process_request(connection, request) -> Response | None
    """
    from websockets.http11 import Response
    from websockets.datastructures import Headers

    path = request.path

    # If this is a WebSocket upgrade request, let it through regardless of path
    upgrade = request.headers.get("Upgrade", "").lower()
    if upgrade == "websocket":
        return None

    static_dir = _get_static_dir()

    if path in ("/", "/index.html"):
        index_path = static_dir / "index.html"
        if index_path.exists():
            body = index_path.read_bytes()
            return Response(
                200, "OK",
                Headers([("Content-Type", "text/html; charset=utf-8")]),
                body,
            )
        return Response(
            404, "Not Found",
            Headers([("Content-Type", "text/plain")]),
            b"index.html not found",
        )

    # Any other HTTP path (favicon.ico, etc.) — return 404, do NOT fall through
    # to WebSocket handshake (returning None on a non-upgrade request crashes).
    return Response(
        404, "Not Found",
        Headers([("Content-Type", "text/plain")]),
        b"Not found",
    )


# --- Entry point ---


async def _serve_async(host: str, port: int, db_path: str) -> None:
    """Start WebSocket server and broadcast loop.

    Pseudo-logic:
    1. Import websockets
    2. Start WebSocket server with HTTP hook for static files
    3. Start broadcast loop as background task
    4. Run both forever until interrupted
    """
    try:
        import websockets
        import websockets.server
    except ImportError:
        raise SystemExit(
            "websockets package not installed. "
            "Install with: uv pip install websockets"
        )

    logger.info("Starting web dashboard on http://%s:%d", host, port)
    logger.info("WebSocket endpoint: ws://%s:%d/ws", host, port)
    logger.info("DB path: %s", db_path)

    # Start broadcast loop as background task
    broadcast_task = asyncio.create_task(_broadcast_loop(db_path))

    async with websockets.serve(  # type: ignore[attr-defined]
        lambda ws: _ws_handler(ws, db_path),
        host,
        port,
        process_request=_http_handler,
    ):
        try:
            await asyncio.Future()  # Run forever
        except asyncio.CancelledError:
            logger.info("Web dashboard server cancelled, shutting down")
        finally:
            broadcast_task.cancel()


def serve(host: str = "0.0.0.0", port: int = 8765, db_path: str = "") -> None:
    """Synchronous entry point — resolves DB path and starts the async server.

    Called by the CLI command: `minion dashboard --web [--port PORT]`

    Pseudo-logic:
    1. If db_path not provided, resolve via resolve_db_path() (same as TUI)
    2. Validate DB exists
    3. Run the async server
    """
    if not db_path:
        from minion.defaults import resolve_db_path
        db_path = str(resolve_db_path())

    if not os.path.exists(db_path):
        raise SystemExit(f"Database not found: {db_path}")

    print(f"Minion Web Dashboard: http://{host}:{port}")
    print(f"Database: {db_path}")
    print("Press Ctrl+C to stop.")

    try:
        asyncio.run(_serve_async(host, port, db_path))
    except KeyboardInterrupt:
        print("\nShutting down.")
