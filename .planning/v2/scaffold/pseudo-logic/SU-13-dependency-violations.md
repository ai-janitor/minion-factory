# SU-13 Pseudo-Logic: Dependency Layer Violation Fixes

## Violation 1: db/ imports auth

```python
# Step 1: Audit
#   grep -r "from minion.auth" src/minion/db/
#   grep -r "from minion import auth" src/minion/db/
#   grep -r "import auth" src/minion/db/

# Step 2: For each import found:
#   - Identify what's imported (VALID_CLASSES? require_class? etc.)
#   - If it's a constant (VALID_CLASSES): move constant to defaults.py, import from there
#   - If it's a function: pass as parameter instead of importing
#   - If it's a decorator: this shouldn't be in db/ at all — remove

# Step 3: Verify: grep returns empty for auth imports in db/
```

## Violation 2: tasks/ imports _tmux

```python
# Step 1: Audit
#   grep -r "_tmux" src/minion/tasks/

# Step 2: Current state check
#   - update_task.py imports "from minion.crew import update_pane_task"
#   - This goes through crew/__init__.py public API — CORRECT if exported
#   - Verify: "update_pane_task" in crew/__init__.py exports

# Step 3: If any direct _tmux import exists:
#   - Change to import through crew/ public API
#   - Add export to crew/__init__.py if needed
```

## Violation 3: comms <-> crew bidirectional coupling

```python
# Step 1: Identify the coupling
#   grep -r "from minion.crew" src/minion/comms/
#   grep -r "from minion.comms" src/minion/crew/
#   Focus on comms/register.py crew-context-merge logic

# Step 2: Extract to neutral location
#   - Read comms/register.py to find crew-context-merge logic
#   - Options for new home:
#     a. src/minion/lifecycle.py (if it's agent lifecycle context)
#     b. src/minion/agent_context.py (NEW — if logic doesn't fit elsewhere)
#   - Extract the function, update imports in both comms/ and crew/

# Step 3: Verify no circular imports:
#   python -c "from minion.comms import register; from minion.crew import spawn"
#   Must succeed without ImportError

# COORDINATION with SU-14:
#   If SU-14 already created shared modules that resolve some violations,
#   use those rather than creating new extraction targets.
```
