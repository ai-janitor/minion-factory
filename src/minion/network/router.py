"""URL dispatch table + path pattern matching for the network API server.

Purpose: Replace the monolithic if/elif chain in _Handler.do_GET/do_POST with a
         declarative route table. Each handler module registers its routes here.
Rationale: A dispatch table makes routes independently testable, self-documenting,
           and keeps the _Handler class thin. Path patterns support {param} captures
           for URL segments like /projects/{name}/agents.
Responsibility: Route registration, URL pattern matching, parameter extraction,
                dispatching to handler functions.
Organization: Router class with add_get/add_post methods and route_get/route_post
              dispatch methods. Pattern matching converts {param} to regex groups.

Implementation order: 3rd (after auth, before handlers).
"""

from __future__ import annotations

import re
from typing import Callable


# Type alias for handler functions: fn(handler, db_path, **captured_params)
HandlerFn = Callable


class Router:
    """Dispatch table mapping URL patterns to handler functions.

    Patterns use {param} syntax for path segments:
      "/projects/{name}/agents" matches "/projects/minion-factory/agents"
      and passes name="minion-factory" to the handler.

    Routes are matched in registration order — first match wins.
    """

    def __init__(self) -> None:
        # PSEUDO: _get_routes and _post_routes are lists of (compiled_regex, param_names, handler_fn)
        self._get_routes: list[tuple[re.Pattern, list[str], HandlerFn]] = []
        self._post_routes: list[tuple[re.Pattern, list[str], HandlerFn]] = []

    def add_get(self, pattern: str, handler: HandlerFn) -> None:
        """Register a GET route.

        Args:
            pattern: URL pattern like "/projects/{name}/agents"
            handler: Function to call when pattern matches
        """
        # PSEUDO: compile pattern to regex — replace {param} with named capture group
        # PSEUDO: extract param names from pattern
        # PSEUDO: append (regex, param_names, handler) to _get_routes
        compiled, params = _compile_pattern(pattern)
        self._get_routes.append((compiled, params, handler))

    def add_post(self, pattern: str, handler: HandlerFn) -> None:
        """Register a POST route.

        Args:
            pattern: URL pattern like "/spawn"
            handler: Function to call when pattern matches
        """
        # PSEUDO: same as add_get but for _post_routes
        compiled, params = _compile_pattern(pattern)
        self._post_routes.append((compiled, params, handler))

    def route_get(self, path: str) -> tuple[HandlerFn | None, dict[str, str]]:
        """Match a GET request path against registered routes.

        Returns:
            (handler_fn, captured_params) if matched, (None, {}) if no match.
        """
        # PSEUDO: strip trailing slash from path
        # PSEUDO: for each (regex, params, handler) in _get_routes:
        #   match = regex.fullmatch(path)
        #   if match: return (handler, {param: match.group(param) for param in params})
        # PSEUDO: return (None, {})
        return _match_routes(self._get_routes, path)

    def route_post(self, path: str) -> tuple[HandlerFn | None, dict[str, str]]:
        """Match a POST request path against registered routes.

        Returns:
            (handler_fn, captured_params) if matched, (None, {}) if no match.
        """
        # PSEUDO: same as route_get but for _post_routes
        return _match_routes(self._post_routes, path)


def _compile_pattern(pattern: str) -> tuple[re.Pattern, list[str]]:
    """Convert a URL pattern with {param} placeholders to a compiled regex.

    Example: "/projects/{name}/agents" → regex r"^/projects/(?P<name>[^/]+)/agents$"

    Returns:
        (compiled_regex, list_of_param_names)
    """
    # PSEUDO: find all {param} in pattern → extract param names
    # PSEUDO: replace each {param} with (?P<param>[^/]+)
    # PSEUDO: anchor with ^ and $
    # PSEUDO: compile and return
    params = re.findall(r"\{(\w+)\}", pattern)
    regex_str = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$"
    return re.compile(regex_str), params


def _match_routes(routes: list, path: str) -> tuple[HandlerFn | None, dict[str, str]]:
    """Try each route in order, return first match with captured params."""
    # PSEUDO: normalize path — strip trailing slash (but keep "/" as-is)
    clean = path.rstrip("/") or "/"
    for regex, params, handler in routes:
        m = regex.fullmatch(clean)
        if m:
            captured = {p: m.group(p) for p in params}
            return handler, captured
    return None, {}
