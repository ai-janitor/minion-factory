# SU-19 Pseudo-Logic: Cross-Project Coordination

## MODIFY: src/minion/polling.py — new function

```python
def multi_project_poll(agent_name: str, project_paths: list[str] | None = None) -> dict:
    """Poll for messages and tasks across multiple projects.

    # Step 1: Discover project paths
    #   IF project_paths provided: use them
    #   ELIF MINION_PROJECTS env var set: split by ":" into list
    #   ELSE: query coordinator DB for distinct project_path values
    #         SELECT DISTINCT project_path FROM agents
    #         WHERE scope_mode matches coordinator's scope
    #   FALLBACK: if coordinator DB unavailable, return single-project poll result

    # Step 2: For each project path:
    #   IF not os.path.isdir(path): skip, log warning
    #   db_path = os.path.join(path, ".work", "minion.db")
    #   IF not os.path.exists(db_path): skip, log warning
    #   TRY:
    #     conn = connect(db_path)
    #     messages = query unread messages for agent_name
    #     tasks = query available/assigned tasks for agent_name
    #     conn.close()
    #   EXCEPT sqlite3.OperationalError: skip, log warning (DB locked/corrupt)

    # Step 3: Aggregate results
    #   return {"projects": [
    #     {"path": path, "messages": [...], "tasks": [...]},
    #     ...
    #   ]}
    """
```

## MODIFY: src/minion/auth.py

```python
# Add "coordinator" to class handling:
#
# In VALID_CLASSES or equivalent:
#   Add "coordinator"
#
# In permissions mapping:
#   "coordinator": same as "lead" PLUS:
#     - exempt from cross-project auth blocks (is_cross_project check)
#     - can register/deregister agents across projects
#     - can send global messages
#
# In is_cross_project() (from SU-07):
#   IF agent_class == "coordinator": return False  # coordinators are never "foreign"
```

## MODIFY: src/minion/tasks/agent_classes.py

```python
# Add coordinator class definition:
# AGENT_CLASSES["coordinator"] = {
#     "capabilities": ["manage", "monitor", "investigate", "plan"],
#     "models": ["claude-opus-4", "claude-sonnet-4"],
#     "description": "System-wide lead over multiple project leads"
# }
```

## MODIFY: src/minion/comms/send.py

```python
# Add formalized sitrep function:
def sitrep_global(from_agent: str, to_agent: str, summary: str) -> dict:
    """Send a global sitrep from project lead to sys-lead.

    # 1. Build message: {"msg_type": "sitrep", "content": summary}
    # 2. Call send_global(from_agent, to_agent, message)
    # 3. Return send result
    # This is a convenience wrapper — same as send global with msg_type=sitrep
    """
```

## MODIFY: src/minion/cli/comms_cmds.py

```python
# Add CLI command:
# @comms_group.command("sitrep")
# @click.option("--to", "-t", required=True)
# @click.option("--scope", default="local", type=click.Choice(["local", "global"]))
# @click.option("--message", "-m", required=True)
# def sitrep(to, scope, message):
#   IF scope == "global": call sitrep_global()
#   ELSE: call send() with msg_type="sitrep"
```

## MODIFY: src/minion/defaults.py

```python
# Add MINION_PROJECTS env var support:
def get_project_paths() -> list[str]:
    """Get list of known project paths.
    # 1. Check MINION_PROJECTS env var (colon-separated)
    # 2. If set: split and return as list
    # 3. If not set: return empty list (caller falls back to coordinator DB)
    """
```
