"""Checklist helper — template lookup and runtime checklist read/write.

Purpose: Provide a single API for accessing checklist templates (shipped as package data)
         and reading/writing agent checklists to ~/.minion_work/checklists/.
Rationale: Templates were previously only in .work/templates/ (not shipped with install).
           Runtime checklists were only in .work/checklists/ (project-local). This module
           makes both accessible from any context via importlib-style path resolution.
Responsibility: Template path resolution, checklist dir creation, checklist CRUD.
Organization: Four public functions — get_template_path, get_checklist_dir, write_checklist, read_checklist.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Template names that ship with the package
TEMPLATE_NAMES = ("napoleon", "lead", "worker")

# Global checklist directory — shared across all projects
_CHECKLIST_DIR = Path("~/.minion_work/checklists").expanduser()

# Templates live alongside this module in src/minion/templates/
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


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


# ---------------------------------------------------------------------------
# Checklist directory
# ---------------------------------------------------------------------------


def get_checklist_dir() -> Path:
    """Return the global checklist directory, creating it if missing.

    Returns:
        Path to ~/.minion_work/checklists/ (guaranteed to exist after call).
    """
    # Create the directory tree if it doesn't exist
    _CHECKLIST_DIR.mkdir(parents=True, exist_ok=True)
    return _CHECKLIST_DIR


# ---------------------------------------------------------------------------
# Write checklist
# ---------------------------------------------------------------------------


def write_checklist(agent_name: str, content: str) -> Path:
    """Write a checklist file for an agent.

    Args:
        agent_name: The agent's registered name (e.g. 'b238-w1').
        content: The full markdown content of the checklist.

    Returns:
        Path to the written file (~/.minion_work/checklists/<agent_name>.md).
    """
    # Ensure directory exists
    checklist_dir = get_checklist_dir()

    # Write the checklist content
    path = checklist_dir / f"{agent_name}.md"
    path.write_text(content, encoding="utf-8")

    return path


# ---------------------------------------------------------------------------
# Read checklist
# ---------------------------------------------------------------------------


def read_checklist(agent_name: str) -> str | None:
    """Read a checklist file for an agent.

    Checks ~/.minion_work/checklists/<agent_name>.md first.
    Returns None if the file does not exist.

    Args:
        agent_name: The agent's registered name.

    Returns:
        The checklist content as a string, or None if not found.
    """
    # Check global checklist location
    path = _CHECKLIST_DIR / f"{agent_name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")

    return None
