"""Shell completion install, show, and generate commands.

Purpose: Set up CLI tab completion for bash/zsh/fish.
Rationale: Reduces onboarding friction — agents and operators can discover commands
           via tab completion instead of --help. Click has built-in completion support
           via the shell_completion module which generates actual completion scripts.
Responsibility: Detect shell, generate completion script, install into rc file idempotently.
Organization: Click group with 'show', 'generate', and 'install' subcommands.

SU-20: Agent experience improvement.
F-053: Enable Click's built-in shell completion support for bash, zsh, fish.
"""

from __future__ import annotations

import os
import sys

import click


# ---------------------------------------------------------------------------
# Supported shells and their Click completion env var values
# ---------------------------------------------------------------------------

_SHELL_SOURCE_VAR = {
    "bash": "bash_source",
    "zsh": "zsh_source",
    "fish": "fish_source",
}


@click.group("completions", short_help="Shell tab completion setup")
def completions():
    """Manage shell tab completion for the minion CLI."""
    pass


def _get_completion_script(shell: str) -> str:
    """Generate the actual completion script for the given shell using Click's shell_completion module.

    Pseudo-logic:
      1. Import Click's shell_completion module
      2. Look up the shell completion class for the requested shell
      3. Instantiate it with our CLI and prog_name='minion'
      4. Call .source() to generate the full completion script
      5. Return the script text
    """
    from click.shell_completion import get_completion_class

    # Get the completion class for this shell (e.g., BashComplete, ZshComplete, FishComplete)
    cls = get_completion_class(shell)
    if cls is None:
        raise click.ClickException(f"Unsupported shell: {shell}. Supported: bash, zsh, fish")

    # We need to get the root CLI group to generate completions against
    from minion.cli.main import cli as root_cli

    # Create a minimal context to get the completion source
    ctx = click.Context(root_cli, info_name="minion")
    comp = cls(root_cli, ctx, "minion", "_MINION_COMPLETE")
    return comp.source()


@completions.command("show")
@click.option("--shell", "-s", type=click.Choice(["bash", "zsh", "fish"]),
              default=None, help="Shell type (default: auto-detect from $SHELL)")
def show(shell: str | None):
    """Print the shell completion script to stdout.

    Pseudo-logic:
      1. Detect shell from --shell option or $SHELL env var
      2. Generate actual completion script via Click's shell_completion module
      3. Print to stdout — user can pipe to eval or redirect to file

    Usage:
      minion completions show                    # auto-detect shell
      minion completions show --shell zsh        # explicit shell
      minion completions show > ~/.minion-complete.zsh  # save to file
      eval "$(minion completions show)"          # activate immediately
    """
    if shell is None:
        shell = _detect_shell()

    if shell not in _SHELL_SOURCE_VAR:
        click.echo(f"Unsupported shell: {shell}. Supported: bash, zsh, fish", err=True)
        sys.exit(1)

    script = _get_completion_script(shell)
    click.echo(script)


@completions.command("install")
@click.option("--shell", "-s", type=click.Choice(["bash", "zsh", "fish"]),
              default=None, help="Shell type (default: auto-detect from $SHELL)")
def install(shell: str | None):
    """Install completion script into shell rc file.

    Pseudo-logic:
      1. Detect shell (bash/zsh/fish) from --shell option or $SHELL
      2. Determine rc file: ~/.bashrc or ~/.zshrc or ~/.config/fish/completions/minion.fish
      3. Generate the source line (eval that invokes Click's completion)
      4. Check if line already in rc file (idempotent)
      5. If not present: append to rc file
      6. Print instructions
    """
    if shell is None:
        shell = _detect_shell()

    if shell == "zsh":
        rc_file = os.path.expanduser("~/.zshrc")
        source_line = 'eval "$(_MINION_COMPLETE=zsh_source minion)"'
    elif shell == "bash":
        rc_file = os.path.expanduser("~/.bashrc")
        source_line = 'eval "$(_MINION_COMPLETE=bash_source minion)"'
    elif shell == "fish":
        rc_file = os.path.expanduser("~/.config/fish/completions/minion.fish")
        source_line = "eval (env _MINION_COMPLETE=fish_source minion)"
    else:
        click.echo(f"Unsupported shell: {shell}. Supported: bash, zsh, fish", err=True)
        sys.exit(1)

    # Check if already installed (idempotent)
    if os.path.exists(rc_file):
        with open(rc_file) as f:
            existing = f.read()
        if source_line in existing:
            click.echo(f"Completion already installed in {rc_file}")
            return

    # For fish, ensure directory exists
    if shell == "fish":
        os.makedirs(os.path.dirname(rc_file), exist_ok=True)

    # Append source line
    with open(rc_file, "a") as f:
        f.write(f"\n# minion CLI tab completion\n{source_line}\n")

    click.echo(f"Completion installed in {rc_file}")
    click.echo(f"Restart your shell or run: source {rc_file}")


def _detect_shell() -> str:
    """Detect current shell from $SHELL env var."""
    shell_path = os.environ.get("SHELL", "")
    basename = os.path.basename(shell_path)
    if "zsh" in basename:
        return "zsh"
    elif "bash" in basename:
        return "bash"
    elif "fish" in basename:
        return "fish"
    return basename or "unknown"
