"""API server daemon lifecycle — start, stop, status, restart.
Manages the network API server as a background process.
State file: ~/.minion/api-server.json {pid, port, started_at, tls_enabled}
Log file: ~/.minion/api-server.log
PID tracked in state file — no separate .pid file needed.
Reuses patterns from crew/lifecycle.py (SIGTERM → grace → SIGKILL).

Purpose: API server daemon lifecycle — start, stop, status, restart.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: API server daemon lifecycle — start, stop, status, restart. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _minion_dir() -> Path:
    """~/.minion/ — global minion state directory."""
    return Path.home() / ".minion"


def _state_file() -> Path:
    return _minion_dir() / "api-server.json"


def _log_file() -> Path:
    return _minion_dir() / "api-server.log"


def _read_state() -> dict | None:
    """Read state file, return None if missing or corrupt."""
    sf = _state_file()
    if not sf.exists():
        return None
    try:
        return json.loads(sf.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _write_state(state: dict) -> None:
    """Write state file atomically."""
    sf = _state_file()
    sf.parent.mkdir(parents=True, exist_ok=True)
    tmp = sf.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.rename(sf)


def _token_file() -> Path:
    """Separate file for token — chmod 600, not in JSON state."""
    return _minion_dir() / ".api-token"


def _save_token(token: str) -> None:
    """Save token to restricted file (owner-only read/write)."""
    tf = _token_file()
    tf.parent.mkdir(parents=True, exist_ok=True)
    tf.write_text(token)
    tf.chmod(0o600)


def _read_token() -> str:
    """Read saved token. Returns empty string if missing."""
    tf = _token_file()
    if not tf.exists():
        return ""
    try:
        return tf.read_text().strip()
    except OSError:
        return ""


def _clear_state() -> None:
    """Remove state file and token file."""
    sf = _state_file()
    if sf.exists():
        sf.unlink()
    # Token file persists across restarts — only cleared on explicit stop
    # Actually keep token file for restart — don't clear it here


def _is_pid_alive(pid: int) -> bool:
    """Check if a process is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def start(port: int = 8377, token: str = "") -> dict:
    """Start the API server as a background daemon.

    PSEUDO: Check if already running (state file + PID alive) → error if so
    PSEUDO: Auto-generate TLS cert if missing (reduce first-time friction)
    PSEUDO: Fork child process via subprocess.Popen with start_new_session=True
    PSEUDO: Child runs `python -m minion.api.runner --port <port>`
    PSEUDO: Pass token to child via MINION_CLUSTER_TOKEN env var
    PSEUDO: Write state file with pid, port, started_at, tls_enabled, token
    PSEUDO: Return status dict
    """
    # Check if already running
    state = _read_state()
    if state and _is_pid_alive(state.get("pid", -1)):
        return {
            "error": f"API server already running (PID {state['pid']}, port {state.get('port', '?')}). "
            f"Stop first: minion api stop"
        }

    # Auto-generate TLS cert if missing
    tls_enabled = False
    from minion.defaults import resolve_network_insecure
    insecure = resolve_network_insecure()
    if not insecure:
        tls_dir = _minion_dir() / "tls"
        cert_path = tls_dir / "cert.pem"
        key_path = tls_dir / "key.pem"
        if not cert_path.exists() or not key_path.exists():
            # Auto-gen TLS cert
            from minion.network.server import gen_cert
            gen_cert()
        tls_enabled = cert_path.exists() and key_path.exists()

    # Ensure log directory exists
    log_path = _log_file()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Fork the server process
    # Runner is a separate module that imports and calls serve()
    log_fh = open(log_path, "a")  # noqa: SIM115
    env = os.environ.copy()
    # Pass token to child process via env var
    if token:
        env["MINION_CLUSTER_TOKEN"] = token
    proc = subprocess.Popen(
        [sys.executable, "-m", "minion.api.runner", "--port", str(port)],
        stdout=log_fh,
        stderr=log_fh,
        env=env,
        start_new_session=True,
    )
    # Don't close log_fh — child inherits the fd.
    # Detach from parent so Popen doesn't track the child.
    log_fh.close()

    # Brief wait to check if process started successfully
    time.sleep(0.5)
    if proc.poll() is not None:
        return {"error": f"API server failed to start. Check log: {log_path}"}

    # Write state file
    from minion.db import now_iso
    # Save token to separate restricted file (chmod 600) — not in JSON state
    if token:
        _save_token(token)

    state = {
        "pid": proc.pid,
        "port": port,
        "started_at": now_iso(),
        "tls_enabled": tls_enabled,
        "auth": bool(token),
    }
    _write_state(state)

    protocol = "https" if tls_enabled else "http"
    return {
        "status": "started",
        "pid": proc.pid,
        "port": port,
        "url": f"{protocol}://0.0.0.0:{port}",
        "tls": tls_enabled,
        "log": str(log_path),
    }


