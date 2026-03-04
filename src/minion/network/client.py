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

    def __init__(self, base_url: str = "", token: str = "", insecure: bool | None = None):
        self.base_url = (base_url or os.environ.get("MINION_NETWORK_URL", "")).rstrip("/")
        self.token = token or os.environ.get("MINION_CLUSTER_TOKEN", "")
        if insecure is None:
            insecure = os.environ.get("MINION_NETWORK_INSECURE", "") == "1"
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

    # --- Dashboard / project-scoped endpoints (stubs) ---
    # Implementation order: after server-side handlers are built.
    # Each method maps 1:1 to a server endpoint defined in handlers/.

    def list_projects(self) -> dict:
        """GET /projects — list all discovered projects."""
        # PSEUDO: return self._request("GET", "/projects")
        raise NotImplementedError

    def project_agents(self, project_name: str) -> dict:
        """GET /projects/{name}/agents — agents from project-local DB."""
        # PSEUDO: return self._request("GET", f"/projects/{project_name}/agents")
        raise NotImplementedError

    def project_tasks(self, project_name: str, **filters) -> dict:
        """GET /projects/{name}/tasks — tasks with optional filters.

        Filters: status, assigned_to, limit, offset.
        """
        # PSEUDO: query_string = urlencode({k: v for k, v in filters.items() if v})
        # PSEUDO: return self._request("GET", f"/projects/{project_name}/tasks?{query_string}")
        raise NotImplementedError

    def task_lineage(self, project_name: str, task_id: int) -> dict:
        """GET /projects/{name}/tasks/{id}/lineage — task detail + status history."""
        # PSEUDO: return self._request("GET", f"/projects/{project_name}/tasks/{task_id}/lineage")
        raise NotImplementedError

    def project_messages(self, project_name: str, **filters) -> dict:
        """GET /projects/{name}/messages — project-local messages.

        Filters: from_agent, to_agent, limit.
        """
        # PSEUDO: query_string = urlencode({k: v for k, v in filters.items() if v})
        # PSEUDO: return self._request("GET", f"/projects/{project_name}/messages?{query_string}")
        raise NotImplementedError

    def project_raid_log(self, project_name: str) -> dict:
        """GET /projects/{name}/raid-log — raid log entries."""
        # PSEUDO: return self._request("GET", f"/projects/{project_name}/raid-log")
        raise NotImplementedError

    def project_flow(self, project_name: str, flow_type: str) -> dict:
        """GET /projects/{name}/flows/{type} — parsed flow DAG definition."""
        # PSEUDO: return self._request("GET", f"/projects/{project_name}/flows/{flow_type}")
        raise NotImplementedError

    def project_requirements(self, project_name: str, **filters) -> dict:
        """GET /projects/{name}/requirements — requirements with stage tracking.

        Filters: stage, flow_type.
        """
        # PSEUDO: query_string = urlencode({k: v for k, v in filters.items() if v})
        # PSEUDO: return self._request("GET", f"/projects/{project_name}/requirements?{query_string}")
        raise NotImplementedError

    def requirement_lineage(self, project_name: str, requirement_id: int) -> dict:
        """GET /projects/{name}/requirements/{id}/lineage — full requirement DAG history."""
        # PSEUDO: return self._request("GET",
        #   f"/projects/{project_name}/requirements/{requirement_id}/lineage")
        raise NotImplementedError

    def project_backlog(self, project_name: str, **filters) -> dict:
        """GET /projects/{name}/backlog — backlog items.

        Filters: priority, status.
        """
        # PSEUDO: query_string = urlencode({k: v for k, v in filters.items() if v})
        # PSEUDO: return self._request("GET", f"/projects/{project_name}/backlog?{query_string}")
        raise NotImplementedError

    def overview(self) -> dict:
        """GET /overview — system-wide summary across all projects."""
        # PSEUDO: return self._request("GET", "/overview")
        raise NotImplementedError

    def alerts(self) -> dict:
        """GET /alerts — actionable alerts for sys-lead monitoring."""
        # PSEUDO: return self._request("GET", "/alerts")
        raise NotImplementedError

    def capacity(self) -> dict:
        """GET /capacity — machine capacity for agent spawning."""
        # PSEUDO: return self._request("GET", "/capacity")
        raise NotImplementedError


def _get_machine_id() -> str:
    """Generate a stable machine identifier."""
    import socket
    return socket.gethostname()


def get_client() -> NetworkClient:
    """Get a NetworkClient from environment config. Returns unconfigured client if no URL set."""
    return NetworkClient()
