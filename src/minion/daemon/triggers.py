"""Daemon trigger handlers — extracted from runner.py for visibility.

Each trigger has a clear contract:
- When it fires
- What it does
- What the daemon does next

Triggers:
    phoenix_down  — agent context exhausted (HP ≤ 5%), daemon respawns with fresh session
    stand_down    — leader dismissed the party (poll exit code 3), daemon exits
    standdown     — no available work after task completion, daemon polls cheaply (no API calls)
    signal        — SIGTERM/SIGINT received, daemon exits
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from threading import Event


def handle_phoenix_down(
    agent_name: str,
    hp_pct: float,
    write_state: Any,
    stop_event: "Event",
    alert_lead: Any,
) -> None:
    """Agent context exhausted. Write state, alert lead, signal inner loop to exit.

    Daemon outer loop catches 'phoenix_down' and respawns a fresh generation.
    Session data persists on disk for potential resume.
    """
    alert_lead(
        f"agent {agent_name} at {hp_pct:.0f}% HP — context exhausted. "
        f"Stopping daemon. Respawn to continue from assessment matrix."
    )
    write_state("phoenix_down", hp_pct=hp_pct)
    stop_event.set()


def handle_stand_down(
    agent_name: str,
    log: Any,
    stop_event: "Event",
) -> None:
    """Leader dismissed the party (poll returned exit code 3).

    Daemon exits entirely. No respawn.
    """
    log("stand_down detected — leader dismissed the party")
    stop_event.set()


def handle_standdown(
    agent_name: str,
    generation: int,
    last_task_id: Optional[int],
    log: Any,
    write_state: Any,
    alert_lead: Any = None,
) -> bool:
    """No available work after task completion. Stand down to idle polling.

    Daemon keeps polling cheaply (no API calls). Session data preserved.
    Alerts lead so they know the agent is no longer working.
    Returns True if stood down.
    """
    log(f"[standdown] no remaining work (last_task_id={last_task_id})")
    write_state("stood_down", generation=generation, last_task_id=last_task_id)
    if alert_lead:
        alert_lead(f"{agent_name} stood down — no remaining work")
    return True


def handle_wake_from_standdown(
    agent_name: str,
    poll_data: Dict[str, Any],
    last_task_id: Optional[int],
    log: Any,
    clear_session: Any,
) -> None:
    """Work arrived while stood down. Decide resume vs fresh session.

    Same task routed back or message → resume (context is valuable).
    New task → fresh session (clear session_id).
    """
    incoming_ids = {t.get("task_id") for t in poll_data.get("tasks", [])}
    messages = poll_data.get("messages", [])

    if messages or (last_task_id and last_task_id in incoming_ids):
        log("waking from standdown: resume session")
    else:
        log(f"waking from standdown: new task(s) {incoming_ids}, fresh session")
        clear_session()


def handle_signal(
    signum: int,
    log: Any,
    stop_event: "Event",
) -> None:
    """SIGTERM/SIGINT received. Clean exit.

    Daemon exits entirely. No respawn.
    """
    log(f"received signal {signum}, shutting down")
    stop_event.set()
