"""File group — claim, release, list-claims.
File ownership to prevent editing conflicts between agents.

Purpose: File group — claim, release, list-claims.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: File group — claim, release, list-claims. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the file group and its subcommands to the root CLI."""

    @cli.group("file")
    @click.pass_context
    def file_group(ctx: click.Context) -> None:
        """Claim files before editing to prevent conflicts between agents."""
        pass

    @file_group.command("claim")
    @_agent_option(required=True)
    @click.option("--file", "-f", "file_path", required=True)
    @click.pass_context
    def claim_file(ctx: click.Context, agent: str, file_path: str) -> None:
        """Claim a file for exclusive editing."""
        from minion.auth import require_class
        require_class("lead", "coder", "builder")(lambda: None)()
        from minion.filesafety import claim_file as _claim_file
        _output(_claim_file(agent, file_path), ctx.obj["human"])

    @file_group.command("release")
    @_agent_option(required=True)
    @click.option("--file", "-f", "file_path", required=True)
    @click.option("--force", "-F", is_flag=True)
    @click.pass_context
    def release_file(ctx: click.Context, agent: str, file_path: str, force: bool) -> None:
        """Release a file claim."""
        from minion.auth import require_class
        require_class("lead", "coder", "builder")(lambda: None)()
        from minion.filesafety import release_file as _release_file
        _output(_release_file(agent, file_path, force), ctx.obj["human"])

    @file_group.command("list")
    @_agent_option(default="")
    @click.pass_context
    def list_claims(ctx: click.Context, agent: str) -> None:
        """List active file claims."""
        from minion.filesafety import get_claims as _get_claims
        _output(_get_claims(agent), ctx.obj["human"])
