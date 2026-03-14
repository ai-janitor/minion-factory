"""Stream.jsonl tail-and-parse utility for the web dashboard.

Purpose: Read and parse agent stream.jsonl files to extract recent tool_use events.
Rationale: The daemon runner writes raw stream-json to .minion-swarm/logs/<agent>.stream.jsonl.
    The web dashboard needs to surface this tool-call activity without re-implementing
    the daemon's stream parsing. This module provides a reusable function that tails
    the last N lines, extracts tool_use events, and returns a dict[str, list[dict]]
    mapping agent names to their recent tool calls.
Responsibility: JSONL tailing, tool_use extraction, error-tolerant parsing.
    NOT responsible for: WebSocket broadcast (web_server.py), stream writing (daemon runner),
    HTML rendering (static/index.html).
Organization: Two public functions — `tail_agent_activity()` for daemon stream.jsonl
    and `tail_cli_activity()` for CLI invocation JSONL — plus internal helpers.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --- Constants ---
# Default number of bytes to read from the tail of each stream file.
# 64KB covers ~200-400 JSONL lines depending on event verbosity.
_DEFAULT_TAIL_BYTES = 64 * 1024

# Maximum tool_use events to return per agent (keeps payload small).
_DEFAULT_MAX_EVENTS = 5


def tail_agent_activity(
    logs_dir: str | Path,
    agent_names: list[str],
    *,
    max_events: int = _DEFAULT_MAX_EVENTS,
    tail_bytes: int = _DEFAULT_TAIL_BYTES,
) -> dict[str, list[dict[str, Any]]]:
    """Tail stream.jsonl files and extract recent tool_use events per agent.

    Pseudo-logic:
    1. For each agent name, resolve the stream.jsonl path in logs_dir
    2. If file missing, return empty list for that agent
    3. Read the last `tail_bytes` bytes from the file (seek from end)
    4. Split into lines, discard the first (likely partial) line
    5. Parse each line as JSON — skip malformed lines
    6. Extract tool_use events from assistant messages
    7. Return last `max_events` per agent, newest first

    Args:
        logs_dir: Path to the .minion-swarm/logs/ directory
        agent_names: List of agent names to look up
        max_events: Max tool_use events per agent (default 5)
        tail_bytes: How many bytes to read from tail of file (default 64KB)

    Returns:
        dict mapping agent name -> list of tool call dicts, each with:
            {"tool": str, "input_summary": str, "timestamp": str}
    """
    logs_path = Path(logs_dir)
    result: dict[str, list[dict[str, Any]]] = {}

    for name in agent_names:
        # Resolve stream file — check primary, then rotated backup
        stream_file = logs_path / f"{name}.stream.jsonl"

        events = _extract_tool_events(stream_file, tail_bytes)

        # If primary file has few events, also check rotated file
        if len(events) < max_events:
            rotated = logs_path / f"{name}.stream.jsonl.1"
            if rotated.exists():
                rotated_events = _extract_tool_events(rotated, tail_bytes)
                events = rotated_events + events

        # Keep only the last max_events, newest first
        result[name] = events[-max_events:][::-1]

    return result


def _extract_tool_events(
    stream_file: Path, tail_bytes: int
) -> list[dict[str, Any]]:
    """Extract tool_use events from a single stream.jsonl file.

    Pseudo-logic:
    1. If file doesn't exist or is empty, return []
    2. Seek to max(0, file_size - tail_bytes)
    3. Read to end, split by newline
    4. If we seeked past 0, discard first line (likely partial)
    5. Parse each line as JSON
    6. For assistant messages with content blocks, extract tool_use blocks
    7. Build event dict with tool name, truncated input, timestamp

    Returns:
        List of tool event dicts in chronological order (oldest first).
    """
    if not stream_file.exists():
        return []

    try:
        file_size = stream_file.stat().st_size
        if file_size == 0:
            return []

        with open(stream_file, "r", encoding="utf-8", errors="replace") as f:
            # Seek to near the end for efficiency
            seek_pos = max(0, file_size - tail_bytes)
            if seek_pos > 0:
                f.seek(seek_pos)
            lines = f.readlines()

        # If we seeked past the start, first line is likely partial — discard it
        if seek_pos > 0 and lines:
            lines = lines[1:]

        events: list[dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(payload, dict):
                continue

            # Extract tool_use from assistant messages
            # Format: {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": ..., "input": ...}]}}
            tool_events = _extract_tools_from_payload(payload)
            events.extend(tool_events)

    except OSError as e:
        logger.debug("Failed to read stream file %s: %s", stream_file, e)
        return []

    return events


def _extract_tools_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract tool_use events from a single JSONL payload.

    Pseudo-logic:
    1. Check if payload is an assistant message with content blocks
    2. Iterate content blocks looking for type == "tool_use"
    3. For each tool_use block, extract name and truncated input
    4. Return list of extracted tool event dicts

    Returns:
        List of {"tool": str, "input_summary": str, "timestamp": str} dicts.
    """
    events: list[dict[str, Any]] = []

    # Pattern 1: assistant message with content blocks
    if payload.get("type") == "assistant":
        message = payload.get("message", {})
        if isinstance(message, dict):
            content_blocks = message.get("content", [])
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        events.append(_make_tool_event(block))

    # Pattern 2: content_block_start with tool_use
    if payload.get("type") == "content_block_start":
        block = payload.get("content_block", {})
        if isinstance(block, dict) and block.get("type") == "tool_use":
            events.append(_make_tool_event(block))

    return events


