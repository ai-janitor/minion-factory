"""Main dashboard poll loop — 2-second refresh cycle with interactive navigation.
Entry point: run()
- Resolves DB path via env or cwd
- Catches KeyboardInterrupt and SIGTERM for clean exit
- Opens a fresh SQLite connection each cycle to get latest WAL snapshot
- Uses PRAGMA query_only=ON to guard against accidental writes
- Supports mouse clicks and keyboard for navigation between views

Purpose: Main dashboard poll loop — 2-second refresh cycle with interactive navigation.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Main dashboard poll loop — 2-second refresh cycle. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import logging
import os
import select
import signal
import sqlite3
import sys
import termios
import time
import tty

logger = logging.getLogger(__name__)

from minion.db.connection import connect
from minion.defaults import resolve_db_path
from minion.dashboard.queries import (
    fetch_activity, fetch_agents, fetch_backlog, fetch_tasks,
    fetch_all_backlog, fetch_lineage, fetch_task_to_backlog_map,
)
from minion.dashboard.render import (
    clear_and_print, render_screen, render_lineage_screen, render_browser_screen,
    ClickMap, BROWSER_SORT_MODES, sort_backlog,
)

# ANSI mouse tracking escape sequences (SGR extended mode — supports large terminals)
_MOUSE_ENABLE  = "\033[?1000h\033[?1006h"  # enable X11 mouse + SGR extended
_MOUSE_DISABLE = "\033[?1000l\033[?1006l"  # disable both


def _drain_stdin() -> None:
    """Drain all pending input from stdin.

    Called after a view switch to discard stale mouse events / keypresses
    that arrived during the transition. A single mouse click generates both
    a press (M) and release (m) event — the release may still be in-flight
    when we drain. The 150ms wait ensures the release event arrives before
    we flush, preventing its raw bytes from being misread as ESC.
    """
    time.sleep(0.15)
    while select.select([sys.stdin], [], [], 0)[0]:
        sys.stdin.read(1)


def _read_input() -> str | tuple[str, int, int] | None:
    """Non-blocking input read from stdin.

    Returns:
      - A key string (e.g. "q", "ESC", "l") for keyboard input
      - ("click", col, row) tuple for mouse clicks (SGR extended mode)
      - None if no input available

    Must be called with terminal in cbreak mode and mouse tracking enabled.
    """
    if not select.select([sys.stdin], [], [], 0)[0]:
        return None
    ch = sys.stdin.read(1)
    if ch == "\x1b":
        # Could be ESC, escape sequence, or mouse event
        if not select.select([sys.stdin], [], [], 0.05)[0]:
            return "ESC"
        ch2 = sys.stdin.read(1)
        if ch2 == "[":
            # Read the rest of the sequence
            seq = ""
            while True:
                if not select.select([sys.stdin], [], [], 0.02)[0]:
                    break
                c = sys.stdin.read(1)
                seq += c
                # SGR mouse: \033[<btn;col;rowM or \033[<btn;col;rowm
                # Regular escape sequence: ends with a letter
                if c.isalpha() or c in ("M", "m", "~"):
                    break
            # Parse SGR mouse event: <btn;col;rowM (press) or <btn;col;rowm (release)
            if seq.startswith("<") and (seq.endswith("M") or seq.endswith("m")):
                # Only handle press events (M), ignore release (m)
                if seq.endswith("M"):
                    try:
                        parts = seq[1:-1].split(";")
                        btn = int(parts[0])
                        col = int(parts[1])
                        row = int(parts[2])
                        # btn 0 = left click, 1 = middle, 2 = right
                        if btn == 0:
                            return ("click", col, row)
                    except (ValueError, IndexError) as e:
                        logger.error("Failed to parse mouse event: %s", e)
                return None  # ignore release events and parse failures
            # Other escape sequences (arrows etc) — ignore
            return None
        return None
    return ch


def run() -> None:
    """Poll loop: fetch DB → render → sleep → read input → repeat until signal.

    Three views:
    - dashboard: main overview — click backlog/activity rows or press L for browser
    - browser: paginated list of ALL backlog items — click or press 1-9
    - lineage: full lineage tree for a single backlog item

    Navigation:
    - Dashboard: click row or L = browser, 1-9 = backlog lineage, q = quit
    - Browser: click row or 1-9 = lineage, n/p = pages, ESC/q = dashboard
    - Lineage: L = browser, ESC/q = dashboard
    """
    db_path = resolve_db_path()
    work_dir = str(db_path.parent) if hasattr(db_path, 'parent') else os.path.dirname(str(db_path))
    _shutdown = False

    # View state
    view: str | tuple[str, int] = "dashboard"
    browser_page = 0
    browser_sort = "id"  # default sort: by ID descending

    def _handle_signal(sig: int, frame: object) -> None:
        nonlocal _shutdown
        _shutdown = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setcbreak(fd)
        # Enable mouse tracking
        sys.stdout.write(_MOUSE_ENABLE)
        sys.stdout.flush()

        # State tracked across render cycles
        displayed_backlog: list = []
        browser_items: list = []
        click_map: ClickMap = {}
        prev_view: str | tuple[str, int] | None = None

        while not _shutdown:
            # Drain stale input after view switches (prevents double-click bounce)
            if view != prev_view:
                _drain_stdin()
                prev_view = view

            try:
                conn = connect(db_path, timeout=2)
                conn.execute("PRAGMA query_only = ON")

                try:
                    width, height = os.get_terminal_size()
                except OSError:
                    width, height = 120, 40

                if view == "dashboard":
                    tasks    = fetch_tasks(conn)
                    agents   = fetch_agents(conn)
                    activity = fetch_activity(conn)
                    backlog  = fetch_backlog(conn)
                    displayed_backlog = list(backlog) if backlog else []
                    # Map activity task IDs back to backlog IDs for click targets
                    task_ids = [row["task_id"] for row in activity]
                    task_to_backlog = fetch_task_to_backlog_map(conn, task_ids)
                    conn.close()
                    screen, click_map = render_screen(
                        tasks, agents, activity, width, height,
                        work_dir=work_dir, backlog=backlog,
                        activity_task_to_backlog=task_to_backlog,
                    )
                    clear_and_print(screen)

                elif view == "browser":
                    browser_items = sort_backlog(list(fetch_all_backlog(conn)), browser_sort)
                    conn.close()
                    screen, click_map = render_browser_screen(
                        browser_items, width, height, page=browser_page,
                        sort_by=browser_sort,
                    )
                    clear_and_print(screen)

                elif isinstance(view, tuple) and view[0] == "lineage":
                    backlog_id = view[1]
                    lineage = fetch_lineage(conn, backlog_id, work_dir=work_dir)
                    conn.close()
                    click_map = {}
                    screen = render_lineage_screen(lineage, width, height)
                    clear_and_print(screen)

                else:
                    conn.close()

            except sqlite3.OperationalError:
                print("\033[2J\033[H  Waiting for minion.db...\n", end="", flush=True)

            # Sleep in short increments, checking for input (keys + mouse)
            for _ in range(20):
                if _shutdown:
                    break
                inp = _read_input()
                if inp is None:
                    time.sleep(0.1)
                    continue

                # Handle mouse click
                if isinstance(inp, tuple) and inp[0] == "click":
                    _, col, row = inp
                    if row in click_map:
                        action = click_map[row]
                        if action[0] == "lineage":
                            view = ("lineage", action[1])
                            break
                    continue

                # Handle keyboard
                key = inp
                if view == "dashboard":
                    if key == "q":
                        _shutdown = True
                        break
                    elif key in ("l", "L"):
                        browser_page = 0
                        view = "browser"
                        break
                    elif key.isdigit() and key != "0":
                        idx = int(key) - 1
                        if 0 <= idx < len(displayed_backlog):
                            view = ("lineage", displayed_backlog[idx]["id"])
                            break

                elif view == "browser":
                    if key in ("q", "ESC"):
                        view = "dashboard"
                        break
                    elif key == "n":
                        browser_page += 1
                        break
                    elif key == "p":
                        browser_page = max(0, browser_page - 1)
                        break
                    elif key == "s":
                        # Cycle sort: id → type → priority → id → ...
                        idx_s = BROWSER_SORT_MODES.index(browser_sort)
                        browser_sort = BROWSER_SORT_MODES[(idx_s + 1) % len(BROWSER_SORT_MODES)]
                        browser_page = 0  # reset to page 1 on sort change
                        break
                    elif key.isdigit() and key != "0":
                        idx = int(key) - 1
                        start = browser_page * 9
                        page_items = browser_items[start:start + 9]
                        if 0 <= idx < len(page_items):
                            view = ("lineage", page_items[idx]["id"])
                            break

                elif isinstance(view, tuple) and view[0] == "lineage":
                    if key in ("q", "ESC"):
                        view = "dashboard"
                        break
                    elif key in ("l", "L"):
                        view = "browser"
                        break

    finally:
        # Disable mouse tracking and restore terminal
        sys.stdout.write(_MOUSE_DISABLE)
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
