"""Team mode — network-first multi-machine team coordination.

Treats the network API tier as the source of truth for team membership,
messaging, and roster. Uses first-class channels as the collaboration scope.
Eliminates the local-vs-global-vs-API confusion by routing everything
through one channel-scoped team layer.

Purpose: Team mode — network-first multi-machine team coordination.
Rationale: Extracted into own module to provide unified team UX over the
  existing local/global/network tiers.
Responsibility: team join, team who, team send, team inbox, team channels.
  NOT responsible for local DB comms, daemon lifecycle, or crew YAML parsing."""

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

    # Fallback: check configured remote profiles (set via `minion api set-remote`)
    if not url:
        from minion.api.remotes import get_remote_client
        client, err = get_remote_client()
        if client:
            return client, None

    if not url:
        return None, "No API server found. Start one with: minion coordinator start\n" \
            "Or configure a remote: minion api set-remote https://host:8377"

    token = _read_token()
    # Local server uses self-signed TLS cert — always skip verification
    insecure = True if local_server else resolve_network_insecure()
    client = NetworkClient(base_url=url, token=token, insecure=insecure)
    return client, None


def _machine_id() -> str:
    return socket.gethostname()


def _channel_name(project_dir: str) -> str:
    """Derive channel name from the last path component of the project dir."""
    return os.path.basename(os.path.abspath(project_dir))


def join(
    agent: str,
    agent_class: str = "coder",
    model: str = "",
    project_dir: str = "",
    channel: str = "",
    server_url: str = "",
) -> dict:
    """Join a team — register on the network tier and join a channel.

    1. Ensure API server is reachable
    2. Register agent with machine_id, project_path, class, model
    3. Explicitly join the channel
    4. Return channel roster
    """
    project_dir = project_dir or os.getcwd()
    project_path = os.path.abspath(project_dir)
    channel = channel or _channel_name(project_dir)

    client, err = _get_team_client(server_url)
    if err:
        return {"error": err}

    # Register on network tier (also auto-joins channel via project_path bridge)
    reg = client.register(
        name=agent,
        agent_class=agent_class,
        host=_machine_id(),
        project_path=project_path,
        machine_id=_machine_id(),
    )
    if "error" in reg:
        return reg

    # Explicitly join channel (canonical path, idempotent)
    role = "lead" if agent_class == "lead" else "member"
    client.join_channel(channel=channel, agent=agent, machine_id=_machine_id(), role=role)

    # Fetch channel roster
    members_result = client.channel_members(channel)
    members = members_result.get("members", [])

    # Extract stable UUID from registration response
    agent_uuid = reg.get("agent_uuid", "")

    return {
        "status": "joined",
        "agent": agent,
        "agent_uuid": agent_uuid,
        "class": agent_class,
        "model": model,
        "machine": _machine_id(),
        "channel": channel,
        "project_path": project_path,
        "team_size": len(members),
        "roster": [
            {
                "name": m.get("name"),
                "machine": m.get("machine", ""),
                "class": m.get("class", ""),
                "role": m.get("role", ""),
                "presence": m.get("presence", "unknown"),
            }
            for m in members
        ],
    }


def who(project_dir: str = "", channel: str = "", server_url: str = "") -> dict:
    """List all team members for a channel across all machines."""
    project_dir = project_dir or os.getcwd()
    channel = channel or _channel_name(project_dir)

    client, err = _get_team_client(server_url)
    if err:
        return {"error": err}

    result = client.channel_members(channel)
    if "error" in result:
        return result

    members = result.get("members", [])
    return {
        "channel": channel,
        "agents": [
            {
                "name": m.get("name"),
                "machine": m.get("machine", ""),
                "class": m.get("class", ""),
                "model": m.get("model", ""),
                "role": m.get("role", ""),
                "presence": m.get("presence", "unknown"),
            }
            for m in members
        ],
    }


def send(
    from_agent: str, to_agent: str, message: str,
    project_dir: str = "", channel: str = "", server_url: str = "",
) -> dict:
    """Send a message via the network tier, scoped to a channel."""
    project_dir = project_dir or os.getcwd()
    channel = channel or _channel_name(project_dir)

    client, err = _get_team_client(server_url)
    if err:
        return {"error": err}

    return client.send(from_agent, to_agent, message, channel=channel)


def inbox(
    agent: str, project_dir: str = "", channel: str = "", server_url: str = "",
) -> dict:
    """Check unread messages for an agent, optionally scoped to a channel."""
    client, err = _get_team_client(server_url)
    if err:
        return {"error": err}

    if not channel and project_dir:
        channel = _channel_name(project_dir)

    return client.check_inbox(agent, channel=channel)


def channels(server_url: str = "") -> dict:
    """List all available channels on the network tier."""
    client, err = _get_team_client(server_url)
    if err:
        return {"error": err}

    return client.list_channels()
