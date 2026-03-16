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
#   Filter: status NOT IN (TERMINAL_STATUSES) — sourced from tasks.dag.TERMINAL_STATUSES
#   Fields: id, status, assigned_to (→assignee), SUBSTR(title,1,40) (→title_short),
#           activity_count, blocked_by, result_file IS NOT NULL (→has_result)
#   Order: status priority (in_progress > assigned > fixed > verified > open), then id ASC
#
# AGENTS section:
#   Source: queries.fetch_agents() → agents table
#   Filter: transport IN ('daemon', 'daemon-ts', 'terminal')
#   Fields: name, agent_class, model (#110), status, transport (#250), last_seen, registered_at,
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

from minion.tasks.dag import TERMINAL_STATUSES

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
    "fixed":          _YELLOW,
    "verified":       _YELLOW,
    "findings_ready": _YELLOW,
    "assessed":       _YELLOW,
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
        status_col = _visible_pad(f"{color}{status}{_RESET}", 12)
        line = (
            f"{row['id']:>4}  "
            f"{status_col}  "
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
    """Find checklist file for an agent. Convention-based lookup.

    Search order (project-local .work/checklists/ ONLY):
    1. <work_dir>/checklists/lead-<name>.md  (lead checklist)
    2. <work_dir>/checklists/<name>.md        (worker/generic checklist)

    The TUI reads from the project's .work/checklists/ — that's the correct
    location. Global ~/.minion_work/checklists/ is NOT searched here.
    """
    if not work_dir:
        return None

    checklist_dir = os.path.join(work_dir, "checklists")

    # Lead checklists: lead-<name>.md
    lead_path = os.path.join(checklist_dir, f"lead-{agent_name}.md")
    if os.path.exists(lead_path):
        return lead_path
    # Worker/generic checklists: <name>.md
    worker_path = os.path.join(checklist_dir, f"{agent_name}.md")
    if os.path.exists(worker_path):
        return worker_path
    return None


def _parse_checklist_tally(path: str) -> str | None:
    """Parse the tally from a checklist file.

    Strategy:
    1. First, look for explicit [32/33-0NA] tally in the first line (lead convention)
    2. Fallback: count [x] and [ ] checkboxes in the full content (universal)

    Returns tally string (e.g. '32/33-0NA' or '3/33') if found, None otherwise.
    On any error (file not found, permission, etc), returns None.
    """
    try:
        with open(path, "r") as f:
            content = f.read()
        if not content:
            return None
        first_line = content.split("\n", 1)[0]
        # Try explicit tally format first
        m = re.search(r"\[(\d+/\d+-\d+NA)\]", first_line)
        if m:
            return m.group(1)
        # Fallback: count checkboxes from full content
        done = len(re.findall(r"- \[x\]", content, re.IGNORECASE))
        total = done + len(re.findall(r"- \[ \]", content))
        if total > 0:
            return f"{done}/{total}"
        return None
    except (OSError, UnicodeDecodeError) as e:
        logger.error("Failed to parse checklist tally from %s: %s", path, e)
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
    elif agent_status in ("busy", "working"):
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
        f"{_BOLD}{'NAME':<14}  {'CLASS':<8}  {'MODEL':<8}  {'XPORT':<20}  {'STATUS':<10}  {'LAST SEEN':<8}  {'TOKENS':<20}  {'CHECKLIST':<14}{_RESET}",
        "─" * 100,
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
            display = tally if tally else "ERROR"
            checklist_col = _osc8_link(checklist_path, f"{_CYAN}{display}{_RESET}")
        else:
            checklist_col = f"{_DIM}—{_RESET}"

        last_seen = _relative_time(row["effective_last_seen"])
        seen_color = _RED if "h ago" in last_seen or "d ago" in last_seen or last_seen == "never" else _DIM
        model_col = _visible_pad(f"{_DIM}{model_short}{_RESET}", 8)
        transport = row["transport"] or "?"
        try:
            spawned_from = row["spawned_from"] or ""
        except (KeyError, IndexError):
            spawned_from = ""
        xport_display = f"{spawned_from}/{transport}" if spawned_from else transport
        transport_col = _visible_pad(f"{_DIM}{xport_display}{_RESET}", 20)
        status_col = _visible_pad(f"{status_color}{display_status}{_RESET}", 10)
        seen_col = _visible_pad(f"{seen_color}{last_seen}{_RESET}", 8)
        lines.append(
            f"{row['name']:<14}  "
            f"{row['agent_class']:<8}  "
            f"{model_col}  "
            f"{transport_col}  "
            f"{status_col}  "
            f"{seen_col}  "
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
        f"{_BOLD}{'#':>2}  {'ID':>4}  {'TYPE':<8}  {'PRI':<8}  {'STATUS':<10}  {'TASK':<12}  {'UPDATED':<8}  {'TITLE':<35}{_RESET}",
        "─" * 92,
    ]

    if not backlog:
        lines.insert(0, f"{_BOLD}BACKLOG{_RESET}")
        lines.append(f"  {_DIM}(no active backlog items){_RESET}")
        return lines

    visible = backlog[:max_rows]
    overflow = len(backlog) - len(visible)

    lines.insert(0, f"{_BOLD}BACKLOG{_RESET}")
    for idx, row in enumerate(visible):
        pri_color = _PRIORITY_COLORS.get(row["priority"], _DIM)
        # Show task stage if promoted, otherwise show backlog status
        if row["promoted_to"]:
            task_info = f"#{row['promoted_to']} {row['task_status']}"
        else:
            task_info = row["status"]
        task_info = _truncate(task_info, 12)
        title = row["title_short"]
        updated = _relative_time(row["updated_at"]) if row["updated_at"] else ""
        pri_col = _visible_pad(f"{pri_color}{row['priority']}{_RESET}", 8)
        updated_col = _visible_pad(f"{_DIM}{updated}{_RESET}", 8)
        # Show 1-9 index for keyboard navigation, blank for items beyond 9
        key_hint = f"{_CYAN}{idx + 1}{_RESET}" if idx < 9 else " "
        key_col = _visible_pad(key_hint, 2)
        lines.append(
            f"{key_col}  "
            f"{row['id']:>4}  "
            f"{_truncate(row['type'], 8):<8}  "
            f"{pri_col}  "
            f"{row['status']:<10}  "
            f"{task_info:<12}  "
            f"{updated_col}  "
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
        # Fixed-width columns: ts(8), id(5), title(25), from(10), arrow+to(12), agent(12)
        ts_col = _visible_pad(f"{_DIM}{ts}{_RESET}", 8)
        id_col = f"#{row['task_id']:<4}"
        title_col = f"{title:<25}"
        from_col = f"{from_s:<10}"
        to_col = _visible_pad(f"→ {_GREEN}{to_s}{_RESET}", 12)
        agent_col = f"[{agent}]"
        lines.append(f"  {ts_col}  {id_col} {title_col}  {from_col} {to_col}  {agent_col}")

    return lines


# Click map type: maps terminal row number (1-indexed) → action tuple
# Actions: ("lineage", backlog_id) | ("browser",)
ClickMap = dict[int, tuple]


def render_screen(
    tasks: list[sqlite3.Row],
    agents: list[sqlite3.Row],
    activity: list[sqlite3.Row],
    width: int,
    height: int,
    work_dir: str = "",
    backlog: list[sqlite3.Row] | None = None,
    activity_task_to_backlog: dict[int, int] | None = None,
) -> tuple[str, ClickMap]:
    """Compose the full screen string from data sections.

    Returns (screen_string, click_map) where click_map maps terminal row numbers
    to navigation actions for mouse click handling.

    Layout: tasks (top), agents (middle), backlog (if any), activity (bottom).
    Heights are proportional to terminal size.

    Big-O: O(T + A + B + V) where T = tasks, A = agents, B = backlog items,
    V = activity entries. Each section renders linearly. Agent rendering does
    O(A) filesystem lookups for checklist files. Hot path — called every 2s.
    """
    lines: list[str] = []
    click_map: ClickMap = {}

    from importlib.metadata import version as pkg_version
    try:
        ver = pkg_version("minion-factory")
    except Exception:
        ver = "?"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"{_BOLD}{_CYAN}  ⚡ MINION DASHBOARD{_RESET}  {_DIM}v{ver}  {now_str}{_RESET}"
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
        # Record line offset before backlog rows start
        # +1 for "BACKLOG" header, +1 for column header, +1 for separator
        backlog_start_line = len(lines) + 3
        lines.extend(_render_backlog(backlog, max_rows=backlog_max))
        # Map each backlog row to its click action (line numbers are 1-indexed for terminal)
        for idx, row in enumerate(backlog[:backlog_max]):
            # +1 because terminal rows are 1-indexed
            click_map[backlog_start_line + idx + 1] = ("lineage", row["id"])
        lines.append("")

    # Activity feed — fixed 10-line block at bottom
    # Record line offset before activity rows start
    # +1 for "RECENT ACTIVITY" header, +1 for separator
    activity_start_line = len(lines) + 2
    lines.extend(_render_activity(activity))
    # Map activity rows to lineage actions (if we can resolve task → backlog)
    if activity_task_to_backlog:
        for idx, row in enumerate(activity):
            task_id = row["task_id"]
            if task_id in activity_task_to_backlog:
                click_map[activity_start_line + idx + 1] = ("lineage", activity_task_to_backlog[task_id])

    # Navigation hint — always visible
    lines.append("")
    lines.append(f"  {_DIM}Click backlog/activity row for lineage │ L: browse all │ q: quit{_RESET}")

    return "\n".join(lines), click_map


def _render_dag_inline(flow_type: str, current_status: str, transitions: list) -> str:
    """Render a task's DAG progression inline, showing which stages have been visited.

    Uses the task's flow definition to render the full stage pipeline,
    marking completed stages (from transition log) and the current position.

    Example: open → assigned → [IN_PROGRESS] → fixed → verified → closed
    """
    try:
        from minion.tasks.loader import load_flow
        flow = load_flow(flow_type)
        return flow.render_dag(current_status)
    except Exception:
        # Fallback: just show transition history
        if not transitions:
            return current_status
        parts = []
        for t in transitions:
            if t["from_status"] and not parts:
                parts.append(t["from_status"])
            parts.append(t["to_status"])
        return " → ".join(parts)


def _render_lineage(lineage: dict, width: int, height: int) -> list[str]:
    """Render the full lineage tree for a backlog item.

    Shows: backlog header → requirements → tasks per requirement → DAG per task.
    Each requirement is a branch in the tree. Each task shows its DAG inline.
    """
    lines: list[str] = []
    bk = lineage["backlog"]
    if not bk:
        lines.append(f"  {_DIM}(backlog item not found){_RESET}")
        return lines

    # Header
    lines.append(
        f"{_BOLD}{_CYAN}  ⚡ LINEAGE: Backlog #{bk['id']}{_RESET}"
    )
    lines.append(f"  {_BOLD}{bk['title']}{_RESET}")
    lines.append(
        f"  Status: {_GREEN}{bk['status']}{_RESET}  │  "
        f"Type: {bk['type']}  │  "
        f"Priority: {bk['priority']}"
    )
    if bk["promoted_to"]:
        lines.append(f"  {_DIM}Path: {bk['promoted_to']}{_RESET}")
    lines.append("")

    # Backlog description from README.md (#246: show backlog description in lineage view)
    readme_content = lineage.get("readme_content")
    if readme_content:
        lines.append(f"  {_BOLD}DESCRIPTION{_RESET}")
        lines.append("  " + "─" * min(width - 4, 60))
        # Render README content, truncated to fit available height
        # Reserve space for requirements tree below (at least 20 lines)
        max_readme_lines = max(5, height - len(lines) - 20)
        readme_lines = readme_content.splitlines()
        for i, rline in enumerate(readme_lines[:max_readme_lines]):
            lines.append(f"  {_DIM}{rline}{_RESET}")
        if len(readme_lines) > max_readme_lines:
            lines.append(f"  {_DIM}... ({len(readme_lines) - max_readme_lines} more lines){_RESET}")
        lines.append("")
    else:
        lines.append(f"  {_DIM}(no description available){_RESET}")
        lines.append("")

    reqs = lineage["requirements"]
    if not reqs:
        lines.append(f"  {_DIM}(no requirements linked — not yet promoted or path mismatch){_RESET}")
        return lines

    # Render each requirement branch
    for i, req_entry in enumerate(reqs):
        req = req_entry["req"]
        tasks = req_entry["tasks"]
        is_last_req = (i == len(reqs) - 1)
        branch = "└" if is_last_req else "├"
        cont = " " if is_last_req else "│"

        # Requirement line
        # Extract the short suffix from the file_path for display
        req_path = req["file_path"]
        # Show just the last segment (requirement slug)
        parts = req_path.rsplit("/", 1)
        req_slug = parts[-1] if len(parts) > 1 else req_path
        req_slug = _truncate(req_slug, max(30, width - 40))

        stage_color = _GREEN if req["stage"] in ("completed", "done") else _YELLOW
        lines.append(
            f"  {branch}── {_BOLD}Req #{req['id']}{_RESET}: "
            f"{req_slug}  "
            f"[{stage_color}{req['stage']}{_RESET}]"
        )

        if not tasks:
            lines.append(f"  {cont}   {_DIM}(no tasks){_RESET}")
            continue

        # Render each task under this requirement
        for j, task_entry in enumerate(tasks):
            task = task_entry["task"]
            transitions = task_entry["transitions"]
            is_last_task = (j == len(tasks) - 1)
            t_branch = "└" if is_last_task else "├"
            t_cont = " " if is_last_task else "│"

            # Task status color
            status = task["status"]
            s_color = _STATUS_COLORS.get(status, _WHITE)
            if status in TERMINAL_STATUSES:
                s_color = _DIM

            title = _truncate(task["title"], max(30, width - 50))
            assignee = task["assigned_to"] or "—"

            lines.append(
                f"  {cont}   {t_branch}── Task #{task['id']}: "
                f"{title}  "
                f"[{s_color}{status}{_RESET}]  "
                f"{_DIM}{assignee}{_RESET}"
            )

            # DAG progression line
            dag_str = _render_dag_inline(task["flow_type"], status, transitions)
            lines.append(f"  {cont}   {t_cont}   {_DIM}DAG:{_RESET} {dag_str}")

            # Transition history (compact)
            if transitions:
                hist_parts = []
                for t in transitions:
                    from_s = t["from_status"] or "·"
                    to_s = t["to_status"]
                    agent = t["triggered_by"] or "?"
                    hist_parts.append(f"{from_s}→{to_s}({agent})")
                hist = "  ".join(hist_parts)
                lines.append(f"  {cont}   {t_cont}   {_DIM}History: {hist}{_RESET}")

        if not is_last_req:
            lines.append(f"  {cont}")

    return lines


def render_lineage_screen(lineage: dict, width: int, height: int) -> str:
    """Compose the lineage view screen.

    Called when user drills into a backlog item from the dashboard.
    """
    lines = _render_lineage(lineage, width, height)
    lines.append("")
    lines.append(f"  {_DIM}Press ESC or 'q' to return │ L to go back to browser{_RESET}")
    return "\n".join(lines)


# Valid sort modes for the browser and their display labels
BROWSER_SORT_MODES = ("id", "type", "priority")
_SORT_LABELS = {"id": "ID ▼", "type": "TYPE ▼", "priority": "PRI ▼"}


def sort_backlog(items: list, sort_by: str) -> list:
    """Sort backlog items by the given field.

    Returns a new sorted list. Does not mutate the input.
    """
    if sort_by == "id":
        return sorted(items, key=lambda r: r["id"], reverse=True)
    elif sort_by == "type":
        return sorted(items, key=lambda r: (r["type"], -r["id"]))
    elif sort_by == "priority":
        pri_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unset": 4}
        return sorted(items, key=lambda r: (pri_order.get(r["priority"], 5), -r["id"]))
    return list(items)


def render_browser_screen(
    all_backlog: list,
    width: int,
    height: int,
    page: int = 0,
    sort_by: str = "id",
) -> tuple[str, ClickMap]:
    """Render the backlog browser — paginated list of ALL backlog items for lineage selection.

    Shows all backlog items (including closed) with key hints 1-9 per page.
    Supports pagination with n/p keys for next/prev page.
    Press 's' to cycle sort: id → type → priority → id → ...
    Returns (screen_string, click_map).
    """
    lines: list[str] = []
    click_map: ClickMap = {}
    lines.append(f"{_BOLD}{_CYAN}  ⚡ BACKLOG LINEAGE BROWSER{_RESET}  {_DIM}sorted by: {sort_by}{_RESET}")
    lines.append("")

    if not all_backlog:
        lines.append(f"  {_DIM}(no backlog items found){_RESET}")
        lines.append("")
        lines.append(f"  {_DIM}Press ESC or 'q' to return to dashboard{_RESET}")
        return "\n".join(lines), click_map

    page_size = 9  # keys 1-9
    total_pages = (len(all_backlog) + page_size - 1) // page_size
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    page_items = all_backlog[start:start + page_size]

    # Header row — highlight the active sort column
    id_hdr = _SORT_LABELS["id"] if sort_by == "id" else "ID"
    type_hdr = _SORT_LABELS["type"] if sort_by == "type" else "TYPE"
    pri_hdr = _SORT_LABELS["priority"] if sort_by == "priority" else "PRI"
    lines.append(
        f"  {_BOLD}{'#':>2}  {id_hdr:>4}  {type_hdr:<8}  {pri_hdr:<8}  {'STATUS':<10}  {'TITLE':<50}{_RESET}"
    )
    lines.append("  " + "─" * (width - 4))

    # Data rows start after: header line, blank, column header, separator = line index 4
    data_start_line = len(lines)
    for idx, row in enumerate(page_items):
        pri_color = _PRIORITY_COLORS.get(row["priority"], _DIM)
        status = row["status"]
        s_color = _GREEN if status == "closed" else _YELLOW if status == "promoted" else _WHITE
        title = _truncate(row["title_short"], 50)
        key_col = _visible_pad(f"{_CYAN}{idx + 1}{_RESET}", 2)
        pri_col = _visible_pad(f"{pri_color}{row['priority']}{_RESET}", 8)
        status_col = _visible_pad(f"{s_color}{status}{_RESET}", 10)
        lines.append(
            f"  {key_col}  "
            f"{row['id']:>4}  "
            f"{_truncate(row['type'], 8):<8}  "
            f"{pri_col}  "
            f"{status_col}  "
            f"{title}"
        )
        # Click map: terminal rows are 1-indexed
        click_map[data_start_line + idx + 1] = ("lineage", row["id"])

    lines.append("")
    page_info = f"Page {page + 1}/{total_pages}  ({len(all_backlog)} items)"
    nav_keys = []
    if page > 0:
        nav_keys.append("p: prev")
    if page < total_pages - 1:
        nav_keys.append("n: next")
    nav_keys.append("s: sort")
    nav_keys.append("click or 1-9: lineage")
    nav_keys.append("ESC/q: back")
    lines.append(f"  {_DIM}{page_info}  │  {' │ '.join(nav_keys)}{_RESET}")

    return "\n".join(lines), click_map


def clear_and_print(screen: str) -> None:
    """Clear terminal and print screen string atomically.

    Uses ANSI clear+home then a single print to minimize flicker.
    """
    print("\033[2J\033[H" + screen, end="", flush=True)
