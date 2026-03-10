"""Task workflow endpoints — complete-phase, result, review, test via network API.

Purpose: Expose task DAG workflow operations as network API endpoints so remote
         agents can advance tasks through the pipeline without CLI access.
Rationale: CLI parity — these are the core task lifecycle operations that agents
           use constantly. Without network endpoints, remote daemon agents
           cannot complete phases, submit results, or write reviews/tests.
Responsibility: POST /tasks/complete-phase, POST /tasks/result,
                POST /tasks/review, POST /tasks/test. Each delegates to the
                corresponding function in minion.tasks after resolving project DB.
Organization: Each handler parses JSON body, validates required fields, sets up
              project context, calls the core function, returns JSON result.

Pseudo-logic for each endpoint:
  1. Parse JSON body from request
  2. Extract agent_name, task_id, project_path (all required)
  3. Validate required fields
  4. Set MINION_PROJECT_DIR to project_path
  5. Call the core task function
  6. Restore MINION_PROJECT_DIR
  7. Return JSON result or error
"""

from __future__ import annotations

import os
import traceback


def register(router) -> None:
    """Register task workflow endpoints with the router dispatch table."""
    router.add_post("/tasks/complete-phase", handle_complete_phase)
    router.add_post("/tasks/result", handle_result)
    router.add_post("/tasks/review", handle_review)
    router.add_post("/tasks/test", handle_test)


def _setup_project(project_path: str):
    """Set MINION_PROJECT_DIR and return old value for restoration."""
    old = os.environ.get("MINION_PROJECT_DIR")
    os.environ["MINION_PROJECT_DIR"] = project_path
    return old


def _teardown_project(old_value):
    """Restore previous MINION_PROJECT_DIR."""
    if old_value is None:
        os.environ.pop("MINION_PROJECT_DIR", None)
    else:
        os.environ["MINION_PROJECT_DIR"] = old_value


def _validate_base_fields(body: dict) -> tuple[str, int, str, str | None]:
    """Extract and validate common fields from request body.

    Returns: (agent_name, task_id, project_path, error_message)
    error_message is None if validation passed.
    """
    agent_name = body.get("agent_name", "").strip() if isinstance(body.get("agent_name"), str) else ""
    project_path = body.get("project_path", "").strip() if isinstance(body.get("project_path"), str) else ""

    task_id_raw = body.get("task_id")
    if not isinstance(task_id_raw, int) or task_id_raw <= 0:
        return "", 0, "", "task_id must be a positive integer"
    if not agent_name:
        return "", 0, "", "agent_name is required"
    if not project_path:
        return "", 0, "", "project_path is required"

    return agent_name, task_id_raw, project_path, None


def handle_complete_phase(handler, db_path: str, **kwargs) -> None:
    """POST /tasks/complete-phase — complete current DAG phase for a task.

    Body: {
        "agent_name": "...",       (required)
        "task_id": 42,             (required)
        "project_path": "/...",    (required)
        "passed": true,            (optional, default true)
        "reason": "..."            (optional, failure reason)
    }

    Pseudo-logic:
      1. Parse and validate body
      2. Set project context
      3. Call tasks.update_task.complete_phase(agent_name, task_id, passed, reason)
      4. Return result
    """
    body = handler._parse_json_body()
    if not body:
        return

    agent_name, task_id, project_path, error = _validate_base_fields(body)
    if error:
        handler._json_response(400, {"error": error})
        return

    passed = body.get("passed", True)
    if not isinstance(passed, bool):
        passed = True
    reason = body.get("reason", "")
    if not isinstance(reason, str):
        reason = ""

    old = _setup_project(project_path)
    try:
        from minion.tasks.update_task import complete_phase
        result = complete_phase(agent_name, task_id, passed=passed, reason=reason or None)
        if "error" in result:
            handler._json_response(400, result)
        else:
            handler._json_response(200, {"status": "ok", **result})
    except Exception as e:
        handler._json_response(500, {"error": str(e), "traceback": traceback.format_exc()})
    finally:
        _teardown_project(old)


