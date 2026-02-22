"""SQLite persistence for DAG-based project/task management with transition audit logging."""

from __future__ import annotations

import warnings
from pathlib import Path

from minion.db import get_db

from .dag import Transition
from .loader import load_flow


class TaskDB:
    def __init__(self, db_path: str | None = None, flows_dir: str | Path | None = None):
        # db_path ignored — factory uses unified DB via get_db()
        # Kept as parameter for API compatibility with minion-tasks consumers
        self._conn = get_db()
        self._flows_dir = Path(flows_dir) if flows_dir else None

    # --- helpers ---

    def _row_to_dict(self, row) -> dict | None:
        if row is None:
            return None
        return dict(row)

    def _load_flow(self, task_type: str):
        return load_flow(task_type, self._flows_dir)

    # --- Projects ---

    def create_project(self, id: str, description: str) -> dict:
        self._conn.execute(
            "INSERT INTO projects (id, description) VALUES (?, ?)",
            (id, description),
        )
        self._conn.commit()
        return self.get_project(id)

    def get_project(self, id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (id,)).fetchone()
        return self._row_to_dict(row)

    def list_projects(self, status: str | None = None) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM projects WHERE status = ?", (status,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM projects").fetchall()
        return [dict(r) for r in rows]

    # --- Tasks ---

    def create_task(
        self,
        id: str,
        project_id: str,
        task_type: str,
        description: str,
        file_path: str | None = None,
        class_required: str | None = None,
    ) -> dict:
        self._conn.execute(
            """INSERT INTO tasks (id, project_id, task_type, description, file_path, class_required)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (id, project_id, task_type, description, file_path, class_required),
        )
        self._conn.commit()
        return self.get_task(id)

    def get_task(self, id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
        return self._row_to_dict(row)

    def list_tasks(
        self,
        project_id: str | None = None,
        status: str | None = None,
        class_required: str | None = None,
        assigned_to: str | None = None,
    ) -> list[dict]:
        clauses, params = [], []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if class_required:
            clauses.append("class_required = ?")
            params.append(class_required)
        if assigned_to:
            clauses.append("assigned_to = ?")
            params.append(assigned_to)
        where = " AND ".join(clauses)
        sql = "SELECT * FROM tasks"
        if where:
            sql += f" WHERE {where}"
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    # --- Transitions ---

    def transition_task(self, task_id: str, to_status: str, agent: str | None = None) -> dict:
        """Move task to a new status. Validates against DAG, logs with valid flag."""
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")

        from_status = task["status"]
        flow = self._load_flow(task["task_type"])
        valid_targets = flow.valid_transitions(from_status)
        is_valid = to_status in valid_targets

        if not is_valid:
            warnings.warn(
                f"Transition {from_status} → {to_status} not valid for flow '{task['task_type']}'. "
                f"Valid: {valid_targets}. Logging with valid=0.",
                stacklevel=2,
            )

        self._conn.execute(
            "UPDATE tasks SET status = ?, assigned_to = COALESCE(?, assigned_to), "
            "updated_at = datetime('now') WHERE id = ?",
            (to_status, agent, task_id),
        )
        self._conn.execute(
            "INSERT INTO transition_log (entity_id, entity_type, from_status, to_status, triggered_by, created_at) "
            "VALUES (?, 'task', ?, ?, ?, datetime('now'))",
            (task_id, from_status, to_status, agent),
        )
        self._conn.commit()
        return self.get_task(task_id)

    def complete(self, task_id: str, agent: str, passed: bool = True) -> Transition | None:
        """Assignee says 'done' — DAG routes to next stage, DB updated."""
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")

        flow = self._load_flow(task["task_type"])
        result = flow.transition(task["status"], task["class_required"] or "", passed)
        if result is None:
            return None

        self._conn.execute(
            "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (result.to_status, task_id),
        )
        self._conn.execute(
            "INSERT INTO transition_log (entity_id, entity_type, from_status, to_status, triggered_by, created_at) "
            "VALUES (?, 'task', ?, ?, ?, datetime('now'))",
            (task_id, task["status"], result.to_status, agent),
        )
        self._conn.commit()
        return result

    def get_transitions(self, task_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM transition_log WHERE entity_id = ? AND entity_type = 'task' ORDER BY created_at, id",
            (task_id,),
        ).fetchall()
        return [dict(r) for r in rows]
