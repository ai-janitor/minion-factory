"""Core network endpoints — /health, /who, /register, /send, /inbox, /messages/recent.

Purpose: Houses the original 6 endpoints extracted from server.py's monolithic _Handler.
Rationale: These are the foundational agent-comms endpoints that existed before the
           dashboard expansion. Grouping them keeps the migration clean — move existing
           logic here, then server.py just delegates.
Responsibility: All reads/writes to the network coordinator DB (agents + messages tables).
Organization: Each endpoint is a standalone function taking (handler, db_path, **kwargs).
              The register() function maps URL patterns to these functions.

Implementation order: 1st (no dependencies on other new modules except auth).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

from minion.network.server import _get_server_db, _DB_LOCK
from minion.network.project_db import get_project_db


def register(router) -> None:
    """Register core endpoints with the router dispatch table."""
    router.add_get("/health", handle_health)
    router.add_get("/who", handle_who)
    router.add_get("/messages/recent", handle_recent_messages)
    router.add_get("/inbox/{agent}", handle_inbox)
    router.add_post("/register", handle_register)
    router.add_post("/send", handle_send)


def handle_health(handler, db_path: str, **kwargs) -> None:
    """GET /health — liveness check, returns status + timestamp."""
    handler._json_response(200, {"status": "ok", "timestamp": datetime.now().isoformat()})


def _build_fqn(agent: dict) -> str:
    """Build fully qualified name: machine_id/project_basename/name."""
    # PSEUDO: fqn = machine_id/basename(project_path)/name
    mid = agent.get("machine_id") or "unknown"
    pp = agent.get("project_path") or "unknown"
    pname = os.path.basename(pp.rstrip("/")) if pp != "unknown" else "unknown"
    return f"{mid}/{pname}/{agent['name']}"


# --- Presence thresholds (minutes) ---
_PRESENCE_ONLINE_MINS = 5
_PRESENCE_STALE_MINS = 30


def _compute_presence(last_seen: str | None) -> str:
    """Compute presence from last_seen timestamp.

    Returns: 'online' (<5min), 'stale' (5-30min), 'offline' (>30min or null).
    """
    # PSEUDO: parse last_seen ISO, compute age in minutes
    # PSEUDO: if age < 5 → online; < 30 → stale; else → offline
    if not last_seen:
        return "offline"
    try:
        ts = datetime.fromisoformat(last_seen)
        now = datetime.now()
        age_mins = (now - ts).total_seconds() / 60
        if age_mins < _PRESENCE_ONLINE_MINS:
            return "online"
        elif age_mins < _PRESENCE_STALE_MINS:
            return "stale"
        return "offline"
    except (ValueError, TypeError):
        return "offline"


def _compute_availability(agent: dict, current_task: dict | None) -> str:
    """Compute availability from agent state and current task.

    Returns: 'idle', 'busy', 'blocked', or 'critical'.
    """
    # PSEUDO: if HP < 25% → critical
    # PSEUDO: if current_task and task.status == 'blocked' → blocked
    # PSEUDO: if current_task → busy
    # PSEUDO: else → idle
    # Check HP from crash_rate (proxy — low crash_rate = healthy)
    # For now, use a simple heuristic based on task state
    if current_task:
        if current_task.get("status") == "blocked":
            return "blocked"
        return "busy"
    return "idle"


def _get_current_task(project_path: str | None, agent_name: str) -> dict | None:
    """Read current task for an agent from project-local DB.

    Returns {id, title, status} or None if no active task or DB unreachable.
    """
    # PSEUDO: if not project_path → return None
    # PSEUDO: conn = get_project_db(project_path)
    # PSEUDO: SELECT id, title, status FROM tasks WHERE assigned_to = ? AND status IN ('assigned','in_progress')
    if not project_path:
        return None
    try:
        conn = get_project_db(project_path)
        if not conn:
            return None
        row = conn.execute(
            "SELECT id, title, status FROM tasks WHERE assigned_to = ? AND status IN ('assigned','in_progress') LIMIT 1",
            (agent_name,),
        ).fetchone()
        if row:
            return {"id": row["id"], "title": row["title"], "status": row["status"]}
    except Exception:
        pass
    return None


def _enrich_agent(agent: dict) -> dict:
    """Add computed fields: fqn, presence, availability, current_task, project_name."""
    # PSEUDO: compute fqn, presence, availability, current_task, project_name
    agent["fqn"] = _build_fqn(agent)
    agent["presence"] = _compute_presence(agent.get("last_seen"))
    pp = agent.get("project_path") or ""
    agent["project_name"] = os.path.basename(pp.rstrip("/")) if pp else None
    current_task = _get_current_task(pp if pp else None, agent["name"])
    agent["current_task"] = current_task
    agent["availability"] = _compute_availability(agent, current_task)
    return agent


def handle_who(handler, db_path: str, **kwargs) -> None:
    """GET /who — list all registered agents with computed presence/availability.

    Query params:
      ?class=coder — filter by agent_class
      ?project=minion-factory — filter by project name (basename of project_path)
      ?status=online — filter by presence (online/stale/offline)
      ?available=true — only agents available for task assignment
    """
    # PSEUDO: fetch all agents from network DB
    # PSEUDO: enrich each with computed fields
    # PSEUDO: apply query param filters
    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            rows = conn.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
            agents = [dict(r) for r in rows]
        finally:
            conn.close()

    # Enrich with computed fields
    for a in agents:
        _enrich_agent(a)

    # Parse query params
    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)

    # Apply filters
    filter_class = params.get("class", [None])[0]
    filter_project = params.get("project", [None])[0]
    filter_status = params.get("status", [None])[0]
    filter_available = params.get("available", [None])[0]

    if filter_class:
        agents = [a for a in agents if a.get("agent_class") == filter_class]
    if filter_project:
        agents = [a for a in agents if a.get("project_name") == filter_project]
    if filter_status:
        agents = [a for a in agents if a.get("presence") == filter_status]
    if filter_available and filter_available.lower() == "true":
        # PSEUDO: available = online AND availability != blocked
        agents = [a for a in agents if a.get("presence") == "online" and a.get("availability") != "blocked"]

    handler._json_response(200, {"agents": agents, "source": "network"})


def handle_recent_messages(handler, db_path: str, **kwargs) -> None:
    """GET /messages/recent — last 20 network-tier messages."""
    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY timestamp DESC LIMIT 20"
            ).fetchall()
            messages = [dict(r) for r in rows]
        finally:
            conn.close()
    handler._json_response(200, {"messages": messages})


def handle_inbox(handler, db_path: str, agent: str = "", **kwargs) -> None:
    """GET /inbox/{agent} — fetch unread messages, mark as read, update last_seen."""
    if not agent:
        handler._json_response(400, {"error": "Agent name required: /inbox/{name}"})
        return

    now = datetime.now().isoformat()
    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM messages WHERE to_agent = ? AND read_flag = 0 ORDER BY timestamp ASC",
                (agent,),
            ).fetchall()
            messages = [dict(r) for r in rows]
            if messages:
                ids = [m["id"] for m in messages]
                conn.execute(
                    f"UPDATE messages SET read_flag = 1 WHERE id IN ({','.join('?' * len(ids))})",
                    ids,
                )
            # PSEUDO: update last_seen for all agents matching this name (composite PK)
            # In network DB, agent URL param is short name — update all matching rows
            conn.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, agent))
            conn.commit()
        finally:
            conn.close()
    handler._json_response(200, {"messages": messages, "agent": agent})


def handle_register(handler, db_path: str, **kwargs) -> None:
    """POST /register — upsert agent with all provided fields."""
    body = handler._parse_json_body()
    if not body:
        handler._json_response(400, {"error": "Invalid JSON body"})
        return

    name = body.get("name", "").strip()
    if not name:
        handler._json_response(400, {"error": "name is required"})
        return

    # PSEUDO: machine_id and project_path form composite PK with name
    # PSEUDO: default to 'unknown' if not provided (backward compat)
    machine_id = body.get("machine_id") or "unknown"
    project_path = body.get("project_path") or "unknown"

    now = datetime.now().isoformat()

    # JSON-encode list/dict fields
    capabilities = body.get("capabilities")
    if isinstance(capabilities, list):
        capabilities = json.dumps(capabilities)
    machine_specs = body.get("machine_specs")
    if isinstance(machine_specs, dict):
        machine_specs = json.dumps(machine_specs)
    runtimes = body.get("runtimes")
    if isinstance(runtimes, list):
        runtimes = json.dumps(runtimes)

    # PSEUDO: Build FQN for response: machine_id/project_basename/name
    project_basename = os.path.basename(project_path.rstrip("/")) if project_path != "unknown" else "unknown"
    fqn = f"{machine_id}/{project_basename}/{name}"

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            # PSEUDO: ON CONFLICT uses composite key (machine_id, project_path, name)
            conn.execute(
                """INSERT INTO agents (name, agent_class, host, project_path, machine_id,
                       registered_at, last_seen, model, capabilities, crew_name, local_lead,
                       machine_specs, runtimes, os_platform, session_count, compaction_count,
                       crash_rate, total_input_tokens, total_output_tokens,
                       last_task_completed_at, autonomous_delegation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(machine_id, project_path, name) DO UPDATE SET
                       agent_class = COALESCE(NULLIF(excluded.agent_class, 'coder'), agents.agent_class),
                       host = COALESCE(excluded.host, agents.host),
                       model = COALESCE(excluded.model, agents.model),
                       capabilities = COALESCE(excluded.capabilities, agents.capabilities),
                       crew_name = COALESCE(excluded.crew_name, agents.crew_name),
                       local_lead = COALESCE(excluded.local_lead, agents.local_lead),
                       machine_specs = COALESCE(excluded.machine_specs, agents.machine_specs),
                       runtimes = COALESCE(excluded.runtimes, agents.runtimes),
                       os_platform = COALESCE(excluded.os_platform, agents.os_platform),
                       session_count = COALESCE(excluded.session_count, agents.session_count),
                       compaction_count = COALESCE(excluded.compaction_count, agents.compaction_count),
                       crash_rate = COALESCE(excluded.crash_rate, agents.crash_rate),
                       total_input_tokens = COALESCE(excluded.total_input_tokens, agents.total_input_tokens),
                       total_output_tokens = COALESCE(excluded.total_output_tokens, agents.total_output_tokens),
                       last_task_completed_at = COALESCE(excluded.last_task_completed_at, agents.last_task_completed_at),
                       autonomous_delegation = COALESCE(excluded.autonomous_delegation, agents.autonomous_delegation),
                       last_seen = excluded.last_seen
                """,
                (
                    name,
                    body.get("agent_class", "coder"),
                    body.get("host"),
                    project_path,
                    machine_id,
                    now, now,
                    body.get("model"),
                    capabilities,
                    body.get("crew_name"),
                    body.get("local_lead"),
                    machine_specs,
                    runtimes,
                    body.get("os_platform"),
                    body.get("session_count"),
                    body.get("compaction_count"),
                    body.get("crash_rate"),
                    body.get("total_input_tokens"),
                    body.get("total_output_tokens"),
                    body.get("last_task_completed_at"),
                    1 if body.get("autonomous_delegation") else 0,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    handler._json_response(200, {"status": "registered", "agent": name, "fqn": fqn})


def handle_send(handler, db_path: str, **kwargs) -> None:
    """POST /send — deliver message to target agent."""
    body = handler._parse_json_body()
    if not body:
        handler._json_response(400, {"error": "Invalid JSON body"})
        return

    from_agent = body.get("from", "").strip()
    to_agent = body.get("to", "").strip()
    content = body.get("message", "").strip()

    if not from_agent or not to_agent or not content:
        handler._json_response(400, {"error": "from, to, and message are required"})
        return

    now = datetime.now().isoformat()
    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            # PSEUDO: check if recipient exists — match by name (short name lookup)
            # With composite PK, multiple agents may share same name across projects
            row = conn.execute("SELECT name FROM agents WHERE name = ?", (to_agent,)).fetchone()
            if not row:
                handler._json_response(404, {"error": f"Agent '{to_agent}' not registered on network"})
                conn.close()
                return
            conn.execute(
                "INSERT INTO messages (from_agent, to_agent, content, timestamp) VALUES (?, ?, ?, ?)",
                (from_agent, to_agent, content, now),
            )
            conn.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, from_agent))
            conn.commit()
        finally:
            conn.close()

    handler._json_response(200, {"status": "sent", "from": from_agent, "to": to_agent})
