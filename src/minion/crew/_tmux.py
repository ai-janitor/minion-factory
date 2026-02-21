"""Shared tmux helpers — pane management, Terminal.app integration."""

from __future__ import annotations

import os
import subprocess
import sys


CLASS_COLORS: dict[str, str] = {
    "lead":    "colour2",   # green
    "coder":   "colour1",   # red
    "builder": "colour3",   # yellow
    "oracle":  "colour4",   # blue
    "recon":   "colour5",   # magenta
    "planner": "colour6",   # cyan
    "auditor": "colour9",   # bright red
}


def open_terminal_with_command(cmd: str, title: str = "") -> None:
    """Open a new Terminal.app window running the given command."""
    import platform
    if platform.system() != "Darwin":
        return
    escaped_cmd = cmd.replace('"', '\\"')
    title_line = f'set custom title of front window to "{title}"' if title else ""
    script = f'''
    tell application "Terminal"
        do script "{escaped_cmd}"
        activate
        {title_line}
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WARNING: open_terminal_with_command failed: {result.stderr.strip()}", file=sys.stderr)


def _terminal_bounds(pane_count: int) -> tuple[int, int, int, int]:
    """Calculate Terminal.app window bounds for N tmux panes.

    Tiled layout: grid of ceil(sqrt(N)) cols x ceil(N/cols) rows.
    Each pane targets 80 cols x 24 rows. Character cell ~7px wide, ~15px tall.
    Add padding for tmux borders and pane title bars.
    """
    import math
    cols = math.ceil(math.sqrt(pane_count)) if pane_count > 0 else 1
    rows = math.ceil(pane_count / cols) if cols > 0 else 1

    # Per-pane: 80 chars * 7px + 2px border
    pane_w = 80 * 7 + 2
    # Per-pane: 24 lines * 15px + 18px title bar + 2px border
    pane_h = 24 * 15 + 18 + 2

    width = cols * pane_w
    height = rows * pane_h

    return (0, 0, width, height)


def open_tmux_terminal(tmux_session: str, pane_count: int = 1) -> None:
    """Open Terminal.app attached to a tmux session, sized for pane_count panes."""
    import platform
    if platform.system() != "Darwin":
        return
    title = f"workers:{tmux_session}"
    escaped_cmd = f"tmux attach -t {tmux_session}".replace('"', '\\"')
    x0, y0, x1, y1 = _terminal_bounds(pane_count)
    script = f'''
    tell application "Terminal"
        do script "{escaped_cmd}"
        activate
        set custom title of front window to "{title}"
        set bounds of front window to {{{x0}, {y0}, {x1}, {y1}}}
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WARNING: open_tmux_terminal failed: {result.stderr.strip()}", file=sys.stderr)


def close_terminal_by_title(title: str) -> None:
    """Close Terminal.app windows matching a title."""
    import platform
    if platform.system() != "Darwin":
        return
    script = f'''
    tell application "Terminal"
        repeat with w in windows
            if custom title of w contains "{title}" then
                close w saving no
            end if
        end repeat
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WARNING: close_terminal_by_title failed: {result.stderr.strip()}", file=sys.stderr)


def kill_tmux_pane_by_title(agent_name: str) -> None:
    """Kill a tmux pane whose title matches an agent name."""
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F",
             "#{session_name}:#{window_name}.#{pane_index} #{pane_title}"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return
        for line in result.stdout.strip().splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                title = parts[1]
                if title == agent_name or title.startswith(f"{agent_name}("):
                    subprocess.run(["tmux", "kill-pane", "-t", parts[0]],
                                   capture_output=True)
                    return
    except FileNotFoundError:
        print("WARNING: tmux not found — cannot kill pane", file=sys.stderr)


def update_pane_task(agent_name: str, task_label: str = "") -> None:
    """Update a tmux pane title to show current task without changing agent name.

    Finds the pane whose title starts with 'agent(role)' and appends the task label.
    If task_label is empty, resets to just 'agent(role) model'.
    """
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F",
             "#{session_name}:#{window_name}.#{pane_index} #{pane_title}"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return
        for line in result.stdout.strip().splitlines():
            parts = line.split(" ", 1)
            if len(parts) != 2:
                continue
            pane_target, title = parts
            # Match pane by agent name prefix: "agent(role) model ..."
            if not (title == agent_name or title.startswith(f"{agent_name}(")):
                continue
            # Keep the base title (agent(role) model) and append task
            base = title.split(" | ")[0]  # strip any previous task suffix
            new_title = f"{base} | {task_label}" if task_label else base
            subprocess.run(
                ["tmux", "select-pane", "-t", pane_target, "-T", new_title],
                capture_output=True,
            )
            return
    except FileNotFoundError:
        pass


def kill_all_crews() -> None:
    """Stop all minion-swarm configs and kill all crew- tmux sessions."""
    from minion.crew.daemon import stop_swarm
    config_dir = os.path.expanduser("~/.minion-swarm")
    if os.path.isdir(config_dir):
        for fname in os.listdir(config_dir):
            if fname.endswith(".yaml"):
                stop_swarm(os.path.join(config_dir, fname))

    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        for session in result.stdout.strip().splitlines():
            if session.startswith("crew-"):
                close_terminal_by_title(f"workers:{session}")
                subprocess.run(["tmux", "kill-session", "-t", session],
                               capture_output=True)


def _short_model(model: str, provider: str = "") -> str:
    """Extract short display name from model ID or provider."""
    for family in ("opus", "sonnet", "haiku"):
        if family in model:
            return family
    if model:
        return model
    if provider and provider != "claude":
        return provider
    return ""


def style_pane(tmux_session: str, pane_idx: int, agent: str, role: str, model: str = "", provider: str = "") -> None:
    """Set pane title and class color."""
    color = CLASS_COLORS.get(role, "colour7")
    base_title = f"{agent}({role})" if role else agent
    short = _short_model(model, provider)
    pane_title = f"{base_title} {short}" if short else base_title
    pane_target = f"{tmux_session}:{0}.{pane_idx}"

    r1 = subprocess.run([
        "tmux", "select-pane", "-t", pane_target, "-T", pane_title,
    ], capture_output=True, text=True)
    if r1.returncode != 0:
        print(f"WARNING: style_pane title failed for {pane_target}: {r1.stderr.strip()}", file=sys.stderr)
    r2 = subprocess.run([
        "tmux", "set-option", "-p", "-t", pane_target, "@cc", color,
    ], capture_output=True, text=True)
    if r2.returncode != 0:
        print(f"WARNING: style_pane color failed for {pane_target}: {r2.stderr.strip()}", file=sys.stderr)


def finalize_layout(tmux_session: str, is_new: bool, pane_count: int = 1) -> None:
    """Apply tiled layout, border colors, and open terminal if new."""
    for cmd, label in [
        (["tmux", "select-layout", "-t", tmux_session, "tiled"], "layout"),
        (["tmux", "set-option", "-t", tmux_session, "pane-border-status", "top"], "border-status"),
        (["tmux", "set-option", "-t", tmux_session, "pane-border-format",
          "#[fg=#{@cc}] #{pane_title} #[default]"], "border-format"),
    ]:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"WARNING: finalize_layout {label} failed for {tmux_session}: {r.stderr.strip()}", file=sys.stderr)

    if is_new:
        open_tmux_terminal(tmux_session, pane_count)
