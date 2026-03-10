"""API GLOBAL coordinator server — stdlib http.server, zero external deps.

Endpoints delegated to handlers/ via router.py dispatch table.
Core endpoints (6): /health, /who, /register, /send, /inbox/{agent}, /messages/recent
Dashboard endpoints: /projects, /projects/{name}/agents|tasks|messages|raid-log, etc.
See router.py for the full route table and handlers/ for endpoint implementations.
"""

from __future__ import annotations

import hmac
import json
import os
import sqlite3
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from minion.db.connection import connect as _db_connect

_DB_LOCK = threading.Lock()


def _get_server_db(db_path: str) -> sqlite3.Connection:
    return _db_connect(db_path)


def _init_server_db(db_path: str) -> None:
    # PSEUDO: Use db_schema.init_db() for fresh installs, then migrate_to_composite_pk() for upgrades
    from minion.network.db_schema import init_db, migrate_db, migrate_to_composite_pk
    init_db(db_path)
    migrate_db(db_path)
    migrate_to_composite_pk(db_path)


def _check_token(headers: dict, expected: str) -> bool:
    """Validate Bearer token from Authorization header."""
    if not expected:
        return True  # no auth configured
    auth = headers.get("Authorization", "")
    return hmac.compare_digest(auth, f"Bearer {expected}")


class _Handler(BaseHTTPRequestHandler):
    """Request handler — routes to endpoint functions."""

    db_path: str = ""
    token: str = ""

    def log_message(self, format, *args):
        """Structured HTTP request logging — method, path, status, client."""
        import json as _json
        from datetime import datetime
        msg = format % args if args else format
        print(_json.dumps({
            "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "level": "INFO",
            "component": "http",
            "client": self.client_address[0],
            "message": msg,
        }), flush=True)

    def _json_response(self, status: int, data: dict) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    _MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB — guard against DoS via large Content-Length

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        if length > self._MAX_BODY_SIZE:
            self._json_response(413, {"error": f"Request body too large (max {self._MAX_BODY_SIZE} bytes)"})
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
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Dashboard HTML — served without auth (JS handles token via localStorage)
        if path == "" or path == "/":
            from minion.network.dashboard import DASHBOARD_HTML
            self._html_response(DASHBOARD_HTML)
            return

        # API endpoints — auth required
        if not _check_token(dict(self.headers), self.token):
            self._json_response(401, {"error": "Unauthorized"})
            return

        # Delegate to router
        if self._router:
            handler_fn, params = self._router.route_get(path)
            if handler_fn:
                handler_fn(self, self.db_path, **params)
                return

        self._json_response(404, {"error": f"Not found: {path}"})

    # POST paths that skip auth (login must work without a token)
    _POST_NO_AUTH = {"/api/login"}

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path not in self._POST_NO_AUTH:
            if not _check_token(dict(self.headers), self.token):
                self._json_response(401, {"error": "Unauthorized"})
                return

        # Delegate to router
        if self._router:
            handler_fn, params = self._router.route_post(path)
            if handler_fn:
                handler_fn(self, self.db_path, **params)
                return

        self._json_response(404, {"error": f"Not found: {path}"})


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


def serve(port: int = 8377, db_path: str = "", token: str = "") -> None:
    """Start the API GLOBAL coordinator server with TLS by default.

    TLS uses ~/.minion/tls/cert.pem + key.pem (generate with gen_cert()).
    Set MINION_NETWORK_INSECURE=1 to run plain HTTP (dev only).

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

    # Migrate existing DBs to add new agent columns (idempotent)
    from minion.network.db_schema import migrate_db
    migrate_db(db_path)

    if not token:
        token = os.environ.get("MINION_CLUSTER_TOKEN", "")

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
    insecure = os.environ.get("MINION_NETWORK_INSECURE", "") == "1"
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