def handle_result(handler, db_path: str, **kwargs) -> None:
    """POST /tasks/result — write a result file and submit it for a task.

    Body: {
        "agent_name": "...",          (required)
        "task_id": 42,                (required)
        "project_path": "/...",       (required)
        "content": "result summary",  (required — summary text)
        "files_changed": "a.py,b.py", (optional)
        "notes": "extra notes"        (optional)
    }

    Pseudo-logic:
      1. Parse and validate body
      2. Validate content (summary) present
      3. Set project context
      4. Call tasks.result.create_result(agent_name, task_id, summary, files_changed, notes)
      5. Return result
    """
    body = handler._parse_json_body()
    if not body:
        return

    agent_name, task_id, project_path, error = _validate_base_fields(body)
    if error:
        handler._json_response(400, {"error": error})
        return

    content = body.get("content", "").strip() if isinstance(body.get("content"), str) else ""
    if not content:
        handler._json_response(400, {"error": "content is required"})
        return

    file_path = body.get("file_path", "")
    if not isinstance(file_path, str):
        file_path = ""

    files_changed = body.get("files_changed", "")
    if not isinstance(files_changed, str):
        files_changed = ""
    notes = body.get("notes", "")
    if not isinstance(notes, str):
        notes = ""

    old = _setup_project(project_path)
    try:
        from minion.tasks.result import create_result
        result = create_result(agent_name, task_id, content, files_changed, notes)
        if "error" in result:
            handler._json_response(400, result)
        else:
            handler._json_response(200, {"status": "ok", **result})
    except Exception as e:
        handler._json_response(500, {"error": str(e), "traceback": traceback.format_exc()})
    finally:
        _teardown_project(old)


def handle_review(handler, db_path: str, **kwargs) -> None:
    """POST /tasks/review — write a review verdict and advance the task phase.

    Body: {
        "agent_name": "...",       (required)
        "task_id": 42,             (required)
        "project_path": "/...",    (required)
        "passed": true,            (required)
        "notes": "review notes"    (optional)
    }

    Pseudo-logic:
      1. Parse and validate body
      2. Validate passed field is boolean
      3. Set project context
      4. Call tasks.review.review_task(agent_name, task_id, passed, notes)
      5. Return result
    """
    body = handler._parse_json_body()
    if not body:
        return

    agent_name, task_id, project_path, error = _validate_base_fields(body)
    if error:
        handler._json_response(400, {"error": error})
        return

    passed = body.get("passed")
    if not isinstance(passed, bool):
        handler._json_response(400, {"error": "passed must be a boolean (true/false)"})
        return

    # PSEUDO: convert boolean passed to verdict string for create_review
    verdict = "pass" if passed else "fail"
    notes = body.get("notes", "")
    if not isinstance(notes, str):
        notes = ""

    old = _setup_project(project_path)
    try:
        from minion.tasks.review import create_review
        result = create_review(agent_name, task_id, verdict=verdict, notes=notes)
        if "error" in result:
            handler._json_response(400, result)
        else:
            handler._json_response(200, {"status": "ok", **result})
    except Exception as e:
        handler._json_response(500, {"error": str(e), "traceback": traceback.format_exc()})
    finally:
        _teardown_project(old)


def handle_test(handler, db_path: str, **kwargs) -> None:
    """POST /tasks/test — write a test report and advance the task phase.

    Body: {
        "agent_name": "...",       (required)
        "task_id": 42,             (required)
        "project_path": "/...",    (required)
        "passed": true,            (required)
        "report": "test output"    (optional)
    }

    Pseudo-logic:
      1. Parse and validate body
      2. Validate passed field is boolean
      3. Set project context
      4. Call tasks.test_report.test_task(agent_name, task_id, passed, report)
      5. Return result
    """
    body = handler._parse_json_body()
    if not body:
        return

    agent_name, task_id, project_path, error = _validate_base_fields(body)
    if error:
        handler._json_response(400, {"error": error})
        return

    passed = body.get("passed")
    if not isinstance(passed, bool):
        handler._json_response(400, {"error": "passed must be a boolean (true/false)"})
        return

    report = body.get("report", "")
    if not isinstance(report, str):
        report = ""

    old = _setup_project(project_path)
    try:
        from minion.tasks.test_report import create_test_report
        result = create_test_report(agent_name, task_id, passed=passed, output=report, notes="")
        if "error" in result:
            handler._json_response(400, result)
        else:
            handler._json_response(200, {"status": "ok", **result})
    except Exception as e:
        handler._json_response(500, {"error": str(e), "traceback": traceback.format_exc()})
    finally:
        _teardown_project(old)
