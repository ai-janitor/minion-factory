"""Flow DAG endpoints — /projects/{name}/flows/{type}.

Purpose: Serve parsed task flow definitions (YAML DAGs) for a given project.
Rationale: The dashboard needs to render flow DAGs (stages, transitions, worker
           restrictions, terminal states). Flows are defined as YAML files in
           <project>/task-flows/<type>.yaml or built-in defaults.
Responsibility: Locate, parse, and return flow definitions. Resolve YAML inheritance.
Organization: Single endpoint, but YAML parsing logic lives here to keep it isolated.

Implementation order: 5th (depends on project_db for path resolution).
"""

from __future__ import annotations

import os
import re

import yaml

from minion.network.server import _DB_LOCK
from minion.network.discovery import resolve_project_path


def register(router) -> None:
    """Register flow endpoints with the router dispatch table."""
    router.add_get("/projects/{name}/flows/{flow_type}", handle_get_flow)


def _load_raw_flow(flow_type: str, flows_dir: str) -> dict:
    """Load a raw YAML flow definition from disk."""
    filename = "_base.yaml" if flow_type == "_base" else f"{flow_type}.yaml"
    flow_path = os.path.join(flows_dir, filename)
    with open(flow_path, "r") as f:
        return yaml.safe_load(f)


def _resolve_flow(flow_type: str, flows_dir: str) -> dict:
    """Resolve a flow with inheritance — child stages override parent."""
    raw = _load_raw_flow(flow_type, flows_dir)
    if not raw.get("inherits"):
        return raw
    parent_type = "_base" if raw["inherits"] == "base" else raw["inherits"]
    parent = _resolve_flow(parent_type, flows_dir)
    stages = {**(parent.get("stages") or {}), **(raw.get("stages") or {})}
    result = {**parent, **raw, "stages": stages}
    result.pop("inherits", None)
    return result


def _extract_pipeline(stages: dict) -> list[str]:
    """Follow `next` links from `open` to extract the main pipeline order."""
    pipeline = []
    current = "open"
    seen = set()
    while current and current in stages and current not in seen:
        seen.add(current)
        stage = stages[current]
        if not stage.get("parked") and not stage.get("skip"):
            pipeline.append(current)
        current = stage.get("next")
    return pipeline


def handle_get_flow(handler, db_path: str, project_name: str = "",
                    flow_type: str = "", name: str = "", **kwargs) -> None:
    """GET /projects/{name}/flows/{type} — parsed flow DAG definition.

    Resolves the flow YAML for the given type:
    1. Check <project_path>/task-flows/<type>.yaml
    2. Fall back to built-in task-flows/ at repo root
    3. Resolve YAML 'inherits' chains
    """
    # Allow both 'name' (from router) and 'project_name' (from compat)
    proj_name = name or project_name
    ftype = flow_type or kwargs.get("type", "")

    # Sanitize flow type
    ftype = re.sub(r"[^a-zA-Z0-9_-]", "", ftype)
    if not ftype:
        handler._json_response(400, {"error": "Flow type required"})
        return

    # Resolve project path to find task-flows/ directory
    project_path = resolve_project_path(db_path, proj_name, _DB_LOCK)

    # Try project-local task-flows first, then built-in
    flows_dirs = []
    if project_path:
        flows_dirs.append(os.path.join(project_path, "task-flows"))
    # Built-in flows at the minion-factory repo root (fallback)
    builtin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), "task-flows")
    if os.path.isdir(builtin):
        flows_dirs.append(builtin)

    for flows_dir in flows_dirs:
        try:
            flow = _resolve_flow(ftype, flows_dir)
            stages = flow.get("stages") or {}
            pipeline = _extract_pipeline(stages)
            dead_ends = flow.get("dead_ends") or []
            parked = [name for name, s in stages.items()
                      if s.get("parked") and not s.get("skip")]
            handler._json_response(200, {
                "type": ftype,
                "pipeline": pipeline,
                "dead_ends": dead_ends,
                "parked": parked,
            })
            return
        except FileNotFoundError:
            continue
        except Exception as e:
            handler._json_response(500, {"error": f"Failed to load flow: {e}"})
            return

    handler._json_response(404, {"error": f"Flow '{ftype}' not found"})
