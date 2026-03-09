"""DB package — re-exports all public names.

Consumer imports never change: `from minion.db import get_db, init_db` still works.
Internals are split by concern across submodules.
"""

from __future__ import annotations

from typing import Any

from minion.db.agents import (
    enrich_agent_row,
    get_lead,
    hp_summary,
    staleness_check,
)
from minion.db.connection import (
    _get_db_path,
    get_coordinator_db,
    get_db,
    get_runtime_dir,
    init_db,
    reset_db_path,
)
from minion.db.coordinator import (
    init_coordinator_db,
    touch_coordinator_activity,
)
from minion.db.timestamp_and_agent_registry import (
    now_iso,
    register_agent_db,
)
from minion.db.messages import (
    DOCS_DIR,
    format_trigger_codebook,
    load_onboarding,
    scan_triggers,
)
from minion.db.migrations import (
    _MIGRATIONS,
    _get_current_schema_version,
    _migrate,
    _run_migrations,
    _table_columns,
)
from minion.db.schema import (
    _COMMS_SCHEMA_SQL,
    _COORDINATOR_SCHEMA_SQL,
    _REQUIREMENTS_SCHEMA_SQL,
    _SCHEMA_VERSION_SQL,
    _TASKS_SCHEMA_SQL,
)

__all__ = [
    "DOCS_DIR",
    "enrich_agent_row",
    "format_trigger_codebook",
    "get_coordinator_db",
    "get_db",
    "get_lead",
    "get_runtime_dir",
    "hp_summary",
    "init_coordinator_db",
    "init_db",
    "load_onboarding",
    "now_iso",
    "register_agent_db",
    "reset_db_path",
    "scan_triggers",
    "staleness_check",
    "touch_coordinator_activity",
    # Semi-private but used across codebase
    "_get_db_path",
]


# Lazy module-level attributes — fs.py imports RUNTIME_DIR, comms.py uses DB_PATH
def __getattr__(name: str) -> Any:
    if name == "DB_PATH":
        return _get_db_path()
    if name == "RUNTIME_DIR":
        return get_runtime_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
