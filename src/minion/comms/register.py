"""Agent registration — register, deregister, rename, set_status, set_context, who.

Manages agent lifecycle in both the local project DB and the global coordinator DB.
Handles onboarding, crew context merging, roster file management, and HP tracking.
"""

from __future__ import annotations

import datetime
import os

from minion.auth import CLASS_MODEL_WHITELIST, VALID_CLASSES, get_tools_for_class
from minion.db import (
    DOCS_DIR,
    enrich_agent_row,
    format_trigger_codebook,
    get_coordinator_db,
    get_db,
    hp_summary,
    init_coordinator_db,
    load_onboarding,
    now_iso,
    touch_coordinator_activity,
)
from minion.fs import atomic_write_file


def register(
    agent_name: str,
    agent_class: str,
    model: str = "",
    description: str = "",
    transport: str = "terminal",
    crew: str = "",
    scope: str = "project",
) -> dict[str, object]:
    # Precondition assertions — backlog #63
    assert agent_name, "agent_name must not be empty"
    assert agent_class, "agent_class must not be empty"
    assert len(agent_name) <= 64, f"agent_name too long ({len(agent_name)} chars, max 64)"
    assert " " not in agent_name, f"agent_name must not contain spaces: '{agent_name}'"

    if transport not in ("terminal", "daemon", "daemon-ts"):
        return {"error": f"Invalid transport '{transport}'. Must be 'terminal', 'daemon', or 'daemon-ts'."}
    if agent_class not in VALID_CLASSES:
        return {"error": f"Unknown class '{agent_class}'. Valid: {', '.join(sorted(VALID_CLASSES))}"}

    allowed_models = CLASS_MODEL_WHITELIST.get(agent_class, set())
    if allowed_models and model and model not in allowed_models:
        return {"error": f"Model '{model}' not allowed for class '{agent_class}'. Allowed: {', '.join(sorted(allowed_models))}"}

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute(
            """INSERT INTO agents
                (name, agent_class, model, registered_at, last_seen, description, status, transport, scope_mode)
            VALUES (?, ?, ?, ?, ?, ?, 'waiting for work', ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                last_seen        = excluded.last_seen,
                agent_class      = excluded.agent_class,
                model            = COALESCE(NULLIF(excluded.model, ''), agents.model),
                description      = COALESCE(NULLIF(excluded.description, ''), agents.description),
                transport        = excluded.transport,
                scope_mode       = excluded.scope_mode,
                status           = 'waiting for work',
                hp_alerts_fired  = NULL
            """,
            (agent_name, agent_class, model or None, now, now, description or None, transport, scope),
        )

        # Auto-mark old broadcasts as read
        cutoff = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
        cursor.execute(
            """INSERT OR IGNORE INTO broadcast_reads (agent_name, message_id)
               SELECT ?, id FROM messages WHERE to_agent = 'all' AND timestamp < ?""",
            (agent_name, cutoff),
        )

        # Clear retire flag for re-spawned agents
        cursor.execute("DELETE FROM agent_retire WHERE agent_name = ?", (agent_name,))
        conn.commit()

        # Register in global coordinator DB for cross-repo routing
        try:
            init_coordinator_db()
            coord = get_coordinator_db()
            try:
                project_path = os.getcwd()
                # Check if name is already taken by a different active project
                existing = coord.execute(
                    "SELECT project_path FROM agents WHERE name = ?", (agent_name,)
                ).fetchone()
                if existing and os.path.realpath(existing["project_path"]) != os.path.realpath(project_path):
                    old_db = os.path.join(existing["project_path"], ".work", "minion.db")
                    if os.path.exists(old_db):
                        return {
                            "error": (
                                f"Agent name '{agent_name}' already registered in project "
                                f"{existing['project_path']}. Use a unique name."
                            )
                        }
                coord.execute(
                    """INSERT INTO agents
                        (name, agent_class, model, project_path, registered_at, last_seen, last_active, description, status, transport, scope_mode)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'waiting for work', ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        last_seen     = excluded.last_seen,
                        last_active   = excluded.last_active,
                        agent_class   = excluded.agent_class,
                        model         = COALESCE(NULLIF(excluded.model, ''), agents.model),
                        project_path  = excluded.project_path,
                        description   = COALESCE(NULLIF(excluded.description, ''), agents.description),
                        transport     = excluded.transport,
                        scope_mode    = excluded.scope_mode,
                        status        = 'waiting for work'
                    """,
                    (agent_name, agent_class, model or None, project_path, now, now, now, description or None, transport, scope),
                )
                coord.commit()
            finally:
                coord.close()
        except Exception as exc:
            import sys
            print(f"WARNING: coordinator DB registration failed: {exc}", file=sys.stderr)

        # Tier 3: Register on API GLOBAL network server (if configured)
        try:
            from minion.network.client import get_client
            net = get_client()
            if net.configured:
                net.register(agent_name, agent_class)
        except Exception:
            pass  # network tier is optional

        result: dict[str, object] = {
            "status": "registered",
            "agent": agent_name,
            "class": agent_class,
        }
        if model:
            result["model"] = model
        if description:
            result["description"] = description

        onboarding = load_onboarding(agent_class)
        if onboarding:
            result["onboarding"] = onboarding

        result["triggers"] = format_trigger_codebook()
        result["tools"] = get_tools_for_class(agent_class)

        # Merge crew YAML context when --crew is provided
        zone = ""
        capabilities: list[str] = []
        if crew:
            from minion.crew.spawn import _find_crew_file
            from minion.crew.config import load_config as _load_crew_config

            crew_file = _find_crew_file(crew)
            if not crew_file:
                result["crew_warning"] = f"Crew '{crew}' not found — skipping crew context"
            else:
                try:
                    crew_cfg = _load_crew_config(crew_file)
                    agent_cfg = crew_cfg.agents.get(agent_name)
                    if not agent_cfg:
                        result["crew_error"] = (
                            f"Agent '{agent_name}' not found in crew '{crew}'. "
                            f"Available: {', '.join(sorted(crew_cfg.agents.keys()))}"
                        )
                    else:
                        result["crew"] = crew
                        if agent_cfg.zone:
                            zone = agent_cfg.zone
                            result["zone"] = zone
                        if agent_cfg.capabilities:
                            capabilities = list(agent_cfg.capabilities)
                            result["capabilities"] = capabilities
                        if agent_cfg.system:
                            result["system_prompt_excerpt"] = agent_cfg.system[:200]
                except Exception as exc:
                    result["crew_error"] = f"Failed to load crew '{crew}': {exc}"

        # Write agent roster file for hook discovery
        from minion.db import get_runtime_dir
        agents_dir = os.path.join(get_runtime_dir(), ".minion-agents")
        os.makedirs(agents_dir, exist_ok=True)
        profile_lines = [
            f"agent_class: {agent_class}",
            f"model: {model or 'default'}",
            f"transport: {transport}",
            f"registered_at: {now}",
        ]
        if zone:
            profile_lines.append(f"zone: {zone}")
        if capabilities:
            profile_lines.append(f"capabilities: {','.join(capabilities)}")
        atomic_write_file(os.path.join(agents_dir, agent_name), "\n".join(profile_lines) + "\n")

        result["critical"] = (
            "YOU MUST START POLLING IMMEDIATELY. "
            "Without polling, you CANNOT receive messages or task assignments. "
            "No poll = no comms. Run: minion poll --agent " + agent_name
        )

        # Suggest intel docs relevant to agent's class and zone
        try:
            from minion.intel import find_docs as _find_docs
            class_docs = _find_docs(tag=agent_class)
            doc_paths = [d["doc_path"] for d in class_docs.get("docs", [])]
            if zone:
                zone_docs = _find_docs(tag=zone.lower().split()[0] if zone else "")
                doc_paths.extend(d["doc_path"] for d in zone_docs.get("docs", []))
            if doc_paths:
                result["suggested_reading"] = list(dict.fromkeys(doc_paths))  # dedupe
        except Exception:
            pass

        if transport == "terminal":
            result["playbook"] = {
                "type": "terminal",
                "steps": [
                    "CRITICAL — START POLLING NOW: Run `minion poll --agent " + agent_name + "` in the FOREGROUND. "
                    "Without poll running, you are DEAF — you cannot receive messages or tasks. "
                    "The poll blocks until a message or task arrives — that is intentional. "
                    "Tuck to terminal background if needed — do NOT launch as a background task. "
                    "Do NOT add --timeout. "
                    "When poll returns content, process it and restart poll in the foreground again. "
                    "If the output says Do NOT restart (stand_down/retire), stop. "
                    "NEVER restart in a tight loop — if poll exits immediately, something is wrong. Investigate, do not retry.",
                    "Read your protocol doc: " + os.path.join(DOCS_DIR, "protocol-" + agent_class + ".md"),
                    "Set your context with HP: minion set-context --agent " + agent_name + " --context 'loaded, waiting for orders' --hp 95",
                    "On compaction: call minion cold-start --agent " + agent_name + " to recover state",
                ],
            }
        else:
            result["playbook"] = {
                "type": "daemon",
                "steps": [
                    "The watcher manages your context — it re-injects tools and state after compaction",
                    "Just check inbox and work: minion check-inbox --agent " + agent_name,
                ],
            }
        return result
    finally:
        conn.close()


