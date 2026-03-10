# SU-20: Agent Experience — Refresh, Cold-Start, Completions, Research Prompts

**Wave:** 6 (parallel within wave)
**Requirements:** 5.3.1, 5.3.2, 5.3.5, 5.3.6
**Dependencies:** None
**Dependents:** None

---

## Purpose

Four agent DX improvements: verify refresh works, enhance cold-start with live briefing, add shell completions, and document research prompt assembly.

## Requirements Traceability

- **5.3.1 (Refresh):** "Agent context refresh — mid-session state injection." — ALREADY IMPLEMENTED, verify.
- **5.3.2 (Cold-Start Live Briefing):** "Cold-start auto-generate operational state (live briefing, not static files)."
- **5.3.5 (Shell Completions):** "Shell completions for CLI (Click supports it)."
- **5.3.6 (Research Prompt Assembly):** "Research prompt assembly strategy for role/character/scope."

## Dependencies

None.

## Behavior

### 5.3.1 — Verify Refresh

**Current state:** `minion refresh --agent <name>` exists in `src/minion/lifecycle.py`.

**Verification:**
- Call `minion refresh --agent test-agent` after registering the agent
- Assert it returns current state: assigned tasks, unread message count, HP, registered agents, active claims
- Assert it does NOT modify any state (read-only operation)
- Assert output includes all info an agent needs to resume work mid-session

### 5.3.2 — Cold-Start Live Briefing

**Current state:** `minion cold-start --agent <name>` returns onboarding info. May be static.

**Target behavior:**
- Cold-start should generate a LIVE operational briefing, not just return static file contents
- Briefing includes:
  1. Agent's current assignment (tasks in progress)
  2. Unread messages (count and senders)
  3. Team composition (who else is registered)
  4. Active battle plan (if any)
  5. Recent raid log entries (last 5)
  6. HP status and warnings
  7. File claims held by this agent
- Format: structured dict that the CLI renders as human-readable briefing
- Difference from refresh: cold-start is for first session entry (more context), refresh is for mid-session updates (less context)

### 5.3.5 — Shell Completions

**Current state:** Click supports shell completions natively but no `_MINION_COMPLETE` setup exists.

**Target:**
- Add completion support via Click's built-in mechanism
- For bash: `eval "$(_MINION_COMPLETE=bash_source minion)"`
- For zsh: `eval "$(_MINION_COMPLETE=zsh_source minion)"`
- Add `minion completions install` command that:
  1. Detects current shell (bash/zsh)
  2. Generates completion script
  3. Appends source line to `~/.bashrc` or `~/.zshrc`
  4. Prints instructions for manual setup
- Add `minion completions show` command that prints the completion script to stdout

### 5.3.6 — Research Prompt Assembly

**Current state:** Prompt system exists in `src/minion/prompts/` with roles/, boot/, inbox/, protocol/ modules.

**Target:** Document the prompt assembly strategy:
- Create `.planning/research-prompt-strategy.md` describing:
  1. How role prompts are assembled (which files, in what order)
  2. How character system prompts override role defaults
  3. How scope/project context is injected
  4. How research findings (from `.work/intel/`) are incorporated into prompts
  5. How to extend the system for new roles or research domains
- This is documentation only — no code changes unless the investigation reveals a missing feature

## Constraints

- refresh and cold-start must not mutate state (read-only)
- Shell completions must not break existing CLI behavior
- Research prompt strategy is documentation only
- cold-start live briefing must be fast (<2 seconds) — no expensive queries

## Edge Cases

1. **Agent not registered:** Cold-start with unregistered agent should return minimal info (just "you're not registered" + registration instructions).
2. **No tasks assigned:** Cold-start briefing with empty task list should still be useful (show team status, battle plan).
3. **Shell completion conflicts:** If user already has a minion completion script, `completions install` should detect and skip (idempotent).
4. **Zsh vs bash:** Completion scripts differ. Detect shell from `$SHELL` env var.
5. **Cold-start performance:** If querying all state is slow, add a `--quick` flag for minimal briefing.

## Current State

- refresh command exists and works
- cold-start exists but may not generate live data
- No shell completions
- Prompt system exists but assembly strategy undocumented

## Test Contract

- **Test 1:** `minion refresh --agent test-agent` returns dict with keys: tasks, messages, hp, agents, claims.
- **Test 2:** `minion cold-start --agent test-agent` returns live briefing with current team composition.
- **Test 3:** `_MINION_COMPLETE=bash_source minion` outputs a bash completion script.
- **Test 4:** `minion completions install` is idempotent (running twice doesn't duplicate the source line).
- **Test 5:** `.planning/research-prompt-strategy.md` exists and documents assembly order.
