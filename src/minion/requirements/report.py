"""Roll up full requirement lineage into a single markdown report.

Reads filesystem (source of truth) for content, enriches with DB for
stage/completion/task status.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from minion.db import _get_db_path
from minion.requirements.crud import get_status, get_tree


def _resolve_work_dir() -> Path:
    """Derive .work/ directory from the DB path."""
    return Path(_get_db_path()).parent


def _read_optional(path: Path) -> str | None:
    """Read file content if it exists, else None."""
    if path.is_file():
        return path.read_text().strip()
    return None


def _extract_title_from_readme(content: str) -> str:
    """Pull the first H1 from README content."""
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "(untitled)"


def _find_children(req_dir: Path) -> list[Path]:
    """Find NNN-slug/ child directories, sorted by prefix."""
    if not req_dir.is_dir():
        return []
    pattern = re.compile(r"^\d{3}-")
    children = [
        req_dir / entry
        for entry in sorted(os.listdir(req_dir))
        if pattern.match(entry) and (req_dir / entry).is_dir()
    ]
    return children


def report(file_path: str) -> dict[str, Any]:
    """Build a full lineage report for a requirement.

    Args:
        file_path: Requirement path relative to .work/requirements/.

    Returns:
        Structured dict with all sections, ready for markdown rendering.
    """
    file_path = file_path.rstrip("/")
    work_dir = _resolve_work_dir()
    req_dir = work_dir / "requirements" / file_path

    if not req_dir.is_dir():
        return {"error": f"Requirement directory not found: {file_path}"}

    # --- Filesystem content ---
    readme = _read_optional(req_dir / "README.md")
    if not readme:
        return {"error": f"No README.md found in {file_path}"}

    title = _extract_title_from_readme(readme)
    spec = _read_optional(req_dir / "SPEC.md")
    findings_content = _read_optional(req_dir / "findings.md")
    itemized = _read_optional(req_dir / "itemized-requirements.md")

    # --- DB enrichment ---
    status_data = get_status(file_path)
    tree_data = get_tree(file_path)

    stage = status_data.get("requirement", {}).get("stage", "unknown")
    flow_type = status_data.get("requirement", {}).get("flow_type", "unknown")
    task_count = status_data.get("task_count", 0)
    closed_count = status_data.get("closed_count", 0)
    completion_pct = status_data.get("completion_pct", 0)

    # Build task status lookup from tree data: child_path -> linked_tasks
    task_lookup: dict[str, list[dict]] = {}
    for node in tree_data.get("nodes", []):
        task_lookup[node["file_path"]] = node.get("linked_tasks", [])

    # --- Children ---
    children = []
    for child_dir in _find_children(req_dir):
        child_readme = _read_optional(child_dir / "README.md")
        child_slug = child_dir.name
        child_path = f"{file_path}/{child_slug}"
        child_tasks = task_lookup.get(child_path, [])
        children.append({
            "slug": child_slug,
            "readme": child_readme,
            "tasks": child_tasks,
        })

    return {
        "status": "ok",
        "title": title,
        "file_path": file_path,
        "stage": stage,
        "flow_type": flow_type,
        "task_count": task_count,
        "closed_count": closed_count,
        "completion_pct": completion_pct,
        "readme": readme,
        "spec": spec,
        "findings": findings_content,
        "itemized": itemized,
        "children": children,
    }


def format_report(data: dict[str, Any]) -> str:
    """Render a report dict as markdown text."""
    if "error" in data:
        return f"Error: {data['error']}"

    lines = [
        f"# Requirement Report: {data['title']}",
        "",
        "## Status",
        f"- **Stage:** {data['stage']}",
        f"- **Flow:** {data['flow_type']}",
        f"- **Completion:** {data['completion_pct']}% ({data['closed_count']}/{data['task_count']} tasks)",
        "",
    ]

    # README (skip title line — already in header)
    readme_body = "\n".join(
        line for line in data["readme"].splitlines()
        if not line.startswith("# ")
    ).strip()
    if readme_body:
        lines += ["## Problem", "", readme_body, ""]

    if data.get("spec"):
        lines += ["## Specification", "", data["spec"], ""]

    if data.get("itemized"):
        lines += ["## Itemized Requirements", "", data["itemized"], ""]

    if data.get("findings"):
        lines += ["## Findings", "", data["findings"], ""]

    if data.get("children"):
        lines += ["## Tasks", ""]
        for child in data["children"]:
            task_status = "no linked task"
            if child["tasks"]:
                statuses = ", ".join(
                    f"{t['title']} [{t['status']}]" for t in child["tasks"]
                )
                task_status = statuses

            lines += [f"### {child['slug']}", f"**Status:** {task_status}", ""]
            if child.get("readme"):
                # Skip title line from child README too
                child_body = "\n".join(
                    line for line in child["readme"].splitlines()
                    if not line.startswith("# ")
                ).strip()
                if child_body:
                    lines += [child_body, ""]

    return "\n".join(lines)
