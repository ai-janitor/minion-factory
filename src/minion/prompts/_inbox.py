"""Format inbox messages and tasks for inline prompt injection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from minion.daemon.contracts import load_contract


def format_inbox(docs_dir: Path, poll_data: Dict[str, Any], agent: str) -> str:
    """Format poll_data messages + tasks into an inline inbox block."""
    tmpl = load_contract(docs_dir, "inbox-template")
    inbox_lines: List[str] = []

    messages = poll_data.get("messages", [])
    if messages:
        inbox_lines.append(
            tmpl["inbox_header"] if tmpl else "=== INBOX (already consumed — do NOT run check-inbox) ==="
        )
        for msg in messages:
            sender = msg.get("from_agent", "unknown")
            content = msg.get("content", "")
            if tmpl:
                inbox_lines.append(
                    tmpl["message_format"]
                    .replace("{sender}", sender)
                    .replace("{content}", content)
                )
            else:
                inbox_lines.append(f"FROM {sender}: {content}")
        inbox_lines.append(tmpl["inbox_footer"] if tmpl else "=== END INBOX ===")

    tasks = poll_data.get("tasks", [])
    if tasks:
        inbox_lines.append(tmpl["task_header"] if tmpl else "=== AVAILABLE TASKS ===")
        for task in tasks:
            if tmpl:
                line = tmpl["task_format"]
                line = line.replace("{task_id}", str(task.get("task_id", "")))
                line = line.replace("{title}", task.get("title", ""))
                line = line.replace("{status}", task.get("status", ""))
                line = line.replace("{claim_cmd}", task.get("claim_cmd", ""))
                inbox_lines.append(line)
            else:
                inbox_lines.append(
                    f"  Task #{task.get('task_id')}: {task.get('title')} [{task.get('status')}]"
                )
                if task.get("claim_cmd"):
                    inbox_lines.append(f"    Claim: {task['claim_cmd']}")
        inbox_lines.append(tmpl["task_footer"] if tmpl else "=== END TASKS ===")

    if tmpl:
        inbox_lines.append("")
        for line in tmpl["post_instructions"]:
            inbox_lines.append(line.replace("{agent}", agent))
    else:
        inbox_lines.extend([
            "",
            "Process the above, then send results:",
            f"  minion send --from {agent} --to <recipient> --message '...'",
            "Do NOT run check-inbox or re-register.",
        ])

    return "\n".join(inbox_lines)
