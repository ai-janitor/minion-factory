"""Tests for provider error log and classification — BaseProvider helpers.

Purpose: Verify _append_error_log writes timestamped entries, _extract_error_summary
         classifies long lines, and filter_log_line integrates both correctly.
Rationale: Error classification prevents tmux panes from flooding with multi-KB
           JSON blobs. If classification breaks, operators lose visibility.
Responsibility: Test _append_error_log, _extract_error_summary, _classify_error,
                filter_log_line. NOT responsible for build_command or session management.
Organization: Grouped by method — error log I/O, summary extraction, filter integration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Minimal agent_cfg stub — matches the interface BaseProvider expects
# ---------------------------------------------------------------------------


@dataclass
class FakeAgentCfg:
    system: str = ""
    allowed_tools: str = ""
    permission_mode: str = ""
    model: str = ""


# ---------------------------------------------------------------------------
# Concrete subclass for testing — BaseProvider is abstract
# ---------------------------------------------------------------------------


class ProviderHarness:
    """Instantiable wrapper that exposes BaseProvider's non-abstract methods."""

    def __init__(self, agent_name: str = "test-agent"):
        from minion.providers.cli_provider_protocol import BaseProvider
        # We can't instantiate BaseProvider directly — use a minimal concrete subclass
        self._provider = _ConcreteProvider(
            agent_name=agent_name,
            agent_cfg=FakeAgentCfg(),
            use_poll=False,
        )

    @property
    def provider(self):
        return self._provider


class _ConcreteProvider:
    """Minimal concrete provider for testing base class methods."""

    def __init__(self, agent_name, agent_cfg, use_poll):
        from minion.providers.cli_provider_protocol import BaseProvider

        class _Impl(BaseProvider):
            def build_command(self, prompt, use_resume=False):
                return ["echo", prompt]

            def prompt_guardrails(self):
                return ""

        self._impl = _Impl(agent_name=agent_name, agent_cfg=agent_cfg, use_poll=use_poll)

    def __getattr__(self, name):
        return getattr(self._impl, name)


# ---------------------------------------------------------------------------
# _append_error_log — writes timestamped entries to file
# ---------------------------------------------------------------------------


def test_append_error_log_creates_file(tmp_path):
    """_append_error_log creates the log file and parent dirs if needed."""
    from minion.providers.cli_provider_protocol import BaseProvider

    log_path = tmp_path / "logs" / "errors.log"
    BaseProvider._append_error_log(log_path, "test error content")

    assert log_path.exists()
    content = log_path.read_text()
    assert "test error content" in content
    assert "---" in content  # timestamp separator


def test_append_error_log_appends_multiple(tmp_path):
    """_append_error_log appends to existing file, doesn't overwrite."""
    from minion.providers.cli_provider_protocol import BaseProvider

    log_path = tmp_path / "errors.log"
    BaseProvider._append_error_log(log_path, "first error")
    BaseProvider._append_error_log(log_path, "second error")

    content = log_path.read_text()
    assert "first error" in content
    assert "second error" in content


# ---------------------------------------------------------------------------
# _extract_error_summary — classifies long lines
# ---------------------------------------------------------------------------


def test_extract_error_summary_short_line_returns_none():
    """Short lines (<=500 chars) are not classified — return None."""
    from minion.providers.cli_provider_protocol import BaseProvider

    result = BaseProvider._extract_error_summary("short line")
    assert result is None


def test_extract_error_summary_json_error():
    """JSON with error.code and error.message is extracted."""
    from minion.providers.cli_provider_protocol import BaseProvider

    payload = json.dumps({
        "error": {"code": "rate_limit", "message": "Too many requests"},
        "padding": "x" * 600,
    })
    result = BaseProvider._extract_error_summary(payload)
    assert result is not None
    assert "rate_limit" in result


def test_extract_error_summary_http_status():
    """Lines containing HTTP status codes like 429 are classified."""
    from minion.providers.cli_provider_protocol import BaseProvider

    line = "HTTP response: 429 " + "x" * 600
    result = BaseProvider._extract_error_summary(line)
    assert result is not None
    assert "429" in result


def test_extract_error_summary_generic_large():
    """Lines that are just large with no pattern get generic classification."""
    from minion.providers.cli_provider_protocol import BaseProvider

    line = "a" * 600
    result = BaseProvider._extract_error_summary(line)
    assert result is not None
    assert "Large output" in result


# ---------------------------------------------------------------------------
# filter_log_line — integration of classify + log
# ---------------------------------------------------------------------------


def test_filter_log_line_passes_short_lines(tmp_path):
    """Short lines pass through unchanged."""
    p = ProviderHarness()
    log_path = tmp_path / "errors.log"

    result = p.provider.filter_log_line("hello world\n", log_path)
    assert result == "hello world\n"


def test_filter_log_line_classifies_long_lines(tmp_path):
    """Long lines are classified and logged."""
    p = ProviderHarness()
    log_path = tmp_path / "errors.log"

    long_line = "x" * 600 + "\n"
    result = p.provider.filter_log_line(long_line, log_path)

    # Should return a short summary, not the original long line
    assert len(result) < len(long_line)
    assert "test-agent" in result  # agent name in summary
    assert log_path.exists()  # error was logged


def test_filter_log_line_empty_lines_pass(tmp_path):
    """Empty lines pass through unchanged."""
    p = ProviderHarness()
    log_path = tmp_path / "errors.log"

    result = p.provider.filter_log_line("\n", log_path)
    assert result == "\n"


# ---------------------------------------------------------------------------
# _classify_error — provider-specific hook (base falls through to summary)
# ---------------------------------------------------------------------------


def test_classify_error_delegates_to_extract_summary():
    """Base _classify_error delegates to _extract_error_summary."""
    p = ProviderHarness()

    # Short line — should return None
    result = p.provider._classify_error("short")
    assert result is None

    # Long line — should return a summary
    result = p.provider._classify_error("y" * 600)
    assert result is not None