def _make_tool_event(block: dict[str, Any]) -> dict[str, Any]:
    """Create a normalized tool event dict from a tool_use content block.

    Pseudo-logic:
    1. Extract tool name from block
    2. Extract input and truncate to a short summary
    3. Return normalized dict

    Returns:
        {"tool": str, "input_summary": str}
    """
    tool_name = block.get("name", "unknown")
    raw_input = block.get("input", {})

    # Build a short summary of the input
    input_summary = _summarize_input(raw_input)

    return {
        "tool": tool_name,
        "input_summary": input_summary,
    }


def _summarize_input(raw_input: Any, max_len: int = 120) -> str:
    """Create a short human-readable summary of tool input.

    Pseudo-logic:
    1. If input is a string, truncate directly
    2. If input is a dict, try to extract meaningful fields:
       - For Bash: show the command
       - For Read/Edit/Write: show the file_path
       - For Grep: show the pattern
       - Fallback: JSON-serialize and truncate
    3. Truncate to max_len with ellipsis

    Returns:
        Truncated string summary.
    """
    if isinstance(raw_input, str):
        return _truncate(raw_input, max_len)

    if isinstance(raw_input, dict):
        # Try well-known tool input patterns
        for key in ("command", "file_path", "pattern", "query", "content", "url"):
            if key in raw_input and isinstance(raw_input[key], str):
                val = raw_input[key]
                prefix = f"{key}: " if key not in ("command",) else ""
                return _truncate(f"{prefix}{val}", max_len)

        # Fallback: serialize
        try:
            text = json.dumps(raw_input, ensure_ascii=False)
            return _truncate(text, max_len)
        except (TypeError, ValueError):
            return "<complex input>"

    if raw_input is None:
        return ""

    return _truncate(str(raw_input), max_len)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    # Replace newlines with spaces for single-line display
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


# ---------------------------------------------------------------------------
# CLI activity reader — parse .work/agent-activity/<agent>.jsonl
# Written by CLI close handler (cli/main.py _log_activity_on_close).
# Format: {"command": str, "args": list, "timestamp": str, "agent": str}
# Converts to same {"tool": str, "input_summary": str, "timestamp": str}
# format as daemon tool events for unified dashboard rendering.
# ---------------------------------------------------------------------------

def tail_cli_activity(
    activity_dir: str | Path,
    agent_names: list[str],
    *,
    max_events: int = _DEFAULT_MAX_EVENTS,
    tail_bytes: int = _DEFAULT_TAIL_BYTES,
) -> dict[str, list[dict[str, Any]]]:
    """Tail CLI activity JSONL files and return recent invocations per agent.

    Pseudo-logic:
    1. For each agent name, resolve <activity_dir>/<agent>.jsonl
    2. If file missing or empty, return empty list for that agent
    3. Read the last tail_bytes from the file (seek from end)
    4. Parse each line as JSON — skip malformed lines
    5. Convert CLI record format to dashboard event format
    6. Return last max_events per agent, newest first

    Args:
        activity_dir: Path to .work/agent-activity/ directory
        agent_names: List of agent names to look up
        max_events: Max events per agent (default 5)
        tail_bytes: How many bytes to read from tail (default 64KB)

    Returns:
        dict mapping agent name -> list of event dicts, each with:
            {"tool": str, "input_summary": str, "timestamp": str}
    """
    activity_path = Path(activity_dir)
    result: dict[str, list[dict[str, Any]]] = {}

    if not activity_path.is_dir():
        return result

    for name in agent_names:
        jsonl_file = activity_path / f"{name}.jsonl"
        events = _extract_cli_events(jsonl_file, tail_bytes)
        # Keep only the last max_events, newest first
        result[name] = events[-max_events:][::-1]

    return result


def _extract_cli_events(
    jsonl_file: Path, tail_bytes: int
) -> list[dict[str, Any]]:
    """Extract CLI invocation events from a single agent JSONL file.

    Pseudo-logic:
    1. If file doesn't exist or is empty, return []
    2. Seek to near the end for efficiency
    3. Parse each line as JSON
    4. Convert {"command", "args", "timestamp", "agent"} to
       {"tool": command, "input_summary": joined args, "timestamp": ts}
    5. Return events in chronological order (oldest first)

    Returns:
        List of event dicts in chronological order.
    """
    if not jsonl_file.exists():
        return []

    try:
        file_size = jsonl_file.stat().st_size
        if file_size == 0:
            return []

        with open(jsonl_file, "r", encoding="utf-8", errors="replace") as f:
            seek_pos = max(0, file_size - tail_bytes)
            if seek_pos > 0:
                f.seek(seek_pos)
            lines = f.readlines()

        # If we seeked past the start, first line is likely partial — discard
        if seek_pos > 0 and lines:
            lines = lines[1:]

        events: list[dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(record, dict):
                continue

            # Convert CLI record to dashboard event format
            command = record.get("command", "")
            args = record.get("args", [])
            timestamp = record.get("timestamp", "")

            # Build input_summary from args list
            if isinstance(args, list):
                input_summary = " ".join(str(a) for a in args)
            else:
                input_summary = str(args)

            events.append({
                "tool": f"minion {command}" if command else "minion",
                "input_summary": _truncate(input_summary, 120),
                "timestamp": timestamp,
            })

    except OSError as e:
        logger.debug("Failed to read CLI activity file %s: %s", jsonl_file, e)
        return []

    return events
