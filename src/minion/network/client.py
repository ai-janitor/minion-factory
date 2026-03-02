"""HTTP client for API GLOBAL network tier — stdlib urllib, zero external deps.

All methods return dicts matching the server's JSON responses.
Failures return {"error": "..."} instead of raising.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error


class NetworkClient:
    """Client for the API GLOBAL coordinator server."""

    def __init__(self, base_url: str = "", token: str = ""):
        self.base_url = (base_url or os.environ.get("MINION_NETWORK_URL", "")).rstrip("/")
        self.token = token or os.environ.get("MINION_CLUSTER_TOKEN", "")

    @property
    def configured(self) -> bool:
        """True if a network URL is set (tier is enabled)."""
        return bool(self.base_url)

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        if not self.base_url:
            return {"error": "MINION_NETWORK_URL not configured"}

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read())
                return err_body
            except Exception:
                return {"error": f"HTTP {e.code}: {e.reason}"}
        except urllib.error.URLError as e:
            return {"error": f"Network unreachable: {e.reason}"}
        except Exception as e:
            return {"error": f"Request failed: {e}"}

    def register(
        self,
        name: str,
        agent_class: str = "coder",
        host: str = "",
        project_path: str = "",
        machine_id: str = "",
    ) -> dict:
        """Register agent on the network tier."""
        import socket
        body = {
            "name": name,
            "agent_class": agent_class,
            "host": host or socket.gethostname(),
            "project_path": project_path or os.getcwd(),
            "machine_id": machine_id or _get_machine_id(),
        }
        return self._request("POST", "/register", body)

    def send(self, from_agent: str, to_agent: str, message: str) -> dict:
        """Send a message via the network tier."""
        return self._request("POST", "/send", {
            "from": from_agent,
            "to": to_agent,
            "message": message,
        })

    def check_inbox(self, agent: str) -> dict:
        """Fetch unread messages from the network tier."""
        return self._request("GET", f"/inbox/{agent}")

    def who(self) -> dict:
        """List all agents registered on the network tier."""
        return self._request("GET", "/who")

    def health(self) -> dict:
        """Check if the network server is reachable."""
        return self._request("GET", "/health")


def _get_machine_id() -> str:
    """Generate a stable machine identifier."""
    import socket
    return socket.gethostname()


def get_client() -> NetworkClient:
    """Get a NetworkClient from environment config. Returns unconfigured client if no URL set."""
    return NetworkClient()
