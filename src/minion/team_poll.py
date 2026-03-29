"""Team poll — foreground delivery loop for coordinator messages.

Polls the coordinator inbox at regular intervals, prints messages to
the terminal as they arrive, and marks them read only after display.

Foreground poll = delivery. Background poll = notify-only (no mark-read).

Purpose: Live message delivery loop for team/coordinator comms.
Rationale: Separates polling from inbox checking — poll is a long-running
  delivery process, inbox is a one-shot query.
Responsibility: Poll loop, message display, mark-read after delivery.
  NOT responsible for inbox semantics, aggregation, or history."""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path


# Poller state file — tracks active pollers to prevent duplicates
def _poller_dir() -> Path:
    return Path.home() / ".minion" / "pollers"


def _poller_file(agent: str) -> Path:
    return _poller_dir() / f"{agent}.json"


def register_poller(agent: str, mode: str = "foreground") -> dict | None:
    """Register this process as the active poller for an agent.

    Returns error dict if a poller is already running for this agent.
    """
    pf = _poller_file(agent)
    pf.parent.mkdir(parents=True, exist_ok=True)

    # Check for existing poller
    if pf.exists():
        try:
            state = json.loads(pf.read_text())
            pid = state.get("pid", -1)
            # Check if process is still alive
            try:
                os.kill(pid, 0)
                return {"error": f"Poller already running for {agent} (PID {pid}, mode: {state.get('mode')}). "
                        f"Stop it first: minion team poll-stop --agent {agent}"}
            except (ProcessLookupError, PermissionError):
                pass  # stale file — process dead
        except (json.JSONDecodeError, OSError):
            pass

    # Register this process
    state = {
        "agent": agent,
        "pid": os.getpid(),
        "mode": mode,
        "started_at": datetime.now().isoformat(),
    }
    pf.write_text(json.dumps(state, indent=2))
    return None


def unregister_poller(agent: str) -> None:
    """Remove poller registration."""
    pf = _poller_file(agent)
    if pf.exists():
        pf.unlink()


def list_pollers() -> list[dict]:
    """List all registered pollers with liveness check."""
    pd = _poller_dir()
    if not pd.exists():
        return []

    pollers = []
    for f in pd.glob("*.json"):
        try:
            state = json.loads(f.read_text())
            pid = state.get("pid", -1)
            alive = False
            try:
                os.kill(pid, 0)
                alive = True
            except (ProcessLookupError, PermissionError):
                pass
            state["alive"] = alive
            if not alive:
                f.unlink()  # clean up stale
            else:
                pollers.append(state)
        except (json.JSONDecodeError, OSError):
            f.unlink()

    return pollers


def stop_poller(agent: str) -> dict:
    """Stop a running poller for an agent."""
    pf = _poller_file(agent)
    if not pf.exists():
        return {"status": "not_running", "agent": agent}

    try:
        state = json.loads(pf.read_text())
        pid = state.get("pid", -1)
        try:
            os.kill(pid, signal.SIGTERM)
            pf.unlink()
            return {"status": "stopped", "agent": agent, "pid": pid}
        except ProcessLookupError:
            pf.unlink()
            return {"status": "not_running", "agent": agent, "message": "Stale poller cleared"}
    except (json.JSONDecodeError, OSError):
        pf.unlink()
        return {"status": "not_running", "agent": agent}


def run_poll_loop(
    agent: str,
    server_url: str = "",
    channel: str = "",
    interval: int = 5,
    mode: str = "foreground",
) -> None:
    """Run the poll loop. Blocks until interrupted.

    foreground mode: prints messages, marks read after display.
    notify mode: prints notification, does NOT mark read.
    """
    from minion.team import _get_team_client

    # Register poller (prevents duplicates)
    err = register_poller(agent, mode=mode)
    if err:
        print(json.dumps(err), file=sys.stderr)
        sys.exit(1)

    # Handle graceful shutdown
    running = True
    def _handle_signal(sig, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Track notified IDs to prevent duplicate notifications
    notified_msg_ids: set[int] = set()
    notified_task_ids: set[int] = set()
    seen_task_states: dict[int, str] = {}  # task_id → last seen status

    try:
        while running:
            try:
                client, client_err = _get_team_client(server_url)
                if client_err:
                    time.sleep(interval)
                    continue

                # --- Check messages ---
                result = client.check_inbox(agent, channel=channel, peek=True)
                messages = result.get("messages", [])

                if messages:
                    if mode == "foreground":
                        for msg in messages:
                            _print_message(msg)
                        ids = [m["id"] for m in messages if isinstance(m.get("id"), int)]
                        if ids:
                            client.mark_read(agent, ids, read_via="team_poll_foreground")
                    else:
                        new_msgs = [m for m in messages if m.get("id") not in notified_msg_ids]
                        if new_msgs:
                            count = len(new_msgs)
                            senders = list({m.get("from_agent", "?") for m in new_msgs})
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] {count} unread from {', '.join(senders)}", flush=True)
                            for m in new_msgs:
                                mid = m.get("id")
                                if mid:
                                    notified_msg_ids.add(mid)

                # --- Check tasks assigned to this agent ---
                try:
                    tasks_result = client._request("GET", f"/team/tasks?assigned_to={agent}")
                    tasks = tasks_result.get("tasks", [])
                    for task in tasks:
                        tid = task.get("id")
                        status = task.get("status", "")
                        title = task.get("title", "")
                        if tid is None:
                            continue

                        prev_status = seen_task_states.get(tid)
                        if prev_status is None:
                            # New task we haven't seen before
                            if tid not in notified_task_ids:
                                _print_task_notification(task, "new")
                                notified_task_ids.add(tid)
                        elif prev_status != status:
                            # Status changed
                            _print_task_notification(task, f"{prev_status} → {status}")

                        seen_task_states[tid] = status
                except Exception:
                    pass  # task check is best-effort

            except Exception as e:
                print(f"[poll error] {e}", file=sys.stderr, flush=True)

            time.sleep(interval)
    finally:
        unregister_poller(agent)


def _print_task_notification(task: dict, change: str) -> None:
    """Print a task notification in operator-friendly format."""
    tid = task.get("id", "?")
    title = task.get("title", "")
    status = task.get("status", "")
    created_by = task.get("created_by_agent", "")
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{ts}] TASK #{tid} ({change}): {title}", flush=True)
    if created_by:
        print(f"  from: {created_by}  status: {status}", flush=True)
    print("---", flush=True)


def _print_message(msg: dict) -> None:
    """Print a message in operator-friendly format."""
    ts = msg.get("timestamp", "")
    if "T" in ts:
        ts = ts.split("T")[1][:8]  # HH:MM:SS
    sender = msg.get("from_agent", "?")
    content = msg.get("content", "")
    channel_id = msg.get("channel_id")
    ch = f" #{channel_id}" if channel_id else ""
    print(f"\n[{ts}]{ch} from {sender}:", flush=True)
    print(content, flush=True)
    print("---", flush=True)