def deregister(agent_name: str) -> dict[str, object]:
    # Precondition — backlog #63
    assert agent_name, "agent_name must not be empty"
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return {"error": f"Agent '{agent_name}' not found."}

        # Release file claims
        cursor.execute("SELECT file_path FROM file_claims WHERE agent_name = ?", (agent_name,))
        claimed_files = [row["file_path"] for row in cursor.fetchall()]
        waitlist_notes: list[str] = []
        for fp in claimed_files:
            cursor.execute("DELETE FROM file_claims WHERE file_path = ?", (fp,))
            cursor.execute(
                "SELECT agent_name FROM file_waitlist WHERE file_path = ? ORDER BY added_at ASC LIMIT 1",
                (fp,),
            )
            waiter = cursor.fetchone()
            if waiter:
                waitlist_notes.append(f"{fp} -> {waiter['agent_name']} waiting")
        cursor.execute("DELETE FROM file_waitlist WHERE agent_name = ?", (agent_name,))
        cursor.execute("DELETE FROM agents WHERE name = ?", (agent_name,))
        conn.commit()

        # Remove from global coordinator DB
        try:
            coord = get_coordinator_db()
            try:
                coord.execute("DELETE FROM agents WHERE name = ?", (agent_name,))
                coord.commit()
            finally:
                coord.close()
        except Exception:
            pass  # coordinator DB may not exist yet

        # Remove agent roster file
        from minion.db import get_runtime_dir
        roster_file = os.path.join(get_runtime_dir(), ".minion-agents", agent_name)
        if os.path.exists(roster_file):
            os.remove(roster_file)

        result: dict[str, object] = {
            "status": "deregistered",
            "agent": agent_name,
            "released_claims": len(claimed_files),
        }
        if waitlist_notes:
            result["waitlist_notify"] = waitlist_notes
        return result
    finally:
        conn.close()


