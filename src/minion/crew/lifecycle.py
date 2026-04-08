"""Stand down, retire, stop, and zone handoff — crew dismissal and agent lifecycle.

Purpose: Stand down, retire, stop, and zone handoff — crew dismissal and agent lifecycle.
Rationale: Extracted into own module for single-responsibility crew lifecycle management.
Responsibility: Stand down, retire, stop, and zone handoff — crew dismissal and agent lifecycle. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time

from minion.comms import deregister
from minion.db import get_db, now_iso

log = logging.getLogger(__name__)
from ._tmux import close_terminal_by_title, kill_all_crews, kill_tmux_pane_by_title
from minion.defaults import resolve_swarm_runtime_dir


def _kill_all_daemons(project_dir: str = "") -> None:
    """SIGTERM every daemon with a state file. Backlog #310: also fall back to
    matching daemon-run processes by command line in case state files are stale
    or missing (e.g. crash that left orphan daemons), and escalate to SIGKILL
    after a short grace period for any survivors.

    project_dir, if provided, anchors the swarm runtime dir lookup so that
    callers running from another cwd (or via `-C`) hit the right state dir.
    """
    state_dir = resolve_swarm_runtime_dir(project_dir or None) / "state"
    pids_killed: set[int] = set()
    agent_names: set[str] = set()

    if state_dir.is_dir():
        for state_file in state_dir.glob("*.json"):
            # Collect every agent name we know about in this project — used as
            # a fallback matcher for live daemons whose stored pid is stale.
            agent_names.add(state_file.stem)

            # Scope 1: file parsing — OSError (can't read) or bad JSON
            try:
                state = json.loads(state_file.read_text())
            except (OSError, json.JSONDecodeError) as e:
                log.error("Failed to read/parse daemon state %s: %s", state_file, e)
                continue

            pid = state.get("pid")
            if not (pid and isinstance(pid, int)):
                continue

            # Scope 2: kill — separate from file-parsing so PermissionError is visible
            try:
                os.kill(pid, signal.SIGTERM)
                pids_killed.add(pid)
            except ProcessLookupError:
                log.debug("Daemon PID %d in %s already gone", pid, state_file)
            except PermissionError:
                log.warning(
                    "PermissionError killing PID %d (from %s) — daemon may still be running",
                    pid,
                    state_file,
                )

    # Backlog #310 fallback: scan process table for daemon-run processes whose
    # --agent argv matches any agent we found state files for. This catches
    # orphans whose stored pid is stale (the common case — state files are
    # written once and not updated when daemons restart).
    extra_pids = _find_daemon_pids(project_dir, agent_names=agent_names)
    for pid in extra_pids:
        if pid in pids_killed:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            pids_killed.add(pid)
        except (ProcessLookupError, PermissionError) as e:
            log.debug("Could not SIGTERM extra daemon PID %d: %s", pid, e)

    if not pids_killed:
        return

    # Escalation: give daemons up to 2s to exit, then SIGKILL survivors.
    deadline = time.time() + 2.0
    while time.time() < deadline and pids_killed:
        survivors = set()
        for pid in pids_killed:
            try:
                os.kill(pid, 0)  # signal 0 = liveness probe
                survivors.add(pid)
            except OSError:
                pass  # exited
        pids_killed = survivors
        if pids_killed:
            time.sleep(0.1)
    for pid in pids_killed:
        try:
            os.kill(pid, signal.SIGKILL)
            log.warning("Backlog #310: SIGKILL daemon PID %d (ignored SIGTERM)", pid)
        except OSError:
            pass


def _find_daemon_pids(project_dir: str = "", agent_names: set[str] | None = None) -> list[int]:
    """Return PIDs of `minion daemon-run` processes, filtered by agent name.

    Uses ps + cmdline parsing rather than psutil to avoid a hard dep. The
    daemon-run argv always includes `--agent <name>`, but the config path it
    references is the GLOBAL crew yaml under ~/.minion-swarm — it does NOT
    include the project path, so project-path filtering misses everything.

    Strategy:
      - If agent_names is provided (the common case from _kill_all_daemons):
        match daemon-run processes whose argv mentions any of those names.
        This is project-scoped because the caller derived agent_names from
        the project's state dir.
      - If agent_names is empty/None: fall back to project-path matching
        (legacy behavior — finds nothing in practice but doesn't kill
        unrelated daemons either).
    """
    try:
        out = subprocess.run(
            ["ps", "-Ao", "pid=,command="],
            capture_output=True, text=True, check=False,
        )
    except (FileNotFoundError, OSError):
        return []
    pids: list[int] = []
    needle = "minion daemon-run"
    proj_filter = os.path.abspath(project_dir) if project_dir else ""
    name_filters = {f"--agent {n}" for n in (agent_names or set())}
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line or needle not in line:
            continue
        if name_filters:
            if not any(nf in line for nf in name_filters):
                continue
        elif proj_filter and proj_filter not in line:
            continue
        try:
            pid_str, _ = line.split(None, 1)
            pids.append(int(pid_str))
        except (ValueError, IndexError):
            continue
    return pids


def stand_down(agent_name: str, crew: str = "", project_dir: str = "") -> dict[str, object]:
    # SU-09: Precondition assertion
    assert agent_name, "agent_name must not be empty"
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

    # Kill all daemon processes from state dir — no YAML references needed.
    # Backlog #310: forward project_dir so the lookup honors `-C`.
    _kill_all_daemons(project_dir)

    if crew:
        # Backlog #305: tmux session name now includes a project hash so two
        # projects can run the same crew in parallel without colliding. Try
        # the project-scoped name first, then fall back to the legacy bare
        # name for sessions spawned before this fix landed.
        import hashlib
        cwd_for_hash = project_dir or os.getcwd()
        proj_hash = hashlib.sha1(os.path.abspath(cwd_for_hash).encode()).hexdigest()[:6]
        scoped_name = f"crew-{crew}-{proj_hash}"
        legacy_name = f"crew-{crew}"
        close_terminal_by_title(f"workers:{scoped_name}")
        close_terminal_by_title(f"lead:")
        killed_any = False
        for sess in (scoped_name, legacy_name):
            r = subprocess.run(["tmux", "kill-session", "-t", sess], capture_output=True, text=True)
            if r.returncode == 0:
                killed_any = True
            else:
                log.debug("tmux kill-session %s: %s", sess, r.stderr.strip())
        if not killed_any:
            log.warning("tmux kill-session for crew %s found no matching session", crew)
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


def stop_agent_process(agent: str) -> dict[str, object]:
    """Stop a single daemon agent: SIGTERM with 5s grace, then SIGKILL."""
    pids_dir = resolve_swarm_runtime_dir() / "pids"
    pid_file = pids_dir / f"{agent}.pid"
    if not pid_file.exists():
        return {"error": f"No PID file for '{agent}' — not running?"}
    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, 0)
    except OSError:
        pid_file.unlink(missing_ok=True)
        return {"error": f"Agent '{agent}' PID {pid} not alive — stale PID file removed."}
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
            time.sleep(0.2)
        except OSError:
            break
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError as e:
            log.error("SIGKILL failed for PID %d: %s", pid, e)
    pid_file.unlink(missing_ok=True)
    return {"status": "stopped", "agent": agent, "pid": pid}
