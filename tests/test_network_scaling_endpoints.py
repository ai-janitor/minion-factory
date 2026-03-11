"""Tests for scaling module endpoints — /spawn (POST) and /capacity (GET).

Purpose: Verify scaling endpoints are registered, routable, and return correct
         501 stub responses with the expected schema shape.
Rationale: F-052 found these endpoints defined but with stale comments claiming
           they were unreachable. Tests lock down the contract so regressions
           are caught mechanically.
Responsibility: Scaling endpoint routing and response contract tests.
Organization: One test per endpoint, plus router-level reachability checks."""

from __future__ import annotations

import pytest
from minion.network.router import Router
from minion.network.handlers.scaling import register, handle_spawn, handle_capacity

pytestmark = pytest.mark.unit


def _build_scaling_router() -> Router:
    """Create a router with only scaling endpoints registered."""
    router = Router()
    register(router)
    return router


class TestScalingRouteRegistration:
    """Verify scaling endpoints are properly registered in the router."""

    def test_capacity_get_route_registered(self):
        """GET /capacity must be routable."""
        router = _build_scaling_router()
        handler_fn, params = router.route_get("/capacity")
        assert handler_fn is not None, "/capacity GET route not registered"
        assert handler_fn is handle_capacity

    def test_spawn_post_route_registered(self):
        """POST /spawn must be routable."""
        router = _build_scaling_router()
        handler_fn, params = router.route_post("/spawn")
        assert handler_fn is not None, "/spawn POST route not registered"
        assert handler_fn is handle_spawn

    def test_spawn_not_routable_via_get(self):
        """GET /spawn should NOT match — spawn is POST-only."""
        router = _build_scaling_router()
        handler_fn, _ = router.route_get("/spawn")
        assert handler_fn is None

    def test_capacity_not_routable_via_post(self):
        """POST /capacity should NOT match — capacity is GET-only."""
        router = _build_scaling_router()
        handler_fn, _ = router.route_post("/capacity")
        assert handler_fn is None


class TestScalingEndpointResponses:
    """Verify scaling endpoints return correct 501 stub responses."""

    def test_handle_spawn_returns_501(self, mock_handler):
        """POST /spawn must return 501 with not_implemented status."""
        handle_spawn(mock_handler, db_path=":memory:")
        mock_handler._json_response.assert_called_once()
        status, body = mock_handler._json_response.call_args[0]
        assert status == 501
        assert body["status"] == "not_implemented"
        assert "schema" in body

    def test_handle_capacity_returns_501(self, mock_handler):
        """GET /capacity must return 501 with not_implemented status."""
        handle_capacity(mock_handler, db_path=":memory:")
        mock_handler._json_response.assert_called_once()
        status, body = mock_handler._json_response.call_args[0]
        assert status == 501
        assert body["status"] == "not_implemented"
        assert "schema" in body

    def test_spawn_response_schema_has_agent_field(self, mock_handler):
        """Spawn 501 response schema must define the agent field."""
        handle_spawn(mock_handler, db_path=":memory:")
        _, body = mock_handler._json_response.call_args[0]
        assert "agent" in body["schema"]

    def test_capacity_response_schema_has_machines_field(self, mock_handler):
        """Capacity 501 response schema must define the machines field."""
        handle_capacity(mock_handler, db_path=":memory:")
        _, body = mock_handler._json_response.call_args[0]
        assert "machines" in body["schema"]


@pytest.fixture
def mock_handler():
    """Create a mock handler object with _json_response spy."""
    from unittest.mock import MagicMock
    handler = MagicMock()
    # Let _json_response be a mock so we can inspect calls
    handler._json_response = MagicMock()
    return handler
