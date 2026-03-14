"""Checklist helper — template lookup and runtime checklist read/write.

Purpose: Provide a single API for accessing checklist templates (shipped as package data)
         and reading/writing agent checklists to project-local .work/checklists/.
Rationale: Templates were previously only in .work/templates/ (not shipped with install).
           Runtime checklists live in .work/checklists/ (project-local). This module
           makes both accessible from any context via importlib-style path resolution.
Responsibility: Template path resolution, template-to-class resolution, checklist dir creation, checklist CRUD.
Organization: Public functions — get_template_path, resolve_template, get_checklist_dir, write_checklist, read_checklist.
"""

from __future__ import annotations

from pathlib import Path

from minion.defaults import resolve_work_dir

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Template names that ship with the package
TEMPLATE_NAMES = ("napoleon", "lead", "worker")

# Templates live alongside this module in src/minion/templates/
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# Map agent class → default template name
_CLASS_TO_TEMPLATE: dict[str, str] = {
    "lead": "lead",
    "coder": "worker",
    "recon": "worker",
    "auditor": "worker",
    "builder": "worker",
}


# ---------------------------------------------------------------------------
# Template lookup
# ---------------------------------------------------------------------------


def get_template_path(template_name: str) -> Path:
    """Return the installed path for a checklist template.

    Args:
        template_name: One of 'napoleon', 'lead', or 'worker'.

    Returns:
        Absolute Path to the template .md file.

    Raises:
        ValueError: If template_name is not one of the known templates.
        FileNotFoundError: If the template file is missing from the install.
    """
    # Validate template name against known set
    if template_name not in TEMPLATE_NAMES:
        raise ValueError(
            f"Unknown template '{template_name}'. Must be one of: {', '.join(TEMPLATE_NAMES)}"
        )

    # Resolve path relative to this module's installed location
    path = _TEMPLATES_DIR / f"{template_name}-checklist.md"

    # Guard: template must exist in the installed package
    if not path.exists():
        raise FileNotFoundError(f"Template not found at {path}. Is the package installed correctly?")

    return path


def resolve_template(agent_class: str, phase: str | None = None) -> Path:
    """Resolve the best checklist template for an agent class and optional phase.

    Resolution order:
    1. <class>-<phase>.md template (e.g. coder-implementation-checklist.md) — if phase provided
    2. Class default: lead → lead-checklist.md, coder/recon/auditor/builder → worker-checklist.md
    3. Fall through to ValueError if nothing resolves

    Args:
        agent_class: The agent's class (lead, coder, recon, auditor, builder).
        phase: Optional current task phase/status (e.g. 'implementation', 'review').

    Returns:
        Path to the resolved template file.

    Raises:
        ValueError: If no template can be resolved for the given class.
    """
    # Step 1: Try phase-specific template if phase is provided
    if phase:
        phase_template = _TEMPLATES_DIR / f"{agent_class}-{phase}-checklist.md"
        if phase_template.exists():
            return phase_template

    # Step 2: Use class-to-template default mapping
    template_name = _CLASS_TO_TEMPLATE.get(agent_class)
    if template_name:
        path = _TEMPLATES_DIR / f"{template_name}-checklist.md"
        if path.exists():
            return path

    raise ValueError(
        f"No template found for class '{agent_class}'"
        + (f" phase '{phase}'" if phase else "")
        + f". Known classes: {', '.join(_CLASS_TO_TEMPLATE.keys())}"
    )


# ---------------------------------------------------------------------------
# Checklist directory — project-local .work/checklists/
# ---------------------------------------------------------------------------


def get_checklist_dir(project_dir: str | Path | None = None) -> Path:
    """Return the project-local checklist directory, creating it if missing.

    Uses resolve_work_dir() to find the project root, then appends checklists/.

    Returns:
        Path to <project>/.work/checklists/ (guaranteed to exist after call).
    """
    work_dir = resolve_work_dir(project_dir)
    checklist_dir = work_dir / "checklists"
    checklist_dir.mkdir(parents=True, exist_ok=True)
    return checklist_dir


# ---------------------------------------------------------------------------
# Write checklist
# ---------------------------------------------------------------------------


def write_checklist(agent_name: str, content: str, project_dir: str | Path | None = None, template_type: str | None = None, task_id: int | None = None) -> Path:
    """Write a checklist file for an agent.

    File naming convention:
      - With task_id (preferred): lead-<name>-task-<id>.md  or  <name>-task-<id>.md
      - Without task_id (legacy):  lead-<name>.md            or  <name>.md

    The task_id suffix scopes checklists to the specific task, preventing stale
    checklists from old sessions (same agent name, different task) from appearing
    in lineage views. Always pass task_id when available.

    Args:
        agent_name: The agent's registered name (e.g. 'b238-w1').
        content: The full markdown content of the checklist.
        project_dir: Optional project directory override.
        template_type: Template type used ('napoleon', 'lead', 'worker', or None).
        task_id: Optional task ID to scope this checklist. Produces task-ID-scoped filename.

    Returns:
        Path to the written file.
    """
    # Ensure directory exists
    checklist_dir = get_checklist_dir(project_dir)

    # Build filename — task_id suffix scopes checklist to prevent session bleed
    # Lead checklists use lead-<name> prefix to match TUI lookup order
    if task_id is not None:
        if template_type == "lead":
            filename = f"lead-{agent_name}-task-{task_id}.md"
        else:
            filename = f"{agent_name}-task-{task_id}.md"
    else:
        # Legacy fallback: no task ID (backward compat for callers that don't pass task_id)
        if template_type == "lead":
            filename = f"lead-{agent_name}.md"
        else:
            filename = f"{agent_name}.md"

    path = checklist_dir / filename
    path.write_text(content, encoding="utf-8")

    return path


# ---------------------------------------------------------------------------
# Read checklist
# ---------------------------------------------------------------------------


def read_checklist(agent_name: str, project_dir: str | Path | None = None, task_id: int | None = None) -> str | None:
    """Read a checklist file for an agent.

    Search order (task_id provided):
    1. lead-<agent_name>-task-<id>.md  (task-scoped lead checklist)
    2. <agent_name>-task-<id>.md       (task-scoped worker checklist)
    3. lead-<agent_name>.md            (legacy lead checklist)
    4. <agent_name>.md                 (legacy worker/generic checklist)

    Search order (no task_id):
    1. lead-<agent_name>.md  (lead checklist)
    2. <agent_name>.md       (worker/generic checklist)

    Returns None if no file is found.

    Args:
        agent_name: The agent's registered name.
        project_dir: Optional project directory override.
        task_id: Optional task ID to prefer task-scoped checklist filenames.

    Returns:
        The checklist content as a string, or None if not found.
    """
    checklist_dir = get_checklist_dir(project_dir)

    # Build candidate list — task-scoped names searched first when task_id provided
    candidates: list[str] = []
    if task_id is not None:
        candidates.append(f"lead-{agent_name}-task-{task_id}.md")
        candidates.append(f"{agent_name}-task-{task_id}.md")
    # Legacy fallback candidates (always included)
    candidates.append(f"lead-{agent_name}.md")
    candidates.append(f"{agent_name}.md")

    for filename in candidates:
        path = checklist_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")

    return None
