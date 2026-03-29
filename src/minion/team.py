"""Team mode — network-first multi-machine team coordination.

Treats the network API tier as the source of truth for team membership,
messaging, and roster. Eliminates the local-vs-global-vs-API confusion
by routing everything through one project-scoped team layer.

Purpose: Team mode — network-first multi-machine team coordination.
Rationale: Extracted into own module to provide unified team UX over the
  existing local/global/network tiers.
Responsibility: team join, team who, team send, team inbox. NOT responsible
  for local DB comms, daemon lifecycle, or crew YAML parsing."""

from __future__ import annotations

import os
import socket

from minion.api.daemon import _read_token, _token_file, start as api_start, status as api_status


def _get_team_client(server_url: str = ""):
    """Build a NetworkClient pointed at the team's API server.

    Resolution order for the server URL:
    1. Explicit server_url argument
    2. MINION_NETWORK_URL env var
    3. Local API server (https://127.0.0.1:8377) if running
    """
    from minion.network.client import NetworkClient
    from minion.defaults import resolve_network_url, resolve_network_insecure

    url = server_url or resolve_network_url()
    local_server = False
    if not url:
        # Check if local API server is running — use it as default
        # Accept both "running" (health OK) and "pid_alive" (process up, health probe may lack token)
        st = api_status()
        if st.get("status") in ("running", "pid_alive"):
            url = st.get("url", "https://127.0.0.1:8377")
            local_server = True

    if not url:
        return None, "No API server found. Start one with: minion api start"

    token = _read_token()
    # Local server uses self-signed TLS cert — always skip verification
    insecure = True if local_server else resolve_network_insecure()
    client = NetworkClient(base_url=url, token=token, insecure=insecure)
    return client, None


def _machine_id() -> str:
    return socket.gethostname()


def _project_name(project_dir: str) -> str:
    """Derive project name from the last path component."""
    return os.path.basename(os.path.abspath(project_dir))


def join(
    agent: str,
    agent_class: str = "coder",
    model: str = "",
    project_dir: str = "",
    server_url: str = "",
) -> dict:
    """Join a team — register on the network tier and verify connectivity.

    1. Ensure API server is reachable
    2. Register agent with machine_id, project_path, class, model
    3. Return roster
    """
    project_dir = project_dir or os.getcwd()
    project_path = os.path.abspath(project_dir)

    client, err = _get_team_client(server_url)
    if err:
        return {"error": err}

    # Register on network tier
    reg = client.register(
        name=agent,
        agent_class=agent_class,
        host=_machine_id(),
        project_path=project_path,
        machine_id=_machine_id(),
    )
    if "error" in reg:
        return reg

    # Fetch current roster for this project
    project = _project_name(project_dir)
    who = client.who()
    agents = who.get("agents", [])
    # Filter to same project
    team = [
        a for a in agents
        if _project_name(a.get("project_path", "")) == project
    ]

    return {
        "status": "joined",
        "agent": agent,
        "class": agent_class,
        "model": model,
        "machine": _machine_id(),
        "project": project,
        "project_path": project_path,
        "team_size": len(team),
        "roster": [
            {
                "name": a.get("name"),
                "machine": a.get("machine_id", ""),
                "class": a.get("agent_class", ""),
                "presence": a.get("presence", "unknown"),
            }
            for a in team
        ],
    }


def who(project_dir: str = "", server_url: str = "") -> dict:
    """List all team members for a project across all machines."""
    project_dir = project_dir or os.getcwd()
    project = _project_name(project_dir)

    client, err = _get_team_client(server_url)
    if err:
        return {"error": err}

    result = client.who()
    if "error" in result:
        return result

    agents = result.get("agents", [])
    team = [
        a for a in agents
        if _project_name(a.get("project_path", "")) == project
    ]

    return {
        "project": project,
        "agents": [
            {
                "name": a.get("name"),
                "machine": a.get("machine_id", ""),
                "class": a.get("agent_class", ""),
                "model": a.get("model", ""),
                "presence": a.get("presence", "unknown"),
                "availability": a.get("availability", "unknown"),
            }
            for a in team
        ],
    }


def send(from_agent: str, to_agent: str, message: str, server_url: str = "") -> dict:
    """Send a message via the network tier. No local/global distinction."""
    client, err = _get_team_client(server_url)
    if err:
        return {"error": err}

    return client.send(from_agent, to_agent, message)


def inbox(agent: str, server_url: str = "") -> dict:
    """Check unread messages for an agent on the network tier."""
    client, err = _get_team_client(server_url)
    if err:
        return {"error": err}

    return client.check_inbox(agent)
