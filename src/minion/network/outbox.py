"""Offline outbox — queue messages when API GLOBAL is unreachable, deliver on next poll."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path


def _outbox_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".minion", "outbox")
    os.makedirs(d, exist_ok=True)
    return d


def queue_message(from_agent: str, to_agent: str, message: str) -> str:
    """Write a message to the outbox for later delivery. Returns the queued file path."""
    outbox = _outbox_dir()
    ts = int(time.time() * 1000)
    fname = f"{ts}-{from_agent}-to-{to_agent}.json"
    path = os.path.join(outbox, fname)
    data = {
        "from": from_agent,
        "to": to_agent,
        "message": message,
        "queued_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def drain_outbox(client) -> list[dict]:
    """Try to deliver all queued messages. Returns list of results (sent or still-queued)."""
    outbox = _outbox_dir()
    results = []

    for fname in sorted(os.listdir(outbox)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(outbox, fname)
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        result = client.send(data["from"], data["to"], data["message"])
        if "error" not in result:
            os.remove(path)
            results.append({"status": "delivered", "file": fname, **result})
        else:
            results.append({"status": "still_queued", "file": fname, "error": result["error"]})

    return results


def outbox_count() -> int:
    """Number of messages waiting in the outbox."""
    outbox = _outbox_dir()
    return len([f for f in os.listdir(outbox) if f.endswith(".json")])
