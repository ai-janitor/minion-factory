"""Agent context endpoint — update agent context and HP via network API.

Purpose: Expose agent context/HP updates as a network API endpoint so remote
         agents can set-context without CLI access to the local project DB.
Rationale: CLI parity — set-context is the primary heartbeat mechanism for
           agents. Without a network endpoint, remote agents cannot report
           health status or update their context summary.
Responsibility: POST /agents/{name}/context — delegates to the same DB logic
                as `minion set-context`.
Organization: Single handler that parses JSON body, resolves project DB,
              updates agent context and HP metrics.

Pseudo-logic:
  1. Parse JSON body from request
  2. Extract agent name from URL param
  3. Extract context, tokens_used, tokens_limit, hp from body
  4. Resolve project DB from project_path in body
  5. Update agent row: context, hp_turn_input, hp_tokens_limit, last_seen
  6. Return JSON: {"status": "ok", "agent": name, "hp": "..."} or {"error": "..."}
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime

from minion.defaults import ENV_PROJECT_DIR


def register(router) -> None:
    """Register agent context endpoints with the router dispatch table."""
    router.add_post("/agents/{name}/context", handle_set_context)


def handle_set_context(handler, db_path: str, name: str = "", **kwargs) -> None:
    """POST /agents/{name}/context — update agent context summary and HP metrics.

    URL param: {name} — agent name
    Body: {
        "project_path": "/path/to/project",  (required)
        "context": "what I'm doing now",      (required)
        "tokens_used": 50000,                 (optional)
        "tokens_limit": 200000,               (optional)
        "hp": 85,                             (optional, 0-100)
        "files_modified": "file1.py,file2.py" (optional)
    }

    Pseudo-logic:
      1. Validate agent name from URL
      2. Parse JSON body
      3. Validate project_path and context present
      4. Set MINION_PROJECT_DIR to resolve project DB
      5. Update agent row with context, HP metrics, last_seen
      6. If hp provided, compute HP string like "85% HP [50k/200k]"
      7. Return updated status
    """
    if not name:
        handler._json_response(400, {"error": "Agent name required in URL: /agents/{name}/context"})
        return

    body = handler._parse_json_body()
    if not body:
        return

    project_path = body.get("project_path", "").strip() if isinstance(body.get("project_path"), str) else ""
    context = body.get("context", "").strip() if isinstance(body.get("context"), str) else ""

    if not project_path:
        handler._json_response(400, {"error": "project_path is required"})
        return
    if not context:
        handler._json_response(400, {"error": "context is required"})
        return

    tokens_used = body.get("tokens_used", 0)
    tokens_limit = body.get("tokens_limit", 0)
    hp = body.get("hp")
    files_modified = body.get("files_modified", "")

    # PSEUDO: set MINION_PROJECT_DIR, call the DB update, restore
    old_proj = os.environ.get(ENV_PROJECT_DIR)
    os.environ[ENV_PROJECT_DIR] = project_path
    try:
        from minion.db import get_db, now_iso

        conn = get_db()
        cursor = conn.cursor()
        now = now_iso()

        # PSEUDO: verify agent exists
        cursor.execute("SELECT name FROM agents WHERE name = ?", (name,))
        if not cursor.fetchone():
            handler._json_response(404, {"error": f"Agent '{name}' not registered"})
            return

        # PSEUDO: build update query based on what fields are provided
        updates = ["context = ?", "last_seen = ?"]
        params: list = [context, now]

        if isinstance(tokens_used, (int, float)) and tokens_used > 0:
            updates.append("hp_turn_input = ?")
            params.append(int(tokens_used))
        if isinstance(tokens_limit, (int, float)) and tokens_limit > 0:
            updates.append("hp_tokens_limit = ?")
            params.append(int(tokens_limit))
        if isinstance(files_modified, str) and files_modified:
            updates.append("files_modified = ?")
            params.append(files_modified)

        params.append(name)
        cursor.execute(
            f"UPDATE agents SET {', '.join(updates)} WHERE name = ?",
            params,
        )
        conn.commit()

        # PSEUDO: compute HP display string
        hp_str = ""
        if hp is not None and isinstance(hp, (int, float)):
            tu = tokens_used if isinstance(tokens_used, (int, float)) else 0
            tl = tokens_limit if isinstance(tokens_limit, (int, float)) else 0
            tu_k = f"{tu // 1000}k" if tu >= 1000 else str(tu)
            tl_k = f"{tl // 1000}k" if tl >= 1000 else str(tl)
            hp_str = f"{int(hp)}% HP [{tu_k}/{tl_k}]"

        handler._json_response(200, {
            "status": "ok",
            "agent": name,
            "context": context,
            "hp": hp_str or "updated",
        })
    except Exception as e:  # broad catch: top-level handler returns 500 on any failure
        handler._json_response(500, {"error": str(e), "traceback": traceback.format_exc()})
    finally:
        if old_proj is None:
            os.environ.pop(ENV_PROJECT_DIR, None)
        else:
            os.environ[ENV_PROJECT_DIR] = old_proj
