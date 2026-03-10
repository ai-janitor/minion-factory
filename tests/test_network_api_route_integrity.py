"""Reference integrity tests for network API route-to-handler mapping.
Ensures every registered route points to a callable handler, no dead routes
exist, and all handler modules are properly imported and registered.

Purpose: Reference integrity tests for network API route-to-handler mapping.
Rationale: Test coverage for the corresponding module.
Responsibility: Reference integrity tests for network API route-to-handler mapping. NOT responsible for unrelated concerns.
Organization: One TestClass per concern, or standalone test functions."""

from __future__ import annotations

import inspect

from minion.network.router import Router
from minion.network.handlers import register_all


def _build_router() -> Router:
    """Create and populate a router with all handlers."""
    router = Router()
    register_all(router)
    return router


def test_all_get_routes_have_callable_handlers():
    """Every registered GET route must point to a callable handler function."""
    router = _build_router()
    for _regex, _params, handler_fn in router._get_routes:
        assert callable(handler_fn), f"GET handler {handler_fn!r} is not callable"


def test_all_post_routes_have_callable_handlers():
    """Every registered POST route must point to a callable handler function."""
    router = _build_router()
    for _regex, _params, handler_fn in router._post_routes:
        assert callable(handler_fn), f"POST handler {handler_fn!r} is not callable"


def test_at_least_one_route_registered():
    """Sanity check — router should have routes after register_all."""
    router = _build_router()
    total = len(router._get_routes) + len(router._post_routes)
    assert total > 0, "No routes registered — register_all() may be broken"


def test_no_duplicate_route_patterns():
    """No two routes should match the same pattern (first-match-wins is fragile)."""
    router = _build_router()
    seen_get = []
    for regex, _params, _handler in router._get_routes:
        pattern = regex.pattern
        assert pattern not in seen_get, f"Duplicate GET pattern: {pattern}"
        seen_get.append(pattern)

    seen_post = []
    for regex, _params, _handler in router._post_routes:
        pattern = regex.pattern
        assert pattern not in seen_post, f"Duplicate POST pattern: {pattern}"
        seen_post.append(pattern)


def test_handler_functions_are_named():
    """Handlers should be named functions, not lambdas or partials."""
    router = _build_router()
    all_routes = router._get_routes + router._post_routes
    for _regex, _params, handler_fn in all_routes:
        name = getattr(handler_fn, "__name__", None)
        assert name is not None, f"Handler {handler_fn!r} has no __name__"
        assert name != "<lambda>", f"Handler is a lambda — use a named function"


def test_handler_modules_all_imported():
    """All handler modules in handlers/ should be imported by __init__.py."""
    from minion.network import handlers
    expected_registers = [
        "register_core",
        "register_projects",
        "register_flows",
        "register_requirements",
        "register_backlog",
        "register_overview",
        "register_scaling",
        "register_compat",
    ]
    for name in expected_registers:
        assert hasattr(handlers, name), f"Handler register function '{name}' not exported from handlers/__init__.py"


def test_route_patterns_compile_and_match_self():
    """Each registered pattern should match at least one example URL."""
    router = _build_router()
    all_routes = router._get_routes + router._post_routes
    for regex, params, _handler in all_routes:
        # Build a sample URL by replacing named groups with "test"
        sample = regex.pattern.lstrip("^").rstrip("$")
        sample = sample.replace("(?P<", "{").replace(">[^/]+)", "}")
        # Replace {param} with "test-value"
        for p in params:
            sample = sample.replace(f"{{{p}}}", "test-value")
        match = regex.fullmatch(sample)
        assert match is not None, f"Pattern {regex.pattern} doesn't match its own sample URL: {sample}"


def test_expected_core_routes_exist():
    """Core routes that must exist for the API to function."""
    router = _build_router()
    # Collect all GET patterns
    get_patterns = [regex.pattern for regex, _, _ in router._get_routes]
    post_patterns = [regex.pattern for regex, _, _ in router._post_routes]

    # Essential GET routes
    assert any("/health" in p for p in get_patterns), "Missing /health route"
    assert any("/who" in p for p in get_patterns), "Missing /who route"
    assert any("/projects" in p for p in get_patterns), "Missing /projects route"
    assert any("/overview" in p for p in get_patterns), "Missing /overview route"
    assert any("/alerts" in p for p in get_patterns), "Missing /alerts route"

    # Essential POST routes
    assert any("/register" in p for p in post_patterns), "Missing /register route"
    assert any("/send" in p for p in post_patterns), "Missing /send route"
