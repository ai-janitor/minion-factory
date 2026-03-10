# SU-15 Pseudo-Logic: CLI Consistency

## 4.3.1 — Verb vocabulary

```python
# Step 1: Audit current command names
#   minion --help | grep -E "^\s+\w"  # list all top-level commands
#   minion agent --help  # list all agent subcommands
#   minion task --help   # etc.

# Step 2: Identify inconsistencies against the standard verb table
# Step 3: For renamed commands: create hidden alias with deprecation warning

# In cli/main.py or cli/aliases.py:
# @cli.command(hidden=True)
# def old_name():
#     click.echo("WARNING: 'old_name' is deprecated. Use 'new_name'.", err=True)
#     ctx.invoke(new_name)
```

## 4.3.2 — Exit codes

```python
# Audit all sys.exit() and ctx.exit() calls in src/minion/cli/*.py
# For each:
#   success -> exit(0)
#   error (operation failed) -> exit(1)
#   usage error -> Click handles this automatically (exit 2)
#   stand-down/retire -> exit(3) — preserve existing contract for poll
```

## 4.3.3 — Short flags

```python
# For each high-frequency option, add short flag:
# @click.option("--agent", "-a", ...)
# @click.option("--message", "-m", ...)
# etc.
#
# Per-command conflict check:
#   -a (agent), -m (message), -f (from), -t (to), -s (status),
#   -n (name), -c (class), -r (reason), -F (file), -x (context)
# Global: -C (project-dir) — already taken, don't reuse
```

## 4.3.4 — Top-level command leaks

```python
# Move from root to agent group:
# deregister -> agent deregister
# rename -> agent rename
# interrupt -> agent interrupt
# resume -> agent resume

# In cli/agent_cmds.py: add the commands to the agent group
# In cli/top_level.py: keep as hidden aliases with deprecation warning

# Alias pattern:
# @cli.command("deregister", hidden=True, deprecated=True)
# def deregister_alias(**kwargs):
#     """DEPRECATED: Use 'minion agent deregister'."""
#     click.echo("DEPRECATED: Use 'minion agent deregister'", err=True)
#     ctx.invoke(agent_deregister, **kwargs)
```
