"""API server runner — entry point for the forked daemon child process.
Invoked as: python -m minion.api.runner --port 8377
Registers SIGTERM handler for graceful shutdown, then calls serve().
This module is what subprocess.Popen launches in daemon.py start().

Purpose: API server runner — entry point for the forked daemon child process.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: API server runner — entry point for the forked daemon child process. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import argparse
import signal
import sys
import threading


def main() -> None:
    """Parse args, register signal handler, run server.

    PSEUDO: Parse --port from argv
    PSEUDO: Register SIGTERM handler that calls server.shutdown()
    PSEUDO: Import and call serve() from network/server.py
    PSEUDO: serve() blocks until shutdown is triggered
    """
    parser = argparse.ArgumentParser(description="minion API server daemon runner")
    parser.add_argument("--port", type=int, default=8377)
    args = parser.parse_args()

    # Import serve here to avoid circular imports at module level
    from minion.network.server import serve

    # We can't register shutdown on the server object before it's created,
    # but serve() blocks forever. Use a threading.Event + signal to trigger
    # shutdown. We'll monkeypatch the serve function slightly — but actually
    # the simplest approach is to just let SIGTERM raise SystemExit, which
    # serve() catches via KeyboardInterrupt pattern. Let's use that.

    # SIGTERM → raise SystemExit so serve()'s except block runs shutdown()
    def _sigterm_handler(signum: int, frame) -> None:  # noqa: ANN001
        sys.exit(0)

    signal.signal(signal.SIGTERM, _sigterm_handler)

    print(f"[daemon] starting API server on port {args.port}", flush=True)
    try:
        serve(port=args.port)
    except SystemExit:
        print("[daemon] received SIGTERM, shutting down", flush=True)


if __name__ == "__main__":
    main()