def rename(old_name: str, new_name: str) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM agents WHERE name = ?", (old_name,))
        if not cursor.fetchone():
            return {"error": f"Agent '{old_name}' not found."}
        cursor.execute("SELECT name FROM agents WHERE name = ?", (new_name,))
        if cursor.fetchone():
            return {"error": f"Agent '{new_name}' already exists."}

        cursor.execute("UPDATE agents SET name = ? WHERE name = ?", (new_name, old_name))
        cursor.execute("UPDATE messages SET from_agent = ? WHERE from_agent = ?", (new_name, old_name))
        cursor.execute("UPDATE messages SET to_agent = ? WHERE to_agent = ?", (new_name, old_name))
        cursor.execute("UPDATE messages SET cc_original_to = ? WHERE cc_original_to = ?", (new_name, old_name))
        cursor.execute("UPDATE broadcast_reads SET agent_name = ? WHERE agent_name = ?", (new_name, old_name))
        conn.commit()
        return {"status": "renamed", "old": old_name, "new": new_name}
    finally:
        conn.close()


def set_status(agent_name: str, status: str) -> dict[str, object]:
    conn = get_db()
    now = now_iso()
    try:
        # Validate agent status transition — backlog #83
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if row:
            from minion.state_machines import AGENT_STATUS_TRANSITIONS, validate_transition, InvalidTransition
            try:
                validate_transition(AGENT_STATUS_TRANSITIONS, "agent_status", row["status"], status)
            except InvalidTransition as exc:
                return {"error": str(exc)}

        conn.execute(
            "UPDATE agents SET status = ?, last_seen = ? WHERE name = ?",
            (status, now, agent_name),
        )
        conn.commit()
        return {"status": "ok", "agent": agent_name, "new_status": status}
    finally:
        conn.close()


