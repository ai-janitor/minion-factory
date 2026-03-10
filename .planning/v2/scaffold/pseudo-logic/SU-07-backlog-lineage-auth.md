# SU-07 Pseudo-Logic: Backlog Lineage and Auth Hardening

## File: `src/minion/backlog/promote.py`

```python
# Lineage fix: ensure requirement_id propagates
# In promote():
#   result = register(...)  # from requirements/crud.py
#   requirement_id = result.get("id") or result.get("requirement_id")
#   # IF requirement_id not in return value:
#   #   Query: SELECT id FROM requirements WHERE slug = <slug> ORDER BY id DESC LIMIT 1
#   # Include in return dict: {"requirement_id": requirement_id, ...}
#
# Crew display: verify result includes "required_crew" and "available_characters"
#   These come from _scan_crew_characters() — verify it's called and result is included
```

## File: `src/minion/cli/backlog_cmds.py`

```python
# Auth gate for cross-project mutations:
# For each of: backlog_add, backlog_update, backlog_close commands:
#
#   # At the top of the command handler, before any DB operation:
#   if is_cross_project():
#       agent_class = os.environ.get("MINION_CLASS", "")
#       if agent_class not in ("lead", "coordinator", "sys"):
#           click.echo(json.dumps({"error": "BLOCKED: Backlog mutations on foreign projects require lead class."}))
#           ctx.exit(1)
#           return
#
# is_cross_project() logic:
#   project_dir = os.environ.get("MINION_PROJECT_DIR", "")
#   cwd = os.getcwd()
#   return project_dir and os.path.abspath(project_dir) != os.path.abspath(cwd)
```

## File: `src/minion/auth.py`

```python
# New helper:
def is_cross_project() -> bool:
    """Return True if -C flag is active (targeting foreign project).

    # Compare MINION_PROJECT_DIR env var to cwd
    # If they differ -> cross-project operation
    # If MINION_PROJECT_DIR not set -> not cross-project (local operation)
    """
```
