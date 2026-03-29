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
    1. Explicit server_url argument (URL or named remote alias like "trashcan")
    2. MINION_NETWORK_URL env var
    3. Local API server (https://127.0.0.1:8377) if running
    4. Default remote profile
    """
    from minion.network.client import NetworkClient
    from minion.defaults import resolve_network_url, resolve_network_insecure

    # If server_url looks like a name (no ://), try to resolve as a remote profile alias
    if server_url and "://" not in server_url:
        from minion.api.remotes import get_remote_client
        client, err = get_remote_client(server_url)
        if client:
            return client, None
        # Fall through — maybe it's a hostname, not a profile name

    url = (server_url if "://" in server_url else "") or resolve_network_url()
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


def _auto_save_profile(client) -> None:
    """Auto-save the coordinator URL as a remote profile so subsequent
    team commands work without re-specifying the server URL.

    Only saves if no default remote profile exists yet.
    """
    try:
        from minion.api.remotes import get_remote, save_remote
        existing = get_remote()
        if existing:
            return  # already have a default profile, don't overwrite

        url = client.base_url
        token = client.token
        insecure = client._insecure
        if url:
            save_remote(name="default", url=url, token=token, insecure=insecure)
    except Exception:
        pass  # non-fatal — profile save is best-effort


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

    # Auto-save coordinator profile so subsequent commands just work
    _auto_save_profile(client)

    from minion.team_identity import save_identity, get_identity

    # Check for stored identity to reclaim UUID on rejoin
    stored = get_identity(channel=channel, agent_name=agent)
    stored_uuid = stored.get("agent_uuid", "") if stored else ""

    # Register on network tier (also auto-joins channel via project_path bridge)
    reg = client.register(
        name=agent,
        agent_class=agent_class,
        host=_machine_id(),
        project_path=project_path,
        machine_id=_machine_id(),
        agent_uuid=stored_uuid,
    )
    if "error" in reg:
        return reg

    # Explicitly join channel (canonical path, idempotent)
    role = "lead" if agent_class == "lead" else "member"
    client.join_channel(channel=channel, agent=agent, machine_id=_machine_id(), role=role)

    # Fetch channel roster
    members_result = client.channel_members(channel)
    members = members_result.get("members", [])

    # Catch-up: fetch unread messages so the rejoining agent sees what they missed
    catchup = client.check_inbox(agent)
    unread = catchup.get("messages", [])

    # Extract stable UUID from registration response
    agent_uuid = reg.get("agent_uuid", "")

    result = {
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

    # Persist identity locally so subsequent commands auto-resolve agent/channel
    save_identity(
        coordinator_url=client.base_url,
        channel=channel,
        agent_name=agent,
        agent_uuid=agent_uuid,
        agent_class=agent_class,
        project_path=project_path,
    )

    # Include catch-up summary if there are unread messages
    if unread:
        result["catchup"] = {
            "unread_count": len(unread),
            "messages": [
                {
                    "from": m.get("from_agent", ""),
                    "content": m.get("content", "")[:200],  # truncate for summary
                    "timestamp": m.get("timestamp", ""),
                }
                for m in unread[:10]  # cap at 10 most recent
            ],
        }

    return result


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
    agent: str, project_dir: str = "", channel: str = "",
    server_url: str = "", all_coordinators: bool = True,
) -> dict:
    """Check unread messages for an agent, optionally scoped to a channel.

    Without --channel, returns ALL unread messages (including unchanneled ones).
    If all_coordinators=True and no server_url specified, aggregates across all
    joined coordinators. Each message is tagged with coordinator/channel/sender.
    """
    # If a specific server is given, just query that one
    if server_url:
        client, err = _get_team_client(server_url)
        if err:
            return {"error": err}
        result = client.check_inbox(agent, channel=channel)
        # Tag messages with server context
        for msg in result.get("messages", []):
            msg["coordinator"] = client.base_url
        return result

    # Aggregate across all joined coordinators
    if all_coordinators:
        from minion.team_identity import list_identities
        from minion.network.client import NetworkClient
        from minion.defaults import resolve_network_insecure

        identities = list_identities()
        # Deduplicate coordinator URLs
        seen_urls = set()
        coordinator_urls = []
        for identity in identities:
            url = identity.get("coordinator_url", "").rstrip("/")
            if url and url not in seen_urls:
                seen_urls.add(url)
                coordinator_urls.append(url)

        if not coordinator_urls:
            # No saved identities — fall back to single-server path
            client, err = _get_team_client()
            if err:
                return {"error": err}
            return client.check_inbox(agent, channel=channel)

        all_messages = []
        errors = []
        for url in coordinator_urls:
            try:
                token = _read_token()
                insecure = resolve_network_insecure() or url.startswith("https://0.0.0.0") or url.startswith("https://127.0.0.1")
                client = NetworkClient(base_url=url, token=token, insecure=insecure)
                result = client.check_inbox(agent, channel=channel)
                if "error" in result:
                    errors.append({"coordinator": url, "error": result["error"]})
                else:
                    for msg in result.get("messages", []):
                        msg["coordinator"] = url
                    all_messages.extend(result.get("messages", []))
            except Exception as e:
                errors.append({"coordinator": url, "error": str(e)})

        response: dict = {"messages": all_messages, "agent": agent}
        if errors:
            response["errors"] = errors
        return response

    # Single coordinator fallback
    client, err = _get_team_client()
    if err:
        return {"error": err}
    return client.check_inbox(agent, channel=channel)


def channels(server_url: str = "") -> dict:
    """List all available channels on the network tier."""
    client, err = _get_team_client(server_url)
    if err:
        return {"error": err}

    return client.list_channels()


def aggregate_inbox(agent: str, channel: str = "", server_url: str = "") -> dict:
    """Aggregate inbox across ALL sources: local project DB + all joined coordinators.

    Every message is tagged with source context:
    - source_kind: "local" or "coordinator"
    - source_name: "local" or server alias/URL
    - channel: project/channel name
    - source_label: compact "source_name/channel" string
    """
    all_messages = []
    errors = []

    # 1. Local project inbox
    try:
        from minion.db.connection import get_db
        conn = get_db()
        # Read local messages — look for content_file or inline content
        rows = conn.execute(
            "SELECT id, from_agent, to_agent, timestamp, content_file FROM messages "
            "WHERE to_agent = ? AND read_flag = 0 ORDER BY timestamp ASC",
            (agent,),
        ).fetchall()
        # Derive local project name from DB path
        from minion.db.connection import _get_db_path
        db_path = _get_db_path()
        local_project = os.path.basename(os.path.dirname(os.path.dirname(db_path)))

        for row in rows:
            content = ""
            content_file = row["content_file"] if "content_file" in row.keys() else None
            if content_file and os.path.isfile(content_file):
                try:
                    with open(content_file) as f:
                        content = f.read()[:500]
                except OSError:
                    content = "(unreadable)"
            msg = {
                "id": row["id"],
                "from": row["from_agent"],
                "to": row["to_agent"],
                "content": content,
                "timestamp": row["timestamp"],
                "source_kind": "local",
                "source_name": "local",
                "channel": local_project,
                "source_label": f"local/{local_project}",
            }
            all_messages.append(msg)
        conn.close()
    except Exception as e:
        # Local DB may not exist — non-fatal for network-only setups
        errors.append({"source": "local", "error": str(e)})

    # 2. Coordinator inboxes (reuse the existing multi-coordinator logic)
    coord_result = inbox(agent=agent, channel=channel, server_url=server_url)
    if "error" in coord_result:
        errors.append({"source": "coordinator", "error": coord_result["error"]})
    else:
        for msg in coord_result.get("messages", []):
            coordinator_url = msg.get("coordinator", "")
            # Resolve server alias from remote profiles
            server_alias = _resolve_server_alias(coordinator_url)
            ch = msg.get("channel", "") or _guess_channel(coordinator_url)
            msg["source_kind"] = "coordinator"
            msg["source_name"] = server_alias
            msg["channel"] = ch
            msg["source_label"] = f"{server_alias}/{ch}" if ch else server_alias
            all_messages.append(msg)

    # Sort all by timestamp
    all_messages.sort(key=lambda m: m.get("timestamp", ""))

    result: dict = {"messages": all_messages, "agent": agent}
    if errors:
        result["errors"] = errors
    return result


def _resolve_server_alias(url: str) -> str:
    """Resolve a coordinator URL to a human-friendly alias from remote profiles."""
    try:
        from minion.api.remotes import _read_remotes
        data = _read_remotes()
        for name, profile in data.get("remotes", {}).items():
            if profile.get("url", "").rstrip("/") == url.rstrip("/"):
                return name
    except Exception:
        pass
    # Fallback: extract hostname from URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.hostname or url
    except Exception:
        return url


def _guess_channel(coordinator_url: str) -> str:
    """Try to guess the channel from saved identities for a coordinator."""
    try:
        from minion.team_identity import list_identities
        for identity in list_identities():
            if identity.get("coordinator_url", "").rstrip("/") == coordinator_url.rstrip("/"):
                return identity.get("channel", "")
    except Exception:
        pass
    return ""


def coordinators() -> dict:
    """List all coordinators this CLI has joined."""
    from minion.team_identity import list_coordinators, list_identities
    urls = list_coordinators()
    identities = list_identities()
    return {
        "coordinators": [
            {
                "url": url,
                "identities": [
                    {
                        "channel": i.get("channel"),
                        "agent": i.get("agent_name"),
                        "class": i.get("agent_class"),
                        "uuid": i.get("agent_uuid"),
                    }
                    for i in identities if i.get("coordinator_url", "").rstrip("/") == url.rstrip("/")
                ],
            }
            for url in urls
        ],
    }


def identities() -> dict:
    """List all saved team identities."""
    from minion.team_identity import list_identities
    return {"identities": list_identities()}
