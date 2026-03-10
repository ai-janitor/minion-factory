"""Centralized logging configuration for minion-factory.

Purpose: Single place to configure Python's logging system for the minion CLI
         and library. Eliminates the three competing patterns found across the
         codebase: logging.getLogger (3 files), print() (57 calls/23 files),
         click.echo (42 calls/9 files).
Rationale: Without basicConfig, loggers silently discard all records. With it,
           WARNING+ goes to stderr by default — matching the intent of the 57
           print(WARNING:..., file=sys.stderr) calls this replaces.
Responsibility: Call configure_logging() once at CLI startup. Library modules
                just do `log = logging.getLogger(__name__)` — no setup needed.
Organization: configure_logging() → call from cli/main.py; get_logger() → sugar.

Convention:
  CLI output (user-facing):  click.echo() or minion.output.output() — NOT logging
  Internal diagnostics:      log.warning() / log.error() — NOT print(WARNING:...)
  Progress / status dots:    print() is acceptable for interactive progress output

Files converted: tasks/loader.py, missions/party.py, monitoring.py,
  providers/codex.py, providers/gemini.py, comms/delivery.py, comms/register.py,
  crew/lifecycle.py, crew/spawn.py, crew/_tmux.py, crew/daemon.py
Remaining print() uses (intentional):
  - network/server.py: startup banner (server entrypoint, not library)
  - dashboard/render.py: clear_and_print() terminal UI
  - daemon/runner/__init__.py: progress dots
"""

from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    """Configure root logger for the minion CLI.

    Sets WARNING level by default; DEBUG if MINION_DEBUG env var is set.
    Output goes to stderr — keeps stdout clean for JSON / machine-readable output.
    Safe to call multiple times (logging.basicConfig is idempotent after first call).
    """
    # Purpose: bootstrap the logging system once at CLI startup
    # Pseudo: read MINION_DEBUG → set level; call basicConfig → handlers attached
    level = logging.DEBUG if os.environ.get("MINION_DEBUG") else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=None,  # defaults to stderr
    )
    # Silence noisy third-party libraries unless debug
    if level != logging.DEBUG:
        logging.getLogger("watchdog").setLevel(logging.ERROR)
        logging.getLogger("urllib3").setLevel(logging.ERROR)


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper: return a named logger.

    Usage in library modules:
        from minion.logging_setup import get_logger
        log = get_logger(__name__)
        log.warning("something went wrong: %s", exc)
    """
    return logging.getLogger(name)
