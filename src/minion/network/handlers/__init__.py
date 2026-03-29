"""Network API handler registry — re-exports all handler registration functions.

Purpose: Single import point for the router to collect all endpoint handlers.
Rationale: Keeps handler modules independently testable while providing a clean
           registration interface for the router dispatch table.
Responsibility: Import and re-export the register_* function from each handler module.
Organization: Each handler module exposes a register(router) function that adds its
              routes to the dispatch table.
"""

from .core import register as register_core
from .projects import register as register_projects
from .flows import register as register_flows
from .requirements import register as register_requirements
from .backlog import register as register_backlog
from .overview import register as register_overview
from .scaling import register as register_scaling
from .compat import register as register_compat
from .lifecycle import register as register_lifecycle
from .agent_context import register as register_agent_context
from .task_workflow import register as register_task_workflow
from .diagnostics import register as register_diagnostics
from .coordinator_status import register as register_coordinator_status
from .bootstrap import register as register_bootstrap

__all__ = [
    "register_core",
    "register_projects",
    "register_flows",
    "register_requirements",
    "register_backlog",
    "register_overview",
    "register_scaling",
    "register_compat",
    "register_lifecycle",
    "register_agent_context",
    "register_task_workflow",
    "register_diagnostics",
    "register_coordinator_status",
    "register_bootstrap",
]


def register_all(router) -> None:
    """Register all handler modules with the given router.

    Called once at server startup to populate the route dispatch table.
    """
    register_core(router)
    register_projects(router)
    register_flows(router)
    register_requirements(router)
    register_backlog(router)
    register_overview(router)
    register_scaling(router)
    register_compat(router)  # /api/* backward-compat routes for React frontend
    register_lifecycle(router)
    register_agent_context(router)
    register_task_workflow(router)
    register_diagnostics(router)
    register_coordinator_status(router)
    register_bootstrap(router)
