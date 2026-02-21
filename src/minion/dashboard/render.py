"""ANSI screen rendering for the TUI dashboard.

Produces a single string representing the full screen.
clear_and_print() flushes it atomically to stdout.
No external dependencies — pure ANSI escape codes.
"""

from __future__ import annotations

import sqlite3

# ANSI escape codes
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_GREEN  = "\033[32m"
_CYAN   = "\033[36m"
_WHITE  = "\033[37m"

BAR_WIDTH = 10

# Status → display color
_STATUS_COLORS: dict[str, str] = {
    "in_progress": _GREEN,
    "assigned":    _CYAN,
    "fixed":       _YELLOW,
    "verified":    _YELLOW,
    "open":        _WHITE,
    "blocked":     _RED,
}


def hp_bar(used: int, limit: int) -> str:
    """Render a colored HP bar.

    limit <= 100 is the sentinel set before monitoring fires — show unknown.
    """
    if limit <= 100:
        return "░" * BAR_WIDTH + " (---)"
    pct = min(used / limit, 1.0)
    filled = round(pct * BAR_WIDTH)
    color = _RED if pct > 0.75 else _YELLOW if pct > 0.50 else _GREEN
    bar = f"{color}{'█' * filled}{'░' * (BAR_WIDTH - filled)}{_RESET}"
    return f"{bar} {pct * 100:.0f}%"


def _truncate(text: str, width: int) -> str:
    """Clip text to width, appending … if truncated."""
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _render_tasks(tasks: list[sqlite3.Row], width: int) -> list[str]:
    """Render task table rows."""
    title_w = max(10, min(40, width - 55))
    header = (
        f"{_BOLD}{'ID':>4}  {'STATUS':<12}  {'ASSIGNEE':<12}  {'TITLE':<{title_w}}  {'ACT':>3}{_RESET}"
    )
    lines = [header, "─" * min(width, title_w + 40)]

    if not tasks:
        lines.append(f"  {_DIM}(no active tasks){_RESET}")
        return lines

    for row in tasks:
        status = row["status"]
        color = _STATUS_COLORS.get(status, _WHITE)
        blocked = ""
        blockers = [int(x) for x in (row["blocked_by"] or "").split(",") if x.strip().isdigit()]
        if blockers:
            blocked = f" {_RED}[BLOCKED: {', '.join(str(b) for b in blockers)}]{_RESET}"
        result_flag = " ✓" if row["has_result"] else ""
        title = _truncate(row["title_short"], title_w)
        assignee = _truncate(row["assignee"], 12)
        line = (
            f"{row['id']:>4}  "
            f"{color}{status:<12}{_RESET}  "
            f"{assignee:<12}  "
            f"{title:<{title_w}}"
            f"{result_flag}"
            f"  {row['activity_count']:>3}"
            f"{blocked}"
        )
        lines.append(line)

    return lines


def _render_agents(agents: list[sqlite3.Row], max_rows: int) -> list[str]:
    """Render agent HP bars, capped to fit available height."""
    lines: list[str] = [
        f"{_BOLD}{'AGENT':<14}  {'CLASS':<8}  {'STATUS':<10}  HP{_RESET}",
        "─" * 60,
    ]

    visible = agents[:max_rows]
    overflow = len(agents) - len(visible)

    for row in visible:
        bar = hp_bar(row["tokens_used"], row["tokens_limit"])
        agent_status = row["status"] or "unknown"
        status_color = _GREEN if agent_status == "ready" else _YELLOW if agent_status == "busy" else _DIM
        lines.append(
            f"{row['name']:<14}  "
            f"{row['agent_class']:<8}  "
            f"{status_color}{agent_status:<10}{_RESET}  "
            f"{bar}"
        )

    if overflow > 0:
        lines.append(f"  {_DIM}+ {overflow} more agents not shown{_RESET}")

    return lines


def _render_activity(activity: list[sqlite3.Row]) -> list[str]:
    """Render recent task transition feed."""
    lines: list[str] = [f"{_BOLD}RECENT ACTIVITY{_RESET}", "─" * 60]

    if not activity:
        lines.append(f"  {_DIM}(no recent transitions){_RESET}")
        return lines

    for row in activity:
        ts = (row["timestamp"] or "")[-8:]  # HH:MM:SS from ISO timestamp
        from_s = row["from_status"] or "—"
        to_s = row["to_status"] or "—"
        agent = row["agent"] or "—"
        title = _truncate(row["title"], 25)
        lines.append(f"  {_DIM}{ts}{_RESET}  #{row['task_id']} {title}  {from_s} → {_GREEN}{to_s}{_RESET}  [{agent}]")

    return lines


def render_screen(
    tasks: list[sqlite3.Row],
    agents: list[sqlite3.Row],
    activity: list[sqlite3.Row],
    width: int,
    height: int,
) -> str:
    """Compose the full screen string from data sections.

    Layout: tasks (top half), agents (middle), activity (bottom).
    Heights are proportional to terminal size.
    """
    lines: list[str] = []

    header = f"{_BOLD}{_CYAN}  ⚡ MINION DASHBOARD{_RESET}"
    lines.append(header)
    lines.append("")

    # Tasks section — upper portion
    lines.append(f"{_BOLD}TASKS{_RESET}")
    task_lines = _render_tasks(tasks, width)
    lines.extend(task_lines)
    lines.append("")

    # Agent HP section — sized to fit remaining height
    task_section_h = len(task_lines) + 3  # header + blank + section label + blank
    agent_max = max(2, height - task_section_h - 14)  # reserve rows for activity + headers
    lines.append(f"{_BOLD}AGENTS{_RESET}")
    agent_lines = _render_agents(agents, agent_max)
    lines.extend(agent_lines)
    lines.append("")

    # Activity feed — fixed 10-line block at bottom
    lines.extend(_render_activity(activity))

    return "\n".join(lines)


def clear_and_print(screen: str) -> None:
    """Clear terminal and print screen string atomically.

    Uses ANSI clear+home then a single print to minimize flicker.
    """
    print("\033[2J\033[H" + screen, end="", flush=True)
