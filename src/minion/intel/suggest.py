"""Suggest relevant intel docs for a topic or task — keyword search across tags, slug, and description.

Purpose: Suggest relevant intel docs for a topic or task — keyword search across tags, slug, and description.
Rationale: Extracted into own module for single-responsibility intel management.
Responsibility: Suggest relevant intel docs for a topic or task — keyword search across tags, slug, and description. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import json

from minion.db import get_db


def suggest(topic: str = "", task_id: int | None = None, limit: int = 5) -> dict[str, object]:
    """Return intel docs ranked by relevance to a topic string or task title.

    Searches tags, slug, and description fields via LIKE matching on each keyword.
    When task_id is provided, infers keywords from the task's title.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Infer keywords from task title if task_id provided
        if task_id and not topic:
            cursor.execute("SELECT title FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                topic = row["title"]
            else:
                return {"error": f"Task {task_id} not found."}

        if not topic:
            return {"error": "Provide --topic text or --task-id to infer keywords."}

        # Split topic into keywords, drop short noise words
        keywords = [w.lower() for w in topic.split() if len(w) > 2]
        if not keywords:
            return {"docs": []}

        # Score each doc by how many keywords match across slug + tags + description
        cursor.execute(
            "SELECT slug, doc_path, tags, description, created_by FROM intel_docs"
        )
        scored: list[tuple[int, dict[str, object]]] = []
        for row in cursor.fetchall():
            d = dict(row)
            tags_list = json.loads(d.get("tags") or "[]")
            searchable = " ".join([
                d.get("slug", ""),
                " ".join(tags_list),
                d.get("description", ""),
            ]).lower()
            score = sum(1 for kw in keywords if kw in searchable)
            if score > 0:
                d["tags"] = tags_list
                d["score"] = score
                scored.append((score, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        docs = [item[1] for item in scored[:limit]]
        return {"docs": docs, "query": topic, "keywords": keywords}
    finally:
        conn.close()
