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
import sqlite3
import threading
from datetime import datetime

from minion.network.server import _get_server_db, _DB_LOCK


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


def handle_who(handler, db_path: str, **kwargs) -> None:
    """GET /who — list all registered agents."""
    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            rows = conn.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
            agents = [dict(r) for r in rows]
        finally:
            conn.close()
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

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            conn.execute(
                """INSERT INTO agents (name, agent_class, host, project_path, machine_id,
                       registered_at, last_seen, model, capabilities, crew_name, local_lead,
                       machine_specs, runtimes, os_platform, session_count, compaction_count,
                       crash_rate, total_input_tokens, total_output_tokens,
                       last_task_completed_at, autonomous_delegation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                       agent_class = COALESCE(NULLIF(excluded.agent_class, 'coder'), agents.agent_class),
                       host = COALESCE(excluded.host, agents.host),
                       project_path = COALESCE(excluded.project_path, agents.project_path),
                       machine_id = COALESCE(excluded.machine_id, agents.machine_id),
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
                    body.get("project_path"),
                    body.get("machine_id"),
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

    handler._json_response(200, {"status": "registered", "agent": name})


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
