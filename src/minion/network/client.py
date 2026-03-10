"""HTTP client for API GLOBAL network tier — stdlib urllib, zero external deps.

All methods return dicts matching the server's JSON responses.
Failures return {"error": "..."} instead of raising.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

from minion.defaults import resolve_cluster_token, resolve_network_insecure, resolve_network_url


class NetworkClient:
    """Client for the API GLOBAL coordinator server."""

    def __init__(self, base_url: str = "", token: str = "", insecure: bool | None = None):
        self.base_url = (base_url or resolve_network_url()).rstrip("/")
        self.token = token or resolve_cluster_token()
        if insecure is None:
            insecure = resolve_network_insecure()
        self._insecure = insecure

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
            ssl_ctx = None
            if self._insecure:
                import ssl
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
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

    # --- Dashboard / project-scoped endpoints ---
    # Each method maps 1:1 to a server endpoint defined in handlers/.

    def list_projects(self) -> dict:
        """GET /projects — list all discovered projects."""
        return self._request("GET", "/projects")

    def project_agents(self, project_name: str) -> dict:
        """GET /projects/{name}/agents — agents from project-local DB."""
        return self._request("GET", f"/projects/{project_name}/agents")

    def project_tasks(self, project_name: str, **filters: str) -> dict:
        """GET /projects/{name}/tasks — tasks with optional filters."""
        qs = _build_query_string(filters)
        return self._request("GET", f"/projects/{project_name}/tasks{qs}")

    def task_lineage(self, project_name: str, task_id: int) -> dict:
        """GET /projects/{name}/tasks/{id}/lineage — task detail + status history."""
        return self._request("GET", f"/projects/{project_name}/tasks/{task_id}/lineage")

    def project_messages(self, project_name: str, **filters: str) -> dict:
        """GET /projects/{name}/messages — project-local messages."""
        qs = _build_query_string(filters)
        return self._request("GET", f"/projects/{project_name}/messages{qs}")

    def project_raid_log(self, project_name: str) -> dict:
        """GET /projects/{name}/raid-log — raid log entries."""
        return self._request("GET", f"/projects/{project_name}/raid-log")

    def project_flow(self, project_name: str, flow_type: str) -> dict:
        """GET /projects/{name}/flows/{type} — parsed flow DAG definition."""
        return self._request("GET", f"/projects/{project_name}/flows/{flow_type}")

    def project_requirements(self, project_name: str, **filters: str) -> dict:
        """GET /projects/{name}/requirements — requirements with stage tracking."""
        qs = _build_query_string(filters)
        return self._request("GET", f"/projects/{project_name}/requirements{qs}")

    def requirement_lineage(self, project_name: str, requirement_id: int) -> dict:
        """GET /projects/{name}/requirements/{id}/lineage — full requirement DAG history."""
        return self._request("GET", f"/projects/{project_name}/requirements/{requirement_id}/lineage")

    def project_backlog(self, project_name: str, **filters: str) -> dict:
        """GET /projects/{name}/backlog — backlog items."""
        qs = _build_query_string(filters)
        return self._request("GET", f"/projects/{project_name}/backlog{qs}")

    def overview(self) -> dict:
        """GET /overview — system-wide summary across all projects."""
        return self._request("GET", "/overview")

    def alerts(self) -> dict:
        """GET /alerts — actionable alerts for sys-lead monitoring."""
        return self._request("GET", "/alerts")

    def capacity(self) -> dict:
        """GET /capacity — machine capacity for agent spawning."""
        return self._request("GET", "/capacity")


def _build_query_string(params: dict) -> str:
    """Build ?key=val&... from non-empty params."""
    from urllib.parse import urlencode
    filtered = {k: v for k, v in params.items() if v is not None and v != ""}
    if not filtered:
        return ""
    return "?" + urlencode(filtered)


def _get_machine_id() -> str:
    """Generate a stable machine identifier."""
    import socket
    return socket.gethostname()


def get_client() -> NetworkClient:
    """Get a NetworkClient from environment config. Returns unconfigured client if no URL set."""
    return NetworkClient()
