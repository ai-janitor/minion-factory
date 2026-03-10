"""  Init  .

Purpose:   Init   module.
Rationale: Extracted into own module for single-responsibility requirement tracking.
Responsibility:   Init  . NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic.
"""
from .crud import (
    create,
    register,
    reindex,
    resolve_path,
    update_stage,
    link_task,
    list_requirements,
    get_status,
    get_tree,
    get_orphans,
    get_unlinked_tasks,
)
from .decompose import decompose
from .findings import findings
from .itemize import itemize
from .report import report, format_report

__all__ = [
    "create",
    "register",
    "reindex",
    "resolve_path",
    "update_stage",
    "link_task",
    "list_requirements",
    "get_status",
    "get_tree",
    "get_orphans",
    "get_unlinked_tasks",
    "decompose",
    "findings",
    "itemize",
    "report",
    "format_report",
]
