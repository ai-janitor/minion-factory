"""Promote a backlog item into the requirement pipeline.

Copies the backlog README.md into .work/requirements/{target}/, registers the
requirement in the DB, and updates the backlog row to status=promoted.
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from minion.db import _get_db_path, get_db, now_iso
from minion.requirements.crud import register

from ._helpers import _get_backlog_path

# Backlog types that map to the 'bug' requirement origin; everything else → 'feature'
_BUG_TYPES = {"bug"}


def promote(
    file_path: str,
    origin: str | None = None,
    db: str | None = None,
    slug: str | None = None,
    flow: str = "requirement",
) -> dict[str, Any]:
    """Promote an open backlog item to a requirement.

    file_path is relative to .work/backlog/ (e.g. 'bugs/preview-final-word-loss').
    flow selects the requirement lifecycle DAG — 'requirement' (default, 9 stages)
    or 'requirement-lite' (4 stages: seed → decomposing → tasked → completed).

    Steps:
    1. Verify backlog item exists and status=open.
    2. Infer origin (bug|feature) from backlog type if not provided.
    3. Determine requirement target path: {origin}s/{slug} under .work/requirements/.
    4. Create the requirement folder.
    5. Copy the backlog README.md into the requirement folder.
    6. Register the requirement in the DB with the selected flow_type.
    7. Update backlog row: status=promoted, promoted_to=requirement_path, updated_at.
    8. Append to the backlog README.md Outcome section.
    9. Return summary dict.
    """
    file_path = file_path.strip("/")

    # --- Resolve paths ---
    db_path = db or _get_db_path()
    work_dir = os.path.dirname(db_path)
    backlog_root = _get_backlog_path(db)
    req_root = os.path.join(work_dir, "requirements")

    backlog_item_dir = os.path.join(backlog_root, file_path)
    backlog_readme = os.path.join(backlog_item_dir, "README.md")

    # --- Verify backlog item exists and is open ---
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, type, title, status, promoted_to FROM backlog WHERE file_path = ?",
            (file_path,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Backlog item '{file_path}' not found.")

        status = row["status"]
        if status == "promoted":
            raise ValueError(
                f"Backlog item '{file_path}' is already promoted to '{row['promoted_to']}'."
            )
        if status in ("killed", "deferred"):
            raise ValueError(
                f"Backlog item '{file_path}' has status '{status}' and cannot be promoted."
            )
        if status != "open":
            raise ValueError(
                f"Backlog item '{file_path}' has unexpected status '{status}'. Expected 'open'."
            )

        backlog_type = row["type"] or ""
        backlog_id = row["id"]

        # --- Infer origin ---
        if origin is None:
            origin = "bug" if backlog_type in _BUG_TYPES else "feature"

        # --- Determine requirement target path ---
        # Use explicit slug override, otherwise derive from file_path
        slug = slug or file_path.split("/")[-1]
        req_folder_name = f"{origin}s"  # bugs/ or features/
        req_rel_path = f"{req_folder_name}/{slug}"

        req_abs_path = os.path.join(req_root, req_folder_name, slug)

        # --- Guard: requirement folder must not already exist ---
        if os.path.exists(req_abs_path):
            raise ValueError(
                f"Requirement folder already exists at '{req_abs_path}'. Cannot overwrite."
            )

        # --- Create the requirement folder and copy README ---
        os.makedirs(req_abs_path, exist_ok=False)
        if os.path.exists(backlog_readme):
            shutil.copy2(backlog_readme, os.path.join(req_abs_path, "README.md"))

        # --- Register requirement in DB ---
        reg_result = register(file_path=req_rel_path, created_by="backlog-promote", flow_type=flow)
        if "error" in reg_result:
            # Rollback: remove the folder we just created
            shutil.rmtree(req_abs_path, ignore_errors=True)
            raise RuntimeError(f"Failed to register requirement: {reg_result['error']}")

        # --- Update backlog row ---
        now = now_iso()
        cursor.execute(
            "UPDATE backlog SET status = 'promoted', promoted_to = ?, updated_at = ? WHERE id = ?",
            (req_rel_path, now, backlog_id),
        )
        conn.commit()

        # --- Append to backlog README Outcome section ---
        date_str = now[:10]  # YYYY-MM-DD
        outcome_line = f"Promoted to requirement: {req_rel_path} on {date_str}\n"
        if os.path.exists(backlog_readme):
            with open(backlog_readme, "a") as f:
                f.write(f"\n{outcome_line}")

        return {
            "status": "promoted",
            "backlog": {
                "id": backlog_id,
                "file_path": file_path,
                "type": backlog_type,
                "title": row["title"],
                "promoted_to": req_rel_path,
            },
            "requirement": reg_result,
        }
    finally:
        conn.close()
