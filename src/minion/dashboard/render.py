"""ANSI screen rendering for the TUI dashboard.
Produces a single string representing the full screen.
clear_and_print() flushes it atomically to stdout.
No external dependencies — pure ANSI escape codes.

Purpose: ANSI screen rendering for the TUI dashboard.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: ANSI screen rendering for the TUI dashboard. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

# === TUI Data Flow Audit ===
# TASKS section:
#   Source: queries.fetch_tasks() → tasks table
#   Filter: status NOT IN ('closed', 'abandoned', 'stale', 'obsolete')
#   Fields: id, status, assigned_to (→assignee), SUBSTR(title,1,40) (→title_short),
#           activity_count, blocked_by, result_file IS NOT NULL (→has_result)
#   Order: status priority (in_progress > assigned > fixed > verified > open), then id ASC
#
# AGENTS section:
#   Source: queries.fetch_agents() → agents table
#   Filter: transport IN ('daemon', 'daemon-ts', 'terminal')
#   Fields: name, agent_class, model (#110), status, last_seen, registered_at,
#           COALESCE(hp_input_tokens,0)+COALESCE(hp_output_tokens,0) (→tokens_used),
#           COALESCE(hp_tokens_limit,0) (→tokens_limit),
#           MAX(last_seen, context_updated_at, registered_at) (→effective_last_seen)
#   Derived: display_status via _agent_display_status(), token_bar(), checklist via filesystem lookup
#
# BACKLOG section (#112):
#   Source: queries.fetch_backlog() → backlog LEFT JOIN tasks
#   Filter: status NOT IN ('closed', 'abandoned')
#   Fields: id, type, title_short, priority, status, promoted_to, task_status, task_assignee
#   Order: priority (critical > high > medium > low), then id ASC
#
# ACTIVITY section:
#   Source: queries.fetch_activity() → transition_log JOIN tasks
#   Filter: entity_type='task', ROW_NUMBER()=1 per task (most recent transition only)
#   Fields: task_id, SUBSTR(title,1,25), from_status, to_status, triggered_by (→agent), created_at (→timestamp)
#   Order: timestamp DESC LIMIT 8

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

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

# Regex to match ANSI escape sequences (SGR, OSC 8 hyperlinks, etc.)
_ANSI_RE = re.compile(r'\033\[[0-9;]*[a-zA-Z]|\033\]8;;[^\033]*\033\\')


def _visible_len(text: str) -> int:
    """Return the visible character length of text after stripping ANSI escape codes."""
    return len(_ANSI_RE.sub('', text))


def _visible_pad(text: str, width: int) -> str:
    """Pad text with trailing spaces so its visible width reaches *width*.

    ANSI escape codes are invisible — Python's f-string padding counts their bytes
    as visible characters, causing columns after ANSI-colored fields to misalign.
    This helper measures visible length (stripping ANSI) and appends the correct
    number of spaces.
    """
    vis = _visible_len(text)
    if vis >= width:
        return text
    return text + ' ' * (width - vis)


# Status → display color
_STATUS_COLORS: dict[str, str] = {
    "in_progress": _GREEN,
    "assigned":    _CYAN,
    "fixed":       _YELLOW,
    "verified":    _YELLOW,
    "open":        _WHITE,
    "blocked":     _RED,
}

# Map long DB status strings to short display names (max 10 chars for column width)
_STATUS_DISPLAY: dict[str, str] = {
    "waiting for work": "waiting",
    "registered": "reg",
}


def token_bar(used: int, limit: int) -> str:
    """Render a colored token usage bar.

    limit <= 100 is the sentinel set before monitoring fires — show unknown.
    """
    if limit <= 100:
        return "░" * BAR_WIDTH + " (---)"
    pct = min(used / limit, 1.0)
    filled = round(pct * BAR_WIDTH)
    color = _RED if pct > 0.75 else _YELLOW if pct > 0.50 else _GREEN
    bar = f"{color}{'█' * filled}{'░' * (BAR_WIDTH - filled)}{_RESET}"
    used_k = f"{used // 1000}k" if used >= 1000 else str(used)
    limit_k = f"{limit // 1000}k" if limit >= 1000 else str(limit)
    return f"{bar} {used_k}/{limit_k}"


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


def _osc8_link(path: str, display: str) -> str:
    """Render an OSC 8 terminal hyperlink (clickable in iTerm2, Kitty, WezTerm, etc.)."""
    url = f"file://{path}"
    return f"\033]8;;{url}\033\\{display}\033]8;;\033\\"


def _relative_time(iso_ts: str | None) -> str:
    """Convert ISO timestamp to human-readable relative time (e.g. '2m ago', '1h ago')."""
    if not iso_ts:
        return "never"
    try:
        # Parse ISO timestamp (may or may not have timezone)
        ts_str = iso_ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        # Normalize to naive local: if aware, convert to local and strip tzinfo
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        # Both dt and now are naive local
        delta = datetime.now() - dt
        secs = int(delta.total_seconds())
        if secs < 0:
            return "now"
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except (ValueError, TypeError):
        return "?"


def _find_checklist(agent_name: str, work_dir: str) -> str | None:
    """Find checklist file for an agent. Convention-based lookup."""
    # Lead checklists: .work/checklists/lead-<name>.md
    lead_path = os.path.join(work_dir, "checklists", f"lead-{agent_name}.md")
    if os.path.exists(lead_path):
        return lead_path
    # Worker/generic checklists: .work/checklists/<name>.md
    worker_path = os.path.join(work_dir, "checklists", f"{agent_name}.md")
    if os.path.exists(worker_path):
        return worker_path
    return None


def _parse_checklist_tally(path: str) -> str | None:
    """Parse the tally from the first line of a checklist file.

    Looks for a pattern like [32/33-0NA] in the first line.
    Returns the tally string (e.g. '32/33-0NA') if found, None otherwise.
    On any error (file not found, permission, etc), returns None.
    """
    try:
        with open(path, "r") as f:
            first_line = f.readline()
        m = re.search(r"\[(\d+/\d+-\d+NA)\]", first_line)
        return m.group(1) if m else None
    except (OSError, UnicodeDecodeError):
        return None


def _staleness_seconds(iso_timestamp: str | None) -> float | None:
    """Return seconds since the given ISO timestamp, or None if unparseable.

    Handles both naive (assumed local) and timezone-aware ISO strings.
    All comparisons use naive local time via datetime.now().
    """
    if not iso_timestamp:
        return None
    try:
        # Handle ISO format with or without timezone info
        ts = iso_timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        # Normalize to naive local: if aware, convert to local and strip tzinfo
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        # Both dt and now are naive local
        delta = datetime.now() - dt
        return delta.total_seconds()
    except (ValueError, TypeError):
        return None


def _agent_display_status(row: sqlite3.Row) -> tuple[str, str]:
    """Compute display status and ANSI color for an agent row.

    Returns (display_status, ansi_color) based on:
    - effective_last_seen staleness
    - whether the agent has ever heartbeated (last_seen is set)
    - the agent's declared status field

    Thresholds:
    - No heartbeat ever + registered <10min ago: "no hb" (dim)
    - No heartbeat ever + registered >=10min ago: "no hb" (red)
    - Last seen <2min ago: use declared status (green/yellow/dim)
    - Last seen 2-5min ago: "idle?" (yellow)
    - Last seen >5min ago: "stale" (red)
    """
    agent_status = row["status"] or "unknown"
    last_seen = row["last_seen"]
    effective = row["effective_last_seen"]
    stale_secs = _staleness_seconds(effective)

    # — Agent has never heartbeated (last_seen is NULL) —
    if not last_seen:
        if stale_secs is not None and stale_secs < 600:
            # Registered recently, just hasn't heartbeated yet
            return ("no hb", _DIM)
        else:
            # Registered a long time ago and never heartbeated — likely dead
            return ("no hb", _RED)

    # — Agent has heartbeated at some point — use effective_last_seen for staleness —
    if stale_secs is None:
        # Can't parse timestamp — fall through to declared status
        pass
    elif stale_secs > 300:
        # Over 5 minutes since last activity — stale
        return ("stale", _RED)
    elif stale_secs > 120:
        # 2-5 minutes — possibly idle
        return ("idle?", _YELLOW)

    # Fresh enough — use declared status with standard colors
    # Map long statuses to short display names that fit 10-char column
    display = _STATUS_DISPLAY.get(agent_status, agent_status)
    if len(display) > 10:
        display = display[:9] + "…"
    if agent_status == "ready":
        return (display, _GREEN)
    elif agent_status == "busy":
        return (display, _YELLOW)
    else:
        return (display, _DIM)


def _short_model(model: str) -> str:
    """Extract short display name from model ID (e.g. 'claude-opus-4-...' → 'opus').

    Backlog #110: Show model column in TUI agent table.
    """
    if not model:
        return ""
    for family in ("opus", "sonnet", "haiku"):
        if family in model:
            return family
    # Truncate long model IDs to fit column
    return model[:8] if len(model) > 8 else model


def _render_agents(agents: list[sqlite3.Row], max_rows: int, work_dir: str = "") -> list[str]:
    """Render agent token bars with checklist links, capped to fit available height.

    Uses effective_last_seen (COALESCE of last_seen, context_updated_at,
    registered_at) to determine staleness. Agents that registered but
    never heartbeated show "no hb" instead of their declared status.
    """
    lines: list[str] = [
        f"{_BOLD}{'NAME':<14}  {'CLASS':<8}  {'MODEL':<8}  {'STATUS':<10}  {'LAST SEEN':<8}  {'TOKENS':<20}  {'CHECKLIST':<14}{_RESET}",
        "─" * 90,
    ]

    visible = agents[:max_rows]
    overflow = len(agents) - len(visible)

    for row in visible:
        bar = token_bar(row["tokens_used"], row["tokens_limit"])
        display_status, status_color = _agent_display_status(row)
        model_short = _short_model(row["model"])

        # Checklist link
        checklist_path = _find_checklist(row["name"], work_dir) if work_dir else None
        if checklist_path:
            tally = _parse_checklist_tally(checklist_path)
            display = tally if tally else "checklist"
            checklist_col = _osc8_link(checklist_path, f"{_CYAN}{display}{_RESET}")
        else:
            checklist_col = f"{_DIM}—{_RESET}"

        last_seen = _relative_time(row["effective_last_seen"])
        seen_color = _RED if "h ago" in last_seen or "d ago" in last_seen or last_seen == "never" else _DIM
        lines.append(
            f"{row['name']:<14}  "
            f"{row['agent_class']:<8}  "
            f"{_DIM}{model_short:<8}{_RESET}  "
            f"{status_color}{display_status:<10}{_RESET}  "
            f"{seen_color}{last_seen:<8}{_RESET}  "
            f"{_visible_pad(bar, 20)}  "
            f"{_visible_pad(checklist_col, 14)}"
        )

    if overflow > 0:
        lines.append(f"  {_DIM}+ {overflow} more agents not shown{_RESET}")

    return lines


# Priority → display color for backlog items
_PRIORITY_COLORS: dict[str, str] = {
    "critical": _RED,
    "high":     _YELLOW,
    "medium":   _WHITE,
    "low":      _DIM,
    "unset":    _DIM,
}


def _render_backlog(backlog: list[sqlite3.Row], max_rows: int = 10) -> list[str]:
    """Render promoted backlog items with their linked task's DAG stage.

    Backlog #112: TUI dashboard should show promoted backlog items.
    Shows type, priority, title, and the task status if promoted.
    Capped to max_rows visible items with overflow indicator (#230).
    """
    lines: list[str] = [
        f"{_BOLD}{'ID':>4}  {'TYPE':<8}  {'PRI':<8}  {'STATUS':<10}  {'TASK':<12}  {'TITLE':<35}{_RESET}",
        "─" * 80,
    ]

    if not backlog:
        lines.insert(0, f"{_BOLD}BACKLOG{_RESET}")
        lines.append(f"  {_DIM}(no active backlog items){_RESET}")
        return lines

    visible = backlog[:max_rows]
    overflow = len(backlog) - len(visible)

    lines.insert(0, f"{_BOLD}BACKLOG{_RESET}")
    for row in visible:
        pri_color = _PRIORITY_COLORS.get(row["priority"], _DIM)
        # Show task stage if promoted, otherwise show backlog status
        if row["promoted_to"]:
            task_info = f"#{row['promoted_to']} {row['task_status']}"
        else:
            task_info = row["status"]
        task_info = _truncate(task_info, 12)
        title = row["title_short"]
        lines.append(
            f"{row['id']:>4}  "
            f"{_truncate(row['type'], 8):<8}  "
            f"{pri_color}{row['priority']:<8}{_RESET}  "
            f"{row['status']:<10}  "
            f"{task_info:<12}  "
            f"{title}"
        )

    if overflow > 0:
        lines.append(f"  {_DIM}+ {overflow} more backlog items not shown{_RESET}")

    return lines


def _render_activity(activity: list[sqlite3.Row]) -> list[str]:
    """Render recent task transition feed."""
    lines: list[str] = [f"{_BOLD}RECENT ACTIVITY{_RESET}", "─" * 60]

    if not activity:
        lines.append(f"  {_DIM}(no recent transitions){_RESET}")
        return lines

    for row in activity:
        ts = _relative_time(row["timestamp"])
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
    work_dir: str = "",
    backlog: list[sqlite3.Row] | None = None,
) -> str:
    """Compose the full screen string from data sections.

    Layout: tasks (top), agents (middle), backlog (if any), activity (bottom).
    Heights are proportional to terminal size.
    """
    lines: list[str] = []

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"{_BOLD}{_CYAN}  ⚡ MINION DASHBOARD{_RESET}  {_DIM}{now_str}{_RESET}"
    lines.append(header)
    lines.append("")

    # Tasks section — upper portion
    lines.append(f"{_BOLD}TASKS{_RESET}")
    task_lines = _render_tasks(tasks, width)
    lines.extend(task_lines)
    lines.append("")

    # Agent section — sized to fit remaining height
    task_section_h = len(task_lines) + 3  # header + blank + section label + blank
    agent_max = max(2, height - task_section_h - 14)  # reserve rows for activity + headers
    lines.append(f"{_BOLD}AGENTS{_RESET}")
    agent_lines = _render_agents(agents, agent_max, work_dir=work_dir)
    lines.extend(agent_lines)
    lines.append("")

    # Backlog section — only shown if there are active backlog items (#112)
    # Cap visible rows to available height, same pattern as agents (#230)
    if backlog:
        backlog_max = max(2, height - len(lines) - 12)  # reserve rows for activity + headers
        lines.extend(_render_backlog(backlog, max_rows=backlog_max))
        lines.append("")

    # Activity feed — fixed 10-line block at bottom
    lines.extend(_render_activity(activity))

    return "\n".join(lines)


def clear_and_print(screen: str) -> None:
    """Clear terminal and print screen string atomically.

    Uses ANSI clear+home then a single print to minimize flicker.
    """
    print("\033[2J\033[H" + screen, end="", flush=True)