def stop() -> dict:
    """Stop the API server daemon.

    PSEUDO: Read state file → get PID
    PSEUDO: Send SIGTERM → wait up to 5s for graceful shutdown
    PSEUDO: If still alive after 5s → SIGKILL
    PSEUDO: Clear state file
    """
    state = _read_state()
    if not state:
        return {"status": "not_running", "message": "No API server state file found."}

    pid = state.get("pid", -1)
    if not _is_pid_alive(pid):
        _clear_state()
        return {"status": "not_running", "message": f"PID {pid} not found (stale state cleared)."}

    # SIGTERM → graceful shutdown
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _clear_state()
        return {"status": "stopped", "message": f"PID {pid} already gone."}

    # Wait up to 5s for graceful exit
    for _ in range(50):
        if not _is_pid_alive(pid):
            _clear_state()
            return {"status": "stopped", "pid": pid, "message": "Graceful shutdown."}
        time.sleep(0.1)

    # SIGKILL fallback
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        logger.error("Process %d already gone before SIGKILL", pid)

    _clear_state()
    return {"status": "stopped", "pid": pid, "message": "Forced shutdown (SIGKILL after 5s timeout)."}


def status() -> dict:
    """Check API server daemon status.

    PSEUDO: Read state file → get PID and port
    PSEUDO: Check PID alive (os.kill(pid, 0))
    PSEUDO: If alive, HTTP GET /health to verify serving
    PSEUDO: Report running/stopped/port/uptime
    """
    state = _read_state()
    if not state:
        return {"status": "stopped", "message": "No API server state file found."}

    pid = state.get("pid", -1)
    port = state.get("port", 8377)
    started_at = state.get("started_at", "")
    tls_enabled = state.get("tls_enabled", False)

    if not _is_pid_alive(pid):
        _clear_state()
        return {"status": "stopped", "message": f"PID {pid} not found (stale state cleared)."}

    # Process alive — try /health check
    health_ok = False
    try:
        import urllib.request
        import ssl
        protocol = "https" if tls_enabled else "http"
        url = f"{protocol}://127.0.0.1:{port}/health"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
            health_ok = resp.status == 200
    except (OSError, ValueError):
        pass  # health probe failed — process may be alive but not responding

    return {
        "status": "running" if health_ok else "pid_alive",
        "pid": pid,
        "port": port,
        "url": f"{'https' if tls_enabled else 'http'}://0.0.0.0:{port}",
        "tls": tls_enabled,
        "started_at": started_at,
        "health": "ok" if health_ok else "unreachable",
        "log": str(_log_file()),
    }


def restart(port: int | None = None, token: str | None = None) -> dict:
    """Restart the API server daemon.

    PSEUDO: Read current port and token from state (unless overridden)
    PSEUDO: stop() → start(port, token)
    """
    state = _read_state()
    if port is None:
        port = state.get("port", 8377) if state else 8377
    if token is None:
        token = _read_token()

    stop_result = stop()
    # Brief pause for port release
    time.sleep(0.5)
    start_result = start(port=port, token=token or "")

    return {
        "stop": stop_result,
        "start": start_result,
    }
