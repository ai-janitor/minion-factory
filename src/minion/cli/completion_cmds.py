"""Shell completion install and show commands.

Purpose: Set up CLI tab completion for bash/zsh.
Rationale: Reduces onboarding friction — agents and operators can discover commands
           via tab completion instead of --help. Click has built-in completion support.
Responsibility: Detect shell, generate completion script, install into rc file idempotently.
Organization: Click group with 'show' and 'install' subcommands.

SU-20: Agent experience improvement.
"""

from __future__ import annotations

import os
import sys

import click


@click.group("completions", short_help="Shell tab completion setup")
def completions():
    """Manage shell tab completion for the minion CLI."""
    pass


@completions.command("show")
def show():
    """Print completion script to stdout.

    Pseudo-logic:
      1. Detect shell from $SHELL env var
      2. Generate completion script via Click's built-in mechanism
      3. Print to stdout — user can pipe to eval or redirect to file
    """
    shell = _detect_shell()
    if shell == "zsh":
        click.echo('eval "$(_MINION_COMPLETE=zsh_source minion)"')
    elif shell == "bash":
        click.echo('eval "$(_MINION_COMPLETE=bash_source minion)"')
    elif shell == "fish":
        click.echo('eval (env _MINION_COMPLETE=fish_source minion)')
    else:
        click.echo(f"Unsupported shell: {shell}. Supported: bash, zsh, fish", err=True)
        sys.exit(1)


@completions.command("install")
def install():
    """Install completion script into shell rc file.

    Pseudo-logic:
      1. Detect shell (bash/zsh) from $SHELL
      2. Determine rc file: ~/.bashrc or ~/.zshrc
      3. Generate the source line
      4. Check if line already in rc file (idempotent)
      5. If not present: append to rc file
      6. Print instructions
    """
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
