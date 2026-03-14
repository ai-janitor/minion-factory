"""Backlog — lightweight capture for ideas, bugs, requests, smells, and debt.
Items live under .work/backlog/<type>/<slug>/ as README.md folders.
The DB is a rebuildable index; the filesystem is the source of truth.

Purpose: Backlog — lightweight capture for ideas, bugs, requests, smells, and debt.
Rationale: Extracted into own module for single-responsibility backlog management.
Responsibility: Backlog — lightweight capture for ideas, bugs, requests, smells, and debt. NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic."""

from .add_item import add
from .close_item import kill, defer, reopen
from .fast_track import fast_track
from .get_item import get_item
from .lineage import lineage
from .list_items import list_items
from .promote import promote
from .reindex import reindex
from .update_item import update_item

__all__: list[str] = [
    "add",
    "defer",
    "fast_track",
    "get_item",
    "kill",
    "lineage",
    "list_items",
    "promote",
    "reindex",
    "reopen",
    "update_item",
]
