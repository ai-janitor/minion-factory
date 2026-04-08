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


def _make_fake_popen_child(returncode: int = 1, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a fake subprocess.Popen return value that exits immediately.

    Backlog #338: _poll_inbox now uses Popen + a poll loop, so tests have to
    fake a child that .poll() reports done after the first tick.
    """
    fake = MagicMock()
    fake.pid = 9999
    fake.returncode = returncode
    fake.poll.return_value = returncode  # already exited
    fake.communicate.return_value = (stdout, stderr)
    fake.wait.return_value = returncode
    return fake


class TestPollInboxEnvClass:
    """_poll_inbox must pass MINION_CLASS in the subprocess environment."""

    @patch("minion.daemon.runner._polling.subprocess.Popen")
    def test_poll_inbox_sets_env_class(self, mock_popen: MagicMock) -> None:
        """MINION_CLASS env var is present when _poll_inbox spawns the poll subprocess."""
        mock_popen.return_value = _make_fake_popen_child(returncode=1)
        host = _StubPollingHost(role="coder")

        host._poll_inbox()

        mock_popen.assert_called_once()
        env_passed = mock_popen.call_args.kwargs.get("env")
        assert env_passed is not None, "subprocess.Popen was not called with env kwarg"
        assert ENV_CLASS in env_passed, f"ENV_CLASS ({ENV_CLASS}) missing from subprocess env"
        assert env_passed[ENV_CLASS] == "coder"

    @patch("minion.daemon.runner._polling.subprocess.Popen")
    def test_poll_inbox_uses_agent_role(self, mock_popen: MagicMock) -> None:
        """MINION_CLASS should reflect agent_cfg.role, not be hardcoded."""
        mock_popen.return_value = _make_fake_popen_child(returncode=1)
        host = _StubPollingHost(role="builder")

        host._poll_inbox()

        env_passed = mock_popen.call_args.kwargs.get("env")
        assert env_passed[ENV_CLASS] == "builder"

    @patch("minion.daemon.runner._polling.subprocess.Popen")
    def test_poll_inbox_defaults_to_coder_when_role_empty(self, mock_popen: MagicMock) -> None:
        """When agent_cfg.role is empty/None, MINION_CLASS defaults to 'coder'."""
        mock_popen.return_value = _make_fake_popen_child(returncode=1)
        host = _StubPollingHost(role="")

        host._poll_inbox()

        env_passed = mock_popen.call_args.kwargs.get("env")
        assert env_passed[ENV_CLASS] == "coder"

    @patch("minion.daemon.runner._polling.os.getpgid", side_effect=ProcessLookupError())
    @patch("minion.daemon.runner._polling.subprocess.Popen")
    def test_poll_inbox_aborts_promptly_when_stop_event_is_set(
        self, mock_popen: MagicMock, _mock_getpgid: MagicMock
    ) -> None:
        """Backlog #338 regression: SIGTERM mid-poll must terminate the child.

        When _stop_event is set before the child exits, _poll_inbox must
        terminate the subprocess and return None — not block waiting for
        the inner 30-60s timeout. We patch os.getpgid to bypass the killpg
        path so the test deterministically lands on proc.terminate().
        """
        running_child = MagicMock()
        running_child.pid = 9999
        running_child.poll.return_value = None  # still running
        running_child.communicate.return_value = ("", "")
        running_child.wait.return_value = -15
        mock_popen.return_value = running_child

        host = _StubPollingHost(role="coder")
        host._stop_event.set()  # simulate SIGTERM having already arrived

        result = host._poll_inbox()

        assert result is None
        running_child.terminate.assert_called()


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
