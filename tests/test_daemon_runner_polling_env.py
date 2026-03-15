"""Verify daemon runner PollingMixin sets MINION_CLASS in subprocess env.

Purpose: Regression test for bug where _poll_inbox and _check_available_work
         did not set ENV_CLASS (MINION_CLASS) in the subprocess environment,
         causing the CLI to emit human-readable text instead of JSON.
Rationale: Without MINION_CLASS, cli/main.py defaults to human output mode,
           and the daemon's json.loads() fails with 'non-JSON output'.
Requirement: bugs/daemon-runner-subprocesses-missing-minionclass (req #237).
"""
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from minion.defaults import ENV_CLASS, ENV_DB_PATH, ENV_DOCS_DIR
from minion.daemon.runner._polling import PollingMixin


# ---------------------------------------------------------------------------
# Minimal stub to satisfy PollingMixin's type annotations
# ---------------------------------------------------------------------------


@dataclass
class _FakeAgentConfig:
    role: str = "coder"
    self_dismiss: bool = False
    provider: str = "claude"
    max_history_tokens: int = 100_000


@dataclass
class _FakeSwarmConfig:
    comms_db: Path = Path("/tmp/fake.db")
    docs_dir: Path = Path("/tmp/docs")
    project_dir: Path = Path("/tmp/project")
    logs_dir: Path = Path("/tmp/logs")


class _StubPollingHost(PollingMixin):
    """Minimal host that satisfies the mixin's attribute expectations."""

    def __init__(self, role: str = "coder"):
        self.config = _FakeSwarmConfig()
        self.agent_cfg = _FakeAgentConfig(role=role)
        self.agent_name = "test-agent"
        self._stop_event = threading.Event()
        self._stood_down = False
        self._last_task_id = None
        self.resume_ready = False
        self._provider = MagicMock()
        self._logged: list[str] = []

    def _log(self, message: str) -> None:
        self._logged.append(message)

    def _write_state(self, status: str, **extra: Any) -> None:
        pass

    def _alert_lead_poll(self, message: str) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests — ENV_CLASS must be in subprocess env for both methods
# ---------------------------------------------------------------------------


class TestPollInboxEnvClass:
    """_poll_inbox must pass MINION_CLASS in the subprocess environment."""

    @patch("minion.daemon.runner._polling.subprocess.run")
    def test_poll_inbox_sets_env_class(self, mock_run: MagicMock) -> None:
        """MINION_CLASS env var is present when _poll_inbox calls subprocess.run."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        host = _StubPollingHost(role="coder")

        host._poll_inbox()

        mock_run.assert_called_once()
        env_passed = mock_run.call_args.kwargs.get("env") or mock_run.call_args[1].get("env")
        assert env_passed is not None, "subprocess.run was not called with env kwarg"
        assert ENV_CLASS in env_passed, f"ENV_CLASS ({ENV_CLASS}) missing from subprocess env"
        assert env_passed[ENV_CLASS] == "coder"

    @patch("minion.daemon.runner._polling.subprocess.run")
    def test_poll_inbox_uses_agent_role(self, mock_run: MagicMock) -> None:
        """MINION_CLASS should reflect agent_cfg.role, not be hardcoded."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        host = _StubPollingHost(role="builder")

        host._poll_inbox()

        env_passed = mock_run.call_args.kwargs.get("env") or mock_run.call_args[1].get("env")
        assert env_passed[ENV_CLASS] == "builder"

    @patch("minion.daemon.runner._polling.subprocess.run")
    def test_poll_inbox_defaults_to_coder_when_role_empty(self, mock_run: MagicMock) -> None:
        """When agent_cfg.role is empty/None, MINION_CLASS defaults to 'coder'."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        host = _StubPollingHost(role="")

        host._poll_inbox()

        env_passed = mock_run.call_args.kwargs.get("env") or mock_run.call_args[1].get("env")
        assert env_passed[ENV_CLASS] == "coder"


class TestCheckAvailableWorkEnvClass:
    """_check_available_work must pass MINION_CLASS in the subprocess environment."""

    @patch("minion.daemon.runner._polling.subprocess.run")
    def test_check_work_sets_env_class(self, mock_run: MagicMock) -> None:
        """MINION_CLASS env var is present when _check_available_work calls subprocess.run."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        host = _StubPollingHost(role="coder")

        host._check_available_work()

        mock_run.assert_called_once()
        env_passed = mock_run.call_args.kwargs.get("env") or mock_run.call_args[1].get("env")
        assert env_passed is not None, "subprocess.run was not called with env kwarg"
        assert ENV_CLASS in env_passed, f"ENV_CLASS ({ENV_CLASS}) missing from subprocess env"
        assert env_passed[ENV_CLASS] == "coder"

    @patch("minion.daemon.runner._polling.subprocess.run")
    def test_check_work_uses_agent_role(self, mock_run: MagicMock) -> None:
        """MINION_CLASS should reflect agent_cfg.role, not be hardcoded."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        host = _StubPollingHost(role="recon")

        host._check_available_work()

        env_passed = mock_run.call_args.kwargs.get("env") or mock_run.call_args[1].get("env")
        assert env_passed[ENV_CLASS] == "recon"
