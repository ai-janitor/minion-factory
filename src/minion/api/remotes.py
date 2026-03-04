"""Remote profile management — save/load/list named remote server configs.

Profiles stored in ~/.minion/remotes.json with tokens in per-profile
chmod 600 files at ~/.minion/remotes/{name}.token.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _minion_dir() -> Path:
    return Path.home() / ".minion"


def _remotes_file() -> Path:
    return _minion_dir() / "remotes.json"


def _token_dir() -> Path:
    return _minion_dir() / "remotes"


def _token_file(name: str) -> Path:
    return _token_dir() / f"{name}.token"


def _read_remotes() -> dict:
    """Read remotes config. Returns {"default": "...", "remotes": {...}}."""
    rf = _remotes_file()
    if not rf.exists():
        return {"default": "", "remotes": {}}
    try:
        return json.loads(rf.read_text())
    except (json.JSONDecodeError, OSError):
        return {"default": "", "remotes": {}}


def _write_remotes(data: dict) -> None:
    """Write remotes config atomically."""
    rf = _remotes_file()
    rf.parent.mkdir(parents=True, exist_ok=True)
    tmp = rf.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(rf)


def save_remote(name: str, url: str, token: str, insecure: bool = False) -> dict:
    """Save a named remote profile.

    PSEUDO: Read existing remotes config
    PSEUDO: Add/update the named profile with url and insecure flag
    PSEUDO: Save token to separate chmod 600 file
    PSEUDO: If no default set, make this the default
    PSEUDO: Write config
    """
    data = _read_remotes()
    data["remotes"][name] = {
        "url": url.rstrip("/"),
        "insecure": insecure,
    }
    # First remote becomes default
    if not data["default"]:
        data["default"] = name
    _write_remotes(data)

    # Save token to restricted file
    if token:
        td = _token_dir()
        td.mkdir(parents=True, exist_ok=True)
        tf = _token_file(name)
        tf.write_text(token)
        tf.chmod(0o600)

    return {
        "status": "saved",
        "name": name,
        "url": url.rstrip("/"),
        "default": data["default"] == name,
    }


def get_remote(name: str | None = None) -> dict | None:
    """Get a remote profile by name (or default).

    Returns {"url": ..., "token": ..., "insecure": ...} or None.
    """
    data = _read_remotes()
    if name is None:
        name = data.get("default", "")
    if not name:
        return None
    remote = data.get("remotes", {}).get(name)
    if not remote:
        return None

    # Read token from file
    token = ""
    tf = _token_file(name)
    if tf.exists():
        try:
            token = tf.read_text().strip()
        except OSError:
            pass

    return {
        "name": name,
        "url": remote["url"],
        "token": token,
        "insecure": remote.get("insecure", False),
    }


def list_remotes() -> dict:
    """List all configured remotes."""
    data = _read_remotes()
    result = []
    for name, cfg in data.get("remotes", {}).items():
        result.append({
            "name": name,
            "url": cfg["url"],
            "default": name == data.get("default", ""),
            "insecure": cfg.get("insecure", False),
        })
    return {"remotes": result, "default": data.get("default", "")}


def remove_remote(name: str) -> dict:
    """Remove a named remote profile."""
    data = _read_remotes()
    if name not in data.get("remotes", {}):
        return {"error": f"Remote '{name}' not found."}
    del data["remotes"][name]
    if data["default"] == name:
        data["default"] = next(iter(data["remotes"]), "")
    _write_remotes(data)

    # Remove token file
    tf = _token_file(name)
    if tf.exists():
        tf.unlink()

    return {"status": "removed", "name": name}


def get_remote_client(name: str | None = None):
    """Get a NetworkClient configured from a remote profile.

    Returns (client, error_dict). If error, client is None.
    """
    from minion.network.client import NetworkClient

    profile = get_remote(name)
    if not profile:
        if name:
            return None, {"error": f"Remote '{name}' not configured. Run: minion api set-remote <url>"}
        return None, {"error": "No remote configured. Run: minion api set-remote <url>"}

    client = NetworkClient(
        base_url=profile["url"],
        token=profile["token"],
        insecure=profile["insecure"],
    )
    return client, None
