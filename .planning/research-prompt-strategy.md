# Research: Prompt Assembly Strategy

## SU-20: Agent Experience — Prompt Assembly Order

### Problem

Agent system prompts are assembled from multiple sources at spawn time:
1. `system_prefix` from crew YAML
2. Protocol doc for the agent's class
3. CLAUDE.md / project instructions
4. Cold-start operational state
5. Task-specific context (DAG position, spec file)

The order and priority of these pieces affects agent behavior.
Getting it wrong means agents ignore critical rules or waste context
on irrelevant information.

### Current Assembly Order

1. **Crew-level `system_prefix`** (via `--append-system-prompt` in Claude provider)
   - Injected at system prompt level, not user prompt
   - Contains scanning rules, output conventions, behavioral directives
   - Example: "ONLY scan src/ and tests/. Write findings to .work/intel/"

2. **CLAUDE.md** (loaded by Claude Code automatically)
   - Project-level instructions: DAG rules, polling protocol, scaffolding requirements
   - ~/.claude/CLAUDE.md for global rules

3. **Protocol doc** (`~/.minion_work/docs/protocol-{class}.md`)
   - Class-specific playbook loaded during cold-start
   - Defines what the agent can and cannot do

4. **Cold-start state** (returned by `minion cold-start`)
   - Battle plan, agents, tools, HP, open tasks, file claims
   - Fenix-down records for context revival

5. **Task context** (loaded when poll returns a task)
   - Task spec file content
   - DAG visualization showing current position
   - Suggested reading from intel docs

### Principles

- **System-level beats user-level**: `--append-system-prompt` is authoritative.
  Use for hard rules agents must not override.
- **Positive over negative**: "ONLY scan src/" not "NEVER scan .venv/".
  LLMs reliably follow positive instructions.
- **Earlier context has higher priority**: Items at the top of the context
  window get more attention. Put critical rules first.
- **Reduce redundancy**: Don't repeat CLAUDE.md rules in crew YAML.
  Reference once, enforce mechanically where possible.

### Recommendations

1. **Move hard rules to system_prefix**: DAG enforcement, file scope limits,
   output format requirements should be in `system_prefix` not CLAUDE.md.
   CLAUDE.md is for humans reading the repo; system_prefix is for agents.

2. **Cold-start should be compact**: The current cold_start returns everything.
   For agents with limited context windows, provide a "slim" mode that returns
   only: open tasks, HP, unread count, fenix records.

3. **Task context should include DAG render**: Already done in poll's
   _find_available_tasks. Ensure it's also in cold-start task enrichment.

4. **Prompt budget tracking**: Track how many tokens the system prompt consumes.
   If system_prefix + CLAUDE.md + cold-start > 20% of context window,
   the agent has less room for actual work. Monitor and trim.

### Implementation Status

- [x] system_prefix in crew YAML (implemented)
- [x] Claude provider uses --append-system-prompt (implemented)
- [x] cold_start returns operational state with tasks enriched (implemented)
- [x] Poll includes DAG render for available tasks (implemented)
- [x] Completion commands for CLI discovery (implemented, SU-20)
- [ ] Slim cold-start mode (future: reduce token overhead for small models)
- [ ] Prompt budget tracking (future: monitor context consumption)