def set_context(
    agent_name: str,
    context: str,
    tokens_used: int = 0,
    tokens_limit: int = 0,
    hp: int | None = None,
    files_modified: str = "",
) -> dict[str, object]:
    conn = get_db()
    now = now_iso()
    try:
        if hp is not None:
            # Self-reported HP path: write sentinel values to DB
            # max(1, 100-hp) avoids hp_turn_input=0 which triggers "HP unknown" in hp_summary
            hp_turn_input = max(1, 100 - hp)
            conn.execute(
                """UPDATE agents
                   SET context_summary = ?,
                       context_updated_at = ?,
                       last_seen = ?,
                       hp_turn_input = ?,
                       hp_tokens_limit = ?,
                       hp_updated_at = ?
                   WHERE name = ?""",
                (context, now, now, hp_turn_input, 100, now, agent_name),
            )
        else:
            conn.execute(
                """UPDATE agents
                   SET context_summary = ?,
                       context_updated_at = ?,
                       last_seen = ?
                   WHERE name = ?""",
                (context, now, now, agent_name),
            )
        conn.commit()

        result: dict[str, object] = {"status": "ok", "agent": agent_name, "context": context}
        if hp is not None:
            result["hp"] = hp_summary(None, None, 100, turn_input=max(1, 100 - hp))
            # Fire threshold alerts using self-reported hp value
            from minion.monitoring import _fire_hp_alerts
            _fire_hp_alerts(agent_name, float(hp))
        elif tokens_used and tokens_limit:
            result["hp"] = hp_summary(tokens_used, None, tokens_limit)

        # Warn if agent reports modifying files they haven't claimed
        if files_modified:
            from minion.db import get_db as _get_db
            conn2 = _get_db()
            try:
                unclaimed = []
                for f in files_modified.split(","):
                    f = f.strip()
                    if not f:
                        continue
                    normalized = os.path.abspath(f)
                    row = conn2.execute(
                        "SELECT agent_name FROM file_claims WHERE file_path = ?", (normalized,)
                    ).fetchone()
                    if not row or row["agent_name"] != agent_name:
                        unclaimed.append(f)
                if unclaimed:
                    result["unclaimed_files"] = unclaimed
                    result["claim_warning"] = (
                        "Editing unclaimed files — "
                        + " ".join(f"minion claim-file --agent {agent_name} --file {f}" for f in unclaimed)
                    )
            finally:
                conn2.close()

        touch_coordinator_activity(agent_name)
        return result
    finally:
        conn.close()


def who() -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now()
    try:
        cursor.execute("SELECT * FROM agents ORDER BY last_seen DESC")
        agents = [enrich_agent_row(row, now) for row in cursor.fetchall()]
        return {"agents": agents}
    finally:
        conn.close()
