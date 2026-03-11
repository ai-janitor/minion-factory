"""Tests for shell completion generation and installation (F-053).

Purpose: Verify that `minion completions show` outputs actual completion scripts
         for bash, zsh, and fish — not just eval instructions.
Rationale: F-053 identified that Click's built-in shell completion support was
           not properly enabled. These tests ensure the generated scripts are
           valid and the install/show commands work correctly.
Responsibility: Test completion script generation, shell detection, and install idempotency.
Organization: Grouped by subcommand (show, install) and shell type.
"""

from __future__ import annotations

import os

import pytest
from click.testing import CliRunner

from minion.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# show command — generates actual completion scripts
# ---------------------------------------------------------------------------

class TestCompletionsShow:
    """Verify `minion completions show` outputs real completion scripts."""

    def test_show_zsh_outputs_compdef(self, runner):
        """zsh completion script should contain #compdef directive."""
        result = runner.invoke(cli, ["completions", "show", "--shell", "zsh"])
        assert result.exit_code == 0
        assert "#compdef minion" in result.output
        assert "_minion_completion" in result.output

    def test_show_bash_outputs_completion_function(self, runner):
        """bash completion script should contain a completion function."""
        result = runner.invoke(cli, ["completions", "show", "--shell", "bash"])
        assert result.exit_code == 0
        assert "_minion_completion" in result.output
        assert "COMP_WORDS" in result.output

    def test_show_fish_outputs_completion_function(self, runner):
        """fish completion script should contain a completion function."""
        result = runner.invoke(cli, ["completions", "show", "--shell", "fish"])
        assert result.exit_code == 0
        assert "_minion_completion" in result.output
        assert "fish_complete" in result.output.lower() or "COMP_WORDS" in result.output

    def test_show_autodetects_shell(self, runner, monkeypatch):
        """show without --shell should auto-detect from $SHELL."""
        monkeypatch.setenv("SHELL", "/bin/zsh")
        result = runner.invoke(cli, ["completions", "show"])
        assert result.exit_code == 0
        assert "#compdef minion" in result.output

    def test_show_unsupported_shell_fails(self, runner, monkeypatch):
        """Unsupported shell should produce an error."""
        monkeypatch.setenv("SHELL", "/bin/csh")
        result = runner.invoke(cli, ["completions", "show"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# install command — appends to rc file idempotently
# ---------------------------------------------------------------------------

class TestCompletionsInstall:
    """Verify `minion completions install` writes to rc files."""

    def test_install_zsh_creates_entry(self, runner, tmp_path, monkeypatch):
        """install --shell zsh should append eval line to .zshrc."""
        fake_zshrc = tmp_path / ".zshrc"
        fake_zshrc.write_text("# existing content\n")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("SHELL", "/bin/zsh")
        result = runner.invoke(cli, ["completions", "install", "--shell", "zsh"])
        assert result.exit_code == 0
        content = fake_zshrc.read_text()
        assert "_MINION_COMPLETE=zsh_source" in content

    def test_install_idempotent(self, runner, tmp_path, monkeypatch):
        """Running install twice should not duplicate the entry."""
        fake_zshrc = tmp_path / ".zshrc"
        fake_zshrc.write_text('eval "$(_MINION_COMPLETE=zsh_source minion)"\n')
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("SHELL", "/bin/zsh")
        result = runner.invoke(cli, ["completions", "install", "--shell", "zsh"])
        assert result.exit_code == 0
        assert "already installed" in result.output

    def test_install_bash_creates_entry(self, runner, tmp_path, monkeypatch):
        """install --shell bash should append eval line to .bashrc."""
        fake_bashrc = tmp_path / ".bashrc"
        fake_bashrc.write_text("# existing content\n")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("SHELL", "/bin/bash")
        result = runner.invoke(cli, ["completions", "install", "--shell", "bash"])
        assert result.exit_code == 0
        content = fake_bashrc.read_text()
        assert "_MINION_COMPLETE=bash_source" in content


# ---------------------------------------------------------------------------
# _detect_shell helper
# ---------------------------------------------------------------------------

class TestDetectShell:
    """Verify shell detection from $SHELL env var."""

    def test_detect_zsh(self, monkeypatch):
        from minion.cli.completion_cmds import _detect_shell
        monkeypatch.setenv("SHELL", "/bin/zsh")
        assert _detect_shell() == "zsh"

    def test_detect_bash(self, monkeypatch):
        from minion.cli.completion_cmds import _detect_shell
        monkeypatch.setenv("SHELL", "/usr/bin/bash")
        assert _detect_shell() == "bash"

    def test_detect_fish(self, monkeypatch):
        from minion.cli.completion_cmds import _detect_shell
        monkeypatch.setenv("SHELL", "/usr/local/bin/fish")
        assert _detect_shell() == "fish"

    def test_detect_unknown(self, monkeypatch):
        from minion.cli.completion_cmds import _detect_shell
        monkeypatch.setenv("SHELL", "/bin/tcsh")
        assert _detect_shell() == "tcsh"
