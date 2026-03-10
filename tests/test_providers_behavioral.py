"""Behavioral tests for providers/ — BaseProvider, ClaudeProvider, get_provider.

Purpose: Verify provider registry, command building, and protocol compliance.
         Tests are pure Python — no subprocess execution, no real CLI calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pytest


# ---------------------------------------------------------------------------
# Minimal agent_cfg stub
# ---------------------------------------------------------------------------


@dataclass
class _FakeCfg:
    system: str = ""
    allowed_tools: str = ""
    permission_mode: str = ""
    model: str = ""


# ---------------------------------------------------------------------------
# get_provider — registry lookup
# ---------------------------------------------------------------------------


def test_get_provider_returns_claude():
    """get_provider('claude', ...) returns a ClaudeProvider instance."""
    from minion.providers import get_provider, ClaudeProvider
    cfg = _FakeCfg()
    p = get_provider("claude", "agent-x", cfg, use_poll=False)
    assert isinstance(p, ClaudeProvider)


def test_get_provider_returns_gemini():
    """get_provider('gemini', ...) returns a GeminiProvider instance."""
    from minion.providers import get_provider, GeminiProvider
    cfg = _FakeCfg()
    p = get_provider("gemini", "agent-x", cfg, use_poll=False)
    assert isinstance(p, GeminiProvider)


def test_get_provider_returns_codex():
    """get_provider('codex', ...) returns a CodexProvider instance."""
    from minion.providers import get_provider, CodexProvider
    cfg = _FakeCfg()
    p = get_provider("codex", "agent-x", cfg, use_poll=False)
    assert isinstance(p, CodexProvider)


def test_get_provider_unknown_raises():
    """get_provider with unknown name raises ValueError."""
    from minion.providers import get_provider
    cfg = _FakeCfg()
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("fantasy_llm", "agent-x", cfg, use_poll=False)


# ---------------------------------------------------------------------------
# ClaudeProvider — build_command
# ---------------------------------------------------------------------------


def test_claude_provider_build_command_contains_prompt():
    """ClaudeProvider.build_command includes the prompt string."""
    from minion.providers import ClaudeProvider
    cfg = _FakeCfg()
    p = ClaudeProvider("leo", cfg, use_poll=False)
    cmd = p.build_command("Hello world")
    assert "Hello world" in cmd


def test_claude_provider_build_command_uses_claude_binary():
    """ClaudeProvider command starts with 'claude'."""
    from minion.providers import ClaudeProvider
    cfg = _FakeCfg()
    p = ClaudeProvider("leo", cfg, use_poll=False)
    cmd = p.build_command("test")
    assert cmd[0] == "claude"


def test_claude_provider_build_command_includes_model_flag():
    """When model is set, --model flag is included in command."""
    from minion.providers import ClaudeProvider
    cfg = _FakeCfg(model="claude-3-5-sonnet-20241022")
    p = ClaudeProvider("leo", cfg, use_poll=False)
    cmd = p.build_command("test")
    assert "--model" in cmd
    assert "claude-3-5-sonnet-20241022" in cmd


def test_claude_provider_no_model_flag_when_empty():
    """When model is empty, no --model flag in command."""
    from minion.providers import ClaudeProvider
    cfg = _FakeCfg(model="")
    p = ClaudeProvider("leo", cfg, use_poll=False)
    cmd = p.build_command("test")
    assert "--model" not in cmd


def test_claude_provider_resume_includes_resume_flag():
    """When use_resume=True and session_id is set, --resume flag appears."""
    from minion.providers import ClaudeProvider
    cfg = _FakeCfg()
    p = ClaudeProvider("leo", cfg, use_poll=True)
    p.session_id = "abc123"
    cmd = p.build_command("test", use_resume=True)
    assert "--resume" in cmd
    assert "abc123" in cmd


def test_claude_provider_system_prompt_included():
    """When system is set, --system-prompt is included."""
    from minion.providers import ClaudeProvider
    cfg = _FakeCfg(system="You are a helpful agent.")
    p = ClaudeProvider("leo", cfg, use_poll=False)
    cmd = p.build_command("test")
    assert "--system-prompt" in cmd


# ---------------------------------------------------------------------------
# BaseProvider — protocol compliance (prompt_guardrails is abstract)
# ---------------------------------------------------------------------------


def test_all_providers_implement_prompt_guardrails():
    """All registered providers implement prompt_guardrails()."""
    from minion.providers import ClaudeProvider, GeminiProvider, CodexProvider, OpencodeProvider
    cfg = _FakeCfg()
    for ProviderCls in (ClaudeProvider, GeminiProvider, CodexProvider, OpencodeProvider):
        p = ProviderCls("agent", cfg, use_poll=False)
        result = p.prompt_guardrails()
        assert isinstance(result, str), f"{ProviderCls.__name__}.prompt_guardrails() must return str"


def test_all_providers_implement_build_command():
    """All registered providers implement build_command()."""
    from minion.providers import ClaudeProvider, GeminiProvider, CodexProvider, OpencodeProvider
    cfg = _FakeCfg()
    for ProviderCls in (ClaudeProvider, GeminiProvider, CodexProvider, OpencodeProvider):
        p = ProviderCls("agent", cfg, use_poll=False)
        cmd = p.build_command("hello")
        assert isinstance(cmd, list) and len(cmd) > 0, f"{ProviderCls.__name__}.build_command() must return non-empty list"


# ---------------------------------------------------------------------------
# BaseProvider — supports_resume default
# ---------------------------------------------------------------------------


def test_base_provider_supports_resume_default_true():
    """BaseProvider.supports_resume defaults to True."""
    from minion.providers import ClaudeProvider
    cfg = _FakeCfg()
    p = ClaudeProvider("leo", cfg, use_poll=False)
    assert p.supports_resume is True
