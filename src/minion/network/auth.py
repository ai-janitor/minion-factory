"""Authentication utilities — extracted from server.py's _check_token.

Purpose: Centralize token validation logic so both the _Handler class and
         individual handler functions can perform auth checks consistently.
Rationale: As the server grows from 6 to 20+ endpoints, auth logic should live
           in one place. The AuthMixin provides auth-checking methods that
           _Handler can inherit, while check_token stays available as a
           standalone function for testing.
Responsibility: Bearer token validation from Authorization header.
Organization: Standalone check_token function + AuthMixin class for _Handler inheritance.

Implementation order: 1st (no dependencies, other modules may import).
"""

from __future__ import annotations


def check_token(headers: dict, expected: str) -> bool:
    """Validate Bearer token from Authorization header.

    Args:
        headers: Dict-like object with HTTP headers (case-sensitive keys).
        expected: The expected token value. If empty, auth is disabled (dev mode).

    Returns:
        True if token is valid or auth is disabled, False otherwise.
    """
    # PSEUDO: if not expected → return True (no auth configured, dev mode)
    # PSEUDO: auth = headers.get("Authorization", "")
    # PSEUDO: return auth == f"Bearer {expected}"
    if not expected:
        return True
    auth = headers.get("Authorization", "")
    return auth == f"Bearer {expected}"


class AuthMixin:
    """Mixin for BaseHTTPRequestHandler subclasses providing auth convenience methods.

    Expects the class to have:
      - self.token: str (the expected bearer token)
      - self.headers: http.client.HTTPMessage (request headers)
      - self._json_response(status, data): response helper

    Usage: class _Handler(AuthMixin, BaseHTTPRequestHandler): ...
    """

    def require_auth(self) -> bool:
        """Check auth and send 401 if invalid. Returns True if authorized.

        Call at the top of do_GET/do_POST — if it returns False, the 401
        response has already been sent and the caller should return immediately.
        """
        if check_token(dict(self.headers), self.token):
            return True
        self._json_response(401, {"error": "Unauthorized"})
        return False
