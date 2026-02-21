"""Stand down, retire, and zone handoff — crew dismissal and agent lifecycle."""

from __future__ import annotations

import json
import os
import signal
import subprocess

from minion.comms import deregister
from minion.db import get_db, now_iso
from minion.crew._tmux import close_terminal_by_title, kill_all_crews, kill_tmux_pane_by_title
from minion.defaults import resolve_swarm_runtime_dir


def _kill_all_daemons(project_dir: str = "") -> None:
    """SIGTERM every daemon with a state file — no YAML needed."""
    state_dir = resolve_swarm_runtime_dir(project_dir or None) / "state"
    if not state_dir.is_dir():
        return
    for state_file in state_dir.glob("*.json"):
        try:
            state = json.loads(state_file.read_text())
            pid = state.get("pid")
            if pid and isinstance(pid, int):
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except (OSError, json.JSONDecodeError):
            pass


def stand_down(agent_name: str, crew: str = "") -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead-class agents can stand_down. '{agent_name}' is '{row['agent_class']}'."}

        cursor.execute(
            """INSERT INTO flags (key, value, set_by, set_at)
               VALUES ('stand_down', '1', ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = '1', set_by = excluded.set_by, set_at = excluded.set_at""",
            (agent_name, now),
        )
        conn.commit()
    finally:
        conn.close()

    # Deregister agents — scope to crew if specified, otherwise all
    conn2 = get_db()
    try:
        cursor2 = conn2.cursor()
        if crew:
            cursor2.execute(
                "SELECT name, pid FROM agents WHERE crew = ? AND name != ?",
                (crew, agent_name),
            )
        else:
            cursor2.execute(
                "SELECT name, pid FROM agents WHERE name != ?",
                (agent_name,),
            )
        all_agents = [row["name"] for row in cursor2.fetchall()]
    finally:
        conn2.close()

    for a in all_agents:
        deregister(a)
        kill_tmux_pane_by_title(a)

    # Kill all daemon processes from state dir — no YAML references needed
    _kill_all_daemons()

    if crew:
        close_terminal_by_title(f"workers:crew-{crew}")
        close_terminal_by_title(f"lead:")
        r = subprocess.run(["tmux", "kill-session", "-t", f"crew-{crew}"], capture_output=True, text=True)
        if r.returncode != 0:
            import sys
            print(f"WARNING: tmux kill-session crew-{crew} failed: {r.stderr.strip()}", file=sys.stderr)
        return {"status": "dismissed", "crew": crew}
    else:
        kill_all_crews()
        return {"status": "dismissed", "crew": "all"}


def retire_agent(agent_name: str, requesting_agent: str) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (requesting_agent,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{requesting_agent}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead-class agents can retire agents. '{requesting_agent}' is '{row['agent_class']}'."}

        cursor.execute(
            """INSERT INTO agent_retire (agent_name, set_at, set_by)
               VALUES (?, ?, ?)
               ON CONFLICT(agent_name) DO UPDATE SET set_at = excluded.set_at, set_by = excluded.set_by""",
            (agent_name, now, requesting_agent),
        )
        conn.commit()
    finally:
        conn.close()

    deregister(agent_name)
    kill_tmux_pane_by_title(agent_name)

    return {"status": "retired", "agent": agent_name, "by": requesting_agent}


def interrupt_agent(agent_name: str, requesting_agent: str) -> dict[str, object]:
    """Set interrupt flag in DB. The daemon's run loop detects this and
    terminates its own child process — the daemon itself stays alive."""
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (requesting_agent,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{requesting_agent}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead-class agents can interrupt. '{requesting_agent}' is '{row['agent_class']}'."}

        cursor.execute(
            """INSERT INTO agent_interrupt (agent_name, set_at, set_by)
               VALUES (?, ?, ?)
               ON CONFLICT(agent_name) DO UPDATE SET set_at = excluded.set_at, set_by = excluded.set_by""",
            (agent_name, now, requesting_agent),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "status": "interrupt_set",
        "agent": agent_name,
        "by": requesting_agent,
        "note": "Daemon will terminate current invocation on next check cycle.",
    }


def hand_off_zone(
    from_agent: str,
    to_agents: str,
    zone: str,
) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT name FROM agents WHERE name = ?", (from_agent,))
        if not cursor.fetchone():
            return {"error": f"BLOCKED: Agent '{from_agent}' not registered."}

        targets = [a.strip() for a in to_agents.split(",") if a.strip()]
        if not targets:
            return {"error": "BLOCKED: No target agents specified."}

        missing = []
        for t in targets:
            cursor.execute("SELECT name FROM agents WHERE name = ?", (t,))
            if not cursor.fetchone():
                missing.append(t)
        if missing:
            return {"error": f"BLOCKED: Agents not registered: {', '.join(missing)}"}

        for t in targets:
            cursor.execute(
                "UPDATE agents SET current_zone = ?, last_seen = ? WHERE name = ?",
                (zone, now, t),
            )

        cursor.execute(
            "UPDATE agents SET current_zone = NULL, last_seen = ? WHERE name = ?",
            (now, from_agent),
        )

        from minion.fs import atomic_write_file, raid_log_file_path
        entry = f"ZONE HANDOFF: {from_agent} → {', '.join(targets)} | zone: {zone}"
        entry_file = raid_log_file_path(from_agent, "high")
        atomic_write_file(entry_file, entry)

        cursor.execute(
            """INSERT INTO raid_log (agent_name, entry_file, priority, created_at)
               VALUES (?, ?, 'high', ?)""",
            (from_agent, entry_file, now),
        )

        conn.commit()

        return {
            "status": "handed_off",
            "from": from_agent,
            "to": targets,
            "zone": zone,
        }
    finally:
        conn.close()
