"""API GLOBAL coordinator server — stdlib http.server, zero external deps.
Endpoints delegated to handlers/ via router.py dispatch table.
Core endpoints (6): /health, /who, /register, /send, /inbox/{agent}, /messages/recent
Dashboard endpoints: /projects, /projects/{name}/agents|tasks|messages|raid-log, etc.
See router.py for the full route table and handlers/ for endpoint implementations.

Purpose: API GLOBAL coordinator server — stdlib http.server, zero external deps.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: API GLOBAL coordinator server — stdlib http.server, zero external deps. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from minion.db.connection import connect as _db_connect
from minion.network.auth import AuthMixin

_DB_LOCK = threading.Lock()

# Maximum request body size (1 MB) — prevents DoS via oversized payloads
MAX_BODY_SIZE = 1 * 1024 * 1024


def _get_server_db(db_path: str) -> sqlite3.Connection:
    return _db_connect(db_path)


def _init_server_db(db_path: str) -> None:
    # PSEUDO: Use db_schema.init_db() for fresh installs, then migrate_to_composite_pk() for upgrades
    from minion.network.db_schema import init_db, migrate_db, migrate_to_composite_pk, migrate_channels, migrate_agent_uuids, migrate_message_uuids
    init_db(db_path)
    migrate_db(db_path)
    migrate_to_composite_pk(db_path)
    migrate_channels(db_path)
    migrate_agent_uuids(db_path)
    migrate_message_uuids(db_path)


class _Handler(AuthMixin, BaseHTTPRequestHandler):
    """Request handler — routes to endpoint functions."""

    db_path: str = ""
    token: str = ""

    # Per-request start time — set by _timed_dispatch before handler runs
    _request_start: float = 0.0

    def log_message(self, format, *args):
        """Suppress default stderr logging — we emit structured JSON in _log_request instead."""
        pass

    def _log_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        """Emit structured JSON log line for every HTTP request.

        Fields match daemon runner format (ts, level, source, message) plus
        HTTP-specific fields: method, path, status_code, duration_ms, client.
        """
        print(json.dumps({
            "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "level": "INFO",
            "source": "network.http",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "client": self.client_address[0],
            "message": f"{method} {path} {status_code} {round(duration_ms, 1)}ms",
        }), flush=True)

    # Captured response status code — set by send_response override
    _response_status: int = 0

    def send_response(self, code, message=None):
        """Override to capture status code for structured logging."""
        self._response_status = code
        super().send_response(code, message)

    def _json_response(self, status: int, data: dict) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        """Read request body, enforcing MAX_BODY_SIZE limit."""
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY_SIZE:
            self._json_response(413, {"error": f"Request body too large (max {MAX_BODY_SIZE} bytes)"})
            return b""
        return self.rfile.read(length)

    def _check_content_type_json(self) -> bool:
        """Validate Content-Type is application/json. Returns False and sends 415 if not."""
        ct = self.headers.get("Content-Type", "")
        # Accept "application/json" with optional params (e.g. "; charset=utf-8")
        if not ct.split(";")[0].strip().lower() == "application/json":
            self._json_response(415, {"error": "Content-Type must be application/json"})
            return False
        return True

    def _parse_json_body(self) -> dict | None:
        """Parse request body as JSON. Returns None if body is too large, wrong content-type, or invalid."""
        if not self._check_content_type_json():
            return None
        raw = self._read_body()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None

    def _html_response(self, html: str) -> None:
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # Class-level router — initialized once at server startup in serve()
    _router = None

    def do_GET(self) -> None:
        start = time.monotonic()
        self._response_status = 0
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Dashboard HTML — served without auth (JS handles token via localStorage)
        if path == "" or path == "/":
            from minion.network.dashboard import DASHBOARD_HTML
            self._html_response(DASHBOARD_HTML)
            self._log_request("GET", path or "/", self._response_status, (time.monotonic() - start) * 1000)
            return

        # SU-22: Server-rendered dashboard pages — no auth (read-only views)
        if path.startswith("/dashboard"):
            try:
                from minion.network.handlers.dashboard_views import handle_dashboard_page
                html = handle_dashboard_page(path, self.db_path)
                if html is not None:
                    self._html_response(html)
                    self._log_request("GET", path, self._response_status, (time.monotonic() - start) * 1000)
                    return
            except (ImportError, OSError):
                pass  # Fall through to auth-required routes if dashboard views unavailable

        # Bootstrap endpoints — served without auth (new machines need these to install)
        _GET_NO_AUTH = {"/install.sh", "/version"}
        if path in _GET_NO_AUTH:
            if self._router:
                handler_fn, params = self._router.route_get(path)
                if handler_fn:
                    handler_fn(self, self.db_path, **params)
                    self._log_request("GET", path, self._response_status, (time.monotonic() - start) * 1000)
                    return

        # API endpoints — auth required
        if not self.require_auth():
            self._log_request("GET", path, self._response_status, (time.monotonic() - start) * 1000)
            return

        # Delegate to router
        if self._router:
            handler_fn, params = self._router.route_get(path)
            if handler_fn:
                handler_fn(self, self.db_path, **params)
                self._log_request("GET", path, self._response_status, (time.monotonic() - start) * 1000)
                return

        self._json_response(404, {"error": f"Not found: {path}"})
        self._log_request("GET", path, 404, (time.monotonic() - start) * 1000)

    # POST paths that skip auth (login must work without a token)
    _POST_NO_AUTH = {"/api/login"}

    def do_POST(self) -> None:
        start = time.monotonic()
        self._response_status = 0
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path not in self._POST_NO_AUTH:
            if not self.require_auth():
                self._log_request("POST", path, self._response_status, (time.monotonic() - start) * 1000)
                return

        # Delegate to router
        if self._router:
            handler_fn, params = self._router.route_post(path)
            if handler_fn:
                handler_fn(self, self.db_path, **params)
                self._log_request("POST", path, self._response_status, (time.monotonic() - start) * 1000)
                return

        self._json_response(404, {"error": f"Not found: {path}"})
        self._log_request("POST", path, 404, (time.monotonic() - start) * 1000)


def _tls_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".minion", "tls")


def gen_cert(common_name: str = "minion-network") -> dict[str, str]:
    """Generate a self-signed TLS certificate for the network server.

    Creates ~/.minion/tls/cert.pem and ~/.minion/tls/key.pem.
    Uses stdlib ssl + subprocess to call openssl (available on macOS and Linux).
    """
    import subprocess

    tls = _tls_dir()
    os.makedirs(tls, exist_ok=True)
    cert_path = os.path.join(tls, "cert.pem")
    key_path = os.path.join(tls, "key.pem")

    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key_path, "-out", cert_path,
            "-days", "365", "-nodes",
            "-subj", f"/CN={common_name}",
        ],
        check=True,
        capture_output=True,
    )
    os.chmod(key_path, 0o600)
    return {"cert": cert_path, "key": key_path}


def serve(port: int = 8377, db_path: str = "", token: str = "", allow_no_auth: bool = False) -> None:
    """Start the API GLOBAL coordinator server with TLS by default.

    TLS uses ~/.minion/tls/cert.pem + key.pem (generate with gen_cert()).
    Set MINION_NETWORK_INSECURE=1 to run plain HTTP (dev only).

    Args:
        port: TCP port to listen on.
        db_path: Path to the network coordinator SQLite DB.
                 Defaults to ~/.minion/network.db.
        token: Shared cluster token for auth. Falls back to MINION_CLUSTER_TOKEN env var.
        allow_no_auth: If True, allow starting without an auth token (dev mode).
                       Falls back to MINION_NETWORK_NO_AUTH=1 env var.
    """
    if not db_path:
        db_path = os.path.join(os.path.expanduser("~"), ".minion", "network.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    _init_server_db(db_path)

    # Migrate existing DBs to add new agent columns (idempotent)
    from minion.network.db_schema import migrate_db
    migrate_db(db_path)

    if not token:
        from minion.defaults import resolve_cluster_token
        token = resolve_cluster_token()

    # Require auth token at startup — refuse to start without one unless explicitly allowed
    if not allow_no_auth:
        from minion.defaults import resolve_network_no_auth
        allow_no_auth = resolve_network_no_auth()

    if not token and not allow_no_auth:
        print("ERROR: No auth token configured. The server refuses to start without authentication.")
        print("")
        print("Set a cluster token using one of:")
        print("  1. --token <secret>                  (CLI argument)")
        print("  2. MINION_CLUSTER_TOKEN=<secret>      (environment variable)")
        print("")
        print("To explicitly run without auth (DEVELOPMENT ONLY):")
        print("  3. --no-auth                          (CLI flag)")
        print("  4. MINION_NETWORK_NO_AUTH=1            (environment variable)")
        raise SystemExit(1)

    # Build router and register all handler endpoints
    from minion.network.router import Router
    from minion.network.handlers import register_all
    router = Router()
    register_all(router)

    _Handler.db_path = db_path
    _Handler.token = token
    _Handler._router = router

    server = HTTPServer(("0.0.0.0", port), _Handler)

    # TLS setup — default on, opt-out with MINION_NETWORK_INSECURE=1
    from minion.defaults import resolve_network_insecure
    insecure = resolve_network_insecure()
    protocol = "http"
    if not insecure:
        import ssl
        tls = _tls_dir()
        cert_path = os.path.join(tls, "cert.pem")
        key_path = os.path.join(tls, "key.pem")
        if os.path.exists(cert_path) and os.path.exists(key_path):
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert_path, key_path)
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
            protocol = "https"
        else:
            print(f"WARNING: TLS certs not found at {tls}/")
            print("  Generate with: minion network gen-cert")
            print("  Or run insecure: MINION_NETWORK_INSECURE=1 minion network serve")
            print("  Falling back to plain HTTP.")

    print(f"minion network server listening on {protocol}://0.0.0.0:{port}")
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
