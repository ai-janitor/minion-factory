"""Local team identity persistence — stores joined coordinator/channel/agent state.

When an agent joins a team, the identity (coordinator URL, channel, agent name,
agent_uuid) is saved locally under ~/.minion/team/. This allows subsequent
commands to work without re-specifying --agent or --channel.

Structure:
  ~/.minion/team/identities.json — list of joined identities
  Each identity keyed by (coordinator_url, channel, agent_name).

Purpose: Persist local team identity so CLI commands are stateful.
Rationale: CWD alone is not enough when multiple agents share one repo.
Responsibility: Read/write local identity files. NOT responsible for
  coordinator communication or remote profile management."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _identities_file() -> Path:
    return Path.home() / ".minion" / "team" / "identities.json"


def _read_identities() -> list[dict]:
    """Read all saved team identities."""
    f = _identities_file()
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_identities(identities: list[dict]) -> None:
    """Write team identities atomically."""
    f = _identities_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(identities, indent=2))
    tmp.rename(f)


def save_identity(
    coordinator_url: str,
    channel: str,
    agent_name: str,
    agent_uuid: str,
    agent_class: str = "",
    project_path: str = "",
) -> None:
    """Save or update a team identity after joining.

    Keyed by (coordinator_url, channel, agent_name) — upserts if exists.
    """
    from datetime import datetime
    now = datetime.now().isoformat()
    identities = _read_identities()

    # Find existing entry to update
    key = (coordinator_url.rstrip("/"), channel, agent_name)
    for i, entry in enumerate(identities):
        if (entry.get("coordinator_url", "").rstrip("/"),
            entry.get("channel"),
            entry.get("agent_name")) == key:
            # Update existing
            identities[i].update({
                "agent_uuid": agent_uuid,
                "agent_class": agent_class,
                "project_path": project_path,
                "last_contact": now,
            })
            _write_identities(identities)
            return

    # New identity
    identities.append({
        "coordinator_url": coordinator_url.rstrip("/"),
        "channel": channel,
        "agent_name": agent_name,
        "agent_uuid": agent_uuid,
        "agent_class": agent_class,
        "project_path": project_path,
        "last_contact": now,
    })
    _write_identities(identities)


def get_identity(
    channel: str = "",
    agent_name: str = "",
    coordinator_url: str = "",
) -> dict | None:
    """Find a saved identity by any combination of filters.

    Returns the most specific match, or None.
    """
    identities = _read_identities()
    if not identities:
        return None

    for entry in identities:
        match = True
        if channel and entry.get("channel") != channel:
            match = False
        if agent_name and entry.get("agent_name") != agent_name:
            match = False
        if coordinator_url and entry.get("coordinator_url", "").rstrip("/") != coordinator_url.rstrip("/"):
            match = False
        if match:
            return entry

    return None


def get_identity_for_project(project_dir: str = "") -> dict | None:
    """Find a saved identity matching a project directory (by channel name)."""
    project_dir = project_dir or os.getcwd()
    channel = os.path.basename(os.path.abspath(project_dir))
    return get_identity(channel=channel)


def list_identities() -> list[dict]:
    """List all saved team identities."""
    return _read_identities()


def list_coordinators() -> list[str]:
    """List distinct coordinator URLs from saved identities."""
    identities = _read_identities()
    urls = list(dict.fromkeys(e.get("coordinator_url", "") for e in identities if e.get("coordinator_url")))
    return urls


def remove_identity(coordinator_url: str, channel: str, agent_name: str) -> bool:
    """Remove a saved identity. Returns True if found and removed."""
    identities = _read_identities()
    key = (coordinator_url.rstrip("/"), channel, agent_name)
    new = [
        e for e in identities
        if (e.get("coordinator_url", "").rstrip("/"), e.get("channel"), e.get("agent_name")) != key
    ]
    if len(new) < len(identities):
        _write_identities(new)
        return True
    return False
