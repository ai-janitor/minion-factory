# SU-20 Pseudo-Logic: Agent Experience Improvements

## MODIFY: src/minion/lifecycle.py — cold_start() enhancement

```python
def cold_start(agent_name: str) -> dict:
    """Generate live operational briefing for agent first-session entry.

    # CURRENT: returns static onboarding info
    # ENHANCED: returns live state snapshot
    #
    # 1. Get agent record: query agents table for name, class, status, hp
    # 2. Get current assignment: query tasks WHERE assigned_to = agent_name AND status NOT IN terminal
    # 3. Get unread count: query messages WHERE to_agent = agent_name AND read_flag = 0
    #    Also get sender names for unread messages
    # 4. Get team: query agents table for all registered agents (name, class, status)
    # 5. Get battle plan: read .work/battle-plans/ for most recent file
    # 6. Get raid log: read .work/raid-log/ last 5 entries
    # 7. Get HP: from agent record
    # 8. Get file claims: query file_claims WHERE agent_name = agent_name
    #
    # Return structured dict:
    # {"agent": {...}, "tasks": [...], "unread": {"count": N, "from": [...]},
    #  "team": [...], "battle_plan": "...", "raid_log": [...],
    #  "hp": {...}, "claims": [...]}
    #
    # Performance target: <2 seconds (all queries are indexed)
    """
```

## NEW: src/minion/cli/completion_cmds.py

```python
"""Shell completion install and show commands.
Purpose: Set up CLI tab completion for bash/zsh.
"""

# @click.group("completions")

# @completions.command("show")
# def show():
#     """Print completion script to stdout.
#     # Detect shell from $SHELL env var
#     # Generate completion script via Click's built-in mechanism
#     # For bash: _MINION_COMPLETE=bash_source
#     # For zsh: _MINION_COMPLETE=zsh_source
#     # Print to stdout
#     """

# @completions.command("install")
# def install():
#     """Install completion script into shell rc file.
#     # 1. Detect shell (bash/zsh) from $SHELL
#     # 2. Determine rc file: ~/.bashrc or ~/.zshrc
#     # 3. Generate the source line: eval "$(_MINION_COMPLETE=<shell>_source minion)"
#     # 4. Check if line already in rc file (idempotent)
#     # 5. If not present: append to rc file
#     # 6. Print instructions: "Completion installed. Restart shell or source <rc_file>"
#     """
```

## MODIFY: src/minion/cli/main.py

```python
# Add completions group to CLI:
# from minion.cli.completion_cmds import completions
# cli.add_command(completions)
```

## NEW: .planning/research-prompt-strategy.md

```
# Document prompt assembly order:
# 1. System prompt: src/minion/prompts/system_prompt.py assembles base prompt
# 2. Role prompt: loaded from src/minion/prompts/roles/<role>/prompt.md
# 3. Self-service block: injected from _self_service_chore_block.md
# 4. Boot prompt: src/minion/prompts/boot_prompt.py adds onboarding context
# 5. Inbox prompt: src/minion/prompts/inbox_prompt.py adds unread messages
# 6. History: src/minion/prompts/_history.py adds conversation context
# 7. Rules: src/minion/prompts/_rules.py adds behavioral rules
# 8. Character overrides: crew YAML system_prefix field prepended
# 9. Scope/project context: injected based on agent's scope_mode
#
# Extension points:
# - New role: add src/minion/prompts/roles/<new_role>/prompt.md
# - New research domain: add to .work/intel/<category>/ — automatically picked up
# - Character customization: crew YAML system_prefix field
```
