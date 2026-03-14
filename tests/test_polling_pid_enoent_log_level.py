"""Tests: polling.py PID file removal logs DEBUG for ENOENT, ERROR for other OSError.

Purpose: Verify the ENOENT race condition on PID file removal is logged at DEBUG,
         not ERROR. Any other OSError (e.g., permission denied) must still log at ERROR.
Rationale: ENOENT on pidfile removal is expected when another process cleans up first.
           Logging it as ERROR creates noise and misleads operators.
"""

from __future__ import annotations

import errno
import os
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _remove_pidfile
# ---------------------------------------------------------------------------


def test_remove_pidfile_enoent_logs_debug(tmp_path):
    """_remove_pidfile: FileNotFoundError (ENOENT) → DEBUG, not ERROR."""
    from minion.polling import _remove_pidfile

    with (
        patch("minion.polling._poll_pidfile", return_value=str(tmp_path / "agent.pid")),
        patch("os.remove", side_effect=FileNotFoundError(errno.ENOENT, "No such file")),
        patch("minion.polling.logger") as mock_logger,
    ):
        _remove_pidfile("test-agent")

    mock_logger.debug.assert_called_once()
    mock_logger.error.assert_not_called()


def test_remove_pidfile_other_oserror_logs_error(tmp_path):
    """_remove_pidfile: non-ENOENT OSError (e.g., EPERM) → ERROR."""
    from minion.polling import _remove_pidfile

    with (
        patch("minion.polling._poll_pidfile", return_value=str(tmp_path / "agent.pid")),
        patch("os.remove", side_effect=OSError(errno.EPERM, "Permission denied")),
        patch("minion.polling.logger") as mock_logger,
    ):
        _remove_pidfile("test-agent")

    mock_logger.error.assert_called_once()
    mock_logger.debug.assert_not_called()


def test_remove_pidfile_success_no_log(tmp_path):
    """_remove_pidfile: successful removal → no log calls."""
    pid_path = tmp_path / "agent.pid"
    pid_path.write_text("12345")

    from minion.polling import _remove_pidfile

    with (
        patch("minion.polling._poll_pidfile", return_value=str(pid_path)),
        patch("minion.polling.logger") as mock_logger,
    ):
        _remove_pidfile("test-agent")

    mock_logger.debug.assert_not_called()
    mock_logger.error.assert_not_called()


# ---------------------------------------------------------------------------
# _kill_existing_poll — finally block (stale pidfile removal)
# ---------------------------------------------------------------------------


def test_kill_existing_poll_stale_pidfile_enoent_logs_debug(tmp_path):
    """_kill_existing_poll finally: FileNotFoundError on stale pidfile → DEBUG, not ERROR."""
    from minion.polling import _kill_existing_poll

    pid_path = tmp_path / "agent.pid"
    pid_path.write_text("99999")  # PID that won't exist

    def fake_remove(path):
        raise FileNotFoundError(errno.ENOENT, "No such file", path)

    with (
        patch("minion.polling._poll_pidfile", return_value=str(pid_path)),
        patch("os.path.exists", return_value=True),
        patch("os.kill", side_effect=ProcessLookupError),  # process not running
        patch("os.remove", fake_remove),
        patch("minion.polling.logger") as mock_logger,
    ):
        result = _kill_existing_poll("test-agent")

    mock_logger.debug.assert_called_once()
    mock_logger.error.assert_not_called()


def test_kill_existing_poll_stale_pidfile_other_oserror_logs_error(tmp_path):
    """_kill_existing_poll finally: non-ENOENT OSError on stale pidfile removal → ERROR."""
    from minion.polling import _kill_existing_poll

    pid_path = tmp_path / "agent.pid"
    pid_path.write_text("99999")

    def fake_remove(path):
        raise OSError(errno.EPERM, "Permission denied", path)

    with (
        patch("minion.polling._poll_pidfile", return_value=str(pid_path)),
        patch("os.path.exists", return_value=True),
        patch("os.kill", side_effect=ProcessLookupError),
        patch("os.remove", fake_remove),
        patch("minion.polling.logger") as mock_logger,
    ):
        _kill_existing_poll("test-agent")

    mock_logger.error.assert_called_once()
    mock_logger.debug.assert_not_called()
