"""API GLOBAL coordinator server — stdlib http.server, zero external deps.

Endpoints:
  POST /register       — register agent with host/project info
  POST /send           — deliver message to target agent
  GET  /inbox/{agent}  — fetch and mark-read unread messages
  GET  /who            — list all registered agents
  GET  /health         — liveness check
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

_DB_LOCK = threading.Lock()


def _get_server_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _init_server_db(db_path: str) -> None:
    conn = _get_server_db(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            name         TEXT PRIMARY KEY,
            agent_class  TEXT NOT NULL DEFAULT 'coder',
            host         TEXT,
            project_path TEXT,
            machine_id   TEXT,
            registered_at TEXT,
            last_seen    TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent  TEXT NOT NULL,
            to_agent    TEXT NOT NULL,
            content     TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            read_flag   INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_msg_to_unread ON messages(to_agent, read_flag);
    """)
    conn.commit()
    conn.close()


def _check_token(headers: dict, expected: str) -> bool:
    """Validate Bearer token from Authorization header."""
    if not expected:
        return True  # no auth configured
    auth = headers.get("Authorization", "")
    return auth == f"Bearer {expected}"


class _Handler(BaseHTTPRequestHandler):
    """Request handler — routes to endpoint functions."""

    db_path: str = ""
    token: str = ""

    def log_message(self, format, *args):
        """Suppress default stderr logging."""
        pass

    def _json_response(self, status: int, data: dict) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _parse_json_body(self) -> dict | None:
        try:
            return json.loads(self._read_body())
        except (json.JSONDecodeError, ValueError):
            return None

    def do_GET(self) -> None:
        if not _check_token(dict(self.headers), self.token):
            self._json_response(401, {"error": "Unauthorized"})
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/health":
            self._json_response(200, {"status": "ok", "timestamp": datetime.now().isoformat()})
        elif path == "/who":
            self._handle_who()
        elif path.startswith("/inbox/"):
            agent = path[len("/inbox/"):]
            if agent:
                self._handle_inbox(agent)
            else:
                self._json_response(400, {"error": "Agent name required: /inbox/{name}"})
        else:
            self._json_response(404, {"error": f"Not found: {path}"})

    def do_POST(self) -> None:
        if not _check_token(dict(self.headers), self.token):
            self._json_response(401, {"error": "Unauthorized"})
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/register":
            self._handle_register()
        elif path == "/send":
            self._handle_send()
        else:
            self._json_response(404, {"error": f"Not found: {path}"})

    def _handle_register(self) -> None:
        body = self._parse_json_body()
        if not body:
            self._json_response(400, {"error": "Invalid JSON body"})
            return

        name = body.get("name", "").strip()
        if not name:
            self._json_response(400, {"error": "name is required"})
            return

        now = datetime.now().isoformat()
        with _DB_LOCK:
            conn = _get_server_db(self.db_path)
            try:
                conn.execute(
                    """INSERT INTO agents (name, agent_class, host, project_path, machine_id, registered_at, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(name) DO UPDATE SET
                           agent_class = COALESCE(NULLIF(excluded.agent_class, 'coder'), agents.agent_class),
                           host = COALESCE(excluded.host, agents.host),
                           project_path = COALESCE(excluded.project_path, agents.project_path),
                           machine_id = COALESCE(excluded.machine_id, agents.machine_id),
                           last_seen = excluded.last_seen
                    """,
                    (
                        name,
                        body.get("agent_class", "coder"),
                        body.get("host"),
                        body.get("project_path"),
                        body.get("machine_id"),
                        now,
                        now,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        self._json_response(200, {"status": "registered", "agent": name})

    def _handle_send(self) -> None:
        body = self._parse_json_body()
        if not body:
            self._json_response(400, {"error": "Invalid JSON body"})
            return

        from_agent = body.get("from", "").strip()
        to_agent = body.get("to", "").strip()
        content = body.get("message", "").strip()

        if not from_agent or not to_agent or not content:
            self._json_response(400, {"error": "from, to, and message are required"})
            return

        now = datetime.now().isoformat()
        with _DB_LOCK:
            conn = _get_server_db(self.db_path)
            try:
                # Verify target exists
                row = conn.execute("SELECT name FROM agents WHERE name = ?", (to_agent,)).fetchone()
                if not row:
                    self._json_response(404, {"error": f"Agent '{to_agent}' not registered on network"})
                    conn.close()
                    return

                conn.execute(
                    "INSERT INTO messages (from_agent, to_agent, content, timestamp) VALUES (?, ?, ?, ?)",
                    (from_agent, to_agent, content, now),
                )
                # Update sender last_seen
                conn.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, from_agent))
                conn.commit()
            finally:
                conn.close()

        self._json_response(200, {"status": "sent", "from": from_agent, "to": to_agent})

    def _handle_inbox(self, agent: str) -> None:
        now = datetime.now().isoformat()
        with _DB_LOCK:
            conn = _get_server_db(self.db_path)
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

        self._json_response(200, {"messages": messages, "agent": agent})

    def _handle_who(self) -> None:
        with _DB_LOCK:
            conn = _get_server_db(self.db_path)
            try:
                rows = conn.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
                agents = [dict(r) for r in rows]
            finally:
                conn.close()

        self._json_response(200, {"agents": agents, "source": "network"})


def serve(port: int = 8377, db_path: str = "", token: str = "") -> None:
    """Start the API GLOBAL coordinator server.

    Args:
        port: TCP port to listen on.
        db_path: Path to the network coordinator SQLite DB.
                 Defaults to ~/.minion/network.db.
        token: Shared cluster token for auth. Falls back to MINION_CLUSTER_TOKEN env var.
    """
    if not db_path:
        db_path = os.path.join(os.path.expanduser("~"), ".minion", "network.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    _init_server_db(db_path)

    if not token:
        token = os.environ.get("MINION_CLUSTER_TOKEN", "")

    _Handler.db_path = db_path
    _Handler.token = token

    server = HTTPServer(("0.0.0.0", port), _Handler)
    print(f"minion network server listening on 0.0.0.0:{port}")
    if token:
        print("auth: bearer token required")
    else:
        print("auth: NONE (set MINION_CLUSTER_TOKEN for security)")
    print(f"db: {db_path}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()
