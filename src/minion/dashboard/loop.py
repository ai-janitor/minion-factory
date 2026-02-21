"""Main dashboard poll loop — 2-second refresh cycle.

Entry point: run()
- Resolves DB path via env or cwd
- Catches KeyboardInterrupt and SIGTERM for clean exit
- Opens a fresh SQLite connection each cycle to get latest WAL snapshot
- Uses PRAGMA query_only=ON to guard against accidental writes
"""

from __future__ import annotations

import os
import signal
import sqlite3
import time

from minion.defaults import resolve_db_path
from minion.dashboard.queries import fetch_activity, fetch_agents, fetch_tasks
from minion.dashboard.render import clear_and_print, render_screen


def run() -> None:
    """Poll loop: fetch DB → render → sleep 2s → repeat until signal."""
    db_path = resolve_db_path()
    _shutdown = False

    def _handle_signal(sig: int, frame: object) -> None:
        nonlocal _shutdown
        _shutdown = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    while not _shutdown:
        try:
            conn = sqlite3.connect(db_path, timeout=2)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA query_only = ON")
            tasks    = fetch_tasks(conn)
            agents   = fetch_agents(conn)
            activity = fetch_activity(conn)
            conn.close()
            try:
                width, height = os.get_terminal_size()
            except OSError:
                width, height = 120, 40
            screen = render_screen(tasks, agents, activity, width, height)
            clear_and_print(screen)
        except sqlite3.OperationalError:
            # DB not yet created or locked — show waiting state
            print("\033[2J\033[H  Waiting for minion.db...\n", end="", flush=True)
        time.sleep(2)
