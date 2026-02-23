"""Define a task: create spec file + task record in one command."""

from __future__ import annotations

import os
import re

from minion.db import get_runtime_dir
from .create_task import create_task


def _slugify(title: str) -> str:
    """Lowercase, replace spaces/underscores with hyphens, strip non-alnum."""
    slug = title.lower().strip()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def define_task(
    agent_name: str,
    title: str,
    description: str,
    task_type: str = "feature",
    project: str = "",
    zone: str = "",
    blocked_by: str = "",
    class_required: str = "",
) -> dict[str, object]:
    """Create a task spec file and a task record in one shot."""
    work_dir = get_runtime_dir()
    spec_dir = os.path.join(work_dir, "task-specs")
    os.makedirs(spec_dir, exist_ok=True)

    slug = _slugify(title)
    spec_filename = f"TASK-{slug}.md"
    spec_path = os.path.join(spec_dir, spec_filename)

    with open(spec_path, "w") as f:
        f.write(f"# {title}\n\n{description}\n")

    return create_task(
        agent_name=agent_name,
        title=title,
        task_file=spec_path,
        project=project,
        zone=zone,
        blocked_by=blocked_by,
        class_required=class_required,
        task_type=task_type,
    )
