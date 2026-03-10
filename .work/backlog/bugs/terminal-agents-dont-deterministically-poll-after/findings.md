# Findings: Terminal Agents Don't Deterministically Poll After Work (#18)

## Root Cause: Multi-layered — Hook Format, Hook Scope, and Prompt Compliance

The enforcement failure has **three contributing causes**, ranging from definite bug to design gap.

---

### Cause 1 (BUG): settings.json hook structure is wrong

**Evidence:** `~/.claude/settings.json` currently contains:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/hung/.minion/hooks/poll-on-stop.sh"
          }
        ]
      }
    ]
  }
}
```

Claude Code expects Stop hooks as a flat array of hook objects under `hooks.Stop`, not a nested `hooks` array within each entry. The `install-hooks` command in `src/minion/cli/top_level.py` (lines 163-165) writes this incorrect nested structure:

```python
stop_hooks.append({
    "hooks": [{"type": "command", "command": hook_cmd}]
})
```

**Impact:** The hook may never fire because Claude Code doesn't recognize the nested format. This is the most critical cause — if the hook doesn't fire, there is zero mechanical enforcement.

**Fix:** Change the install-hooks command to write the flat format:
```python
stop_hooks.append({"type": "command", "command": hook_cmd})
```

And fix the dedup logic (lines 155-161) to match the flat format. Then re-run `minion install-hooks` to fix the settings.json on all machines.

---

### Cause 2 (DESIGN GAP): Stop hook only checks inbox — doesn't restart poll

**Evidence:** `scripts/poll-on-stop.sh` lines 81-109.

The hook checks if there are unread messages in the inbox. If the inbox is empty, it allows the stop (exit 0). If messages exist, it blocks the stop and tells the agent to poll.

**The gap:** The hook only fires when the agent **finishes responding**. The intended poll loop (CLAUDE.md lines 104-117) says agents must restart poll **immediately after processing a message** — GOTO step 1. But:

1. After the hook blocks and the agent polls + processes messages, the agent finishes responding again
2. Hook fires again — but now inbox is empty (messages were just consumed)
3. Hook allows stop — agent goes silent
4. No new messages arrive for a while → agent is deaf until next user input

The hook handles the "messages waiting right now" case but **not** the "agent should be perpetually polling" case. It's a one-shot check, not a loop enforcer. The `stop_hook_active` guard (line 46) explicitly prevents more than one continuation cycle.

**Fix options:**
- A) Remove the `stop_hook_active` one-cycle guard and instead always block stop if the agent is a registered minion (force perpetual poll). Risk: infinite loop if poll itself triggers a response.
- B) Have the hook block stop whenever a poll PID file does NOT exist for this agent — meaning "you stopped polling, you must restart it." Check `is_poll_alive()` logic from `polling.py` line 69.
- C) Inject a `transport_hint` reminder into every poll result (already done — `polling.py` line 410) AND have the hook check whether a poll process is alive, not just whether inbox has messages.

**Recommended:** Option B or C — check poll PID file existence rather than inbox contents. The question isn't "do you have messages now?" but "are you listening for future messages?"

---

### Cause 3 (PROMPT COMPLIANCE): Agents ignore the documented protocol

**Evidence:** CLAUDE.md lines 100-151 document the poll loop protocol exhaustively. The `transport_hint` in poll results (polling.py line 410-414) explicitly tells agents to restart polling. But terminal agents are LLMs — they process the instruction, do some work, and then their context moves on. The poll restart instruction competes with task completion instincts.

**This is the weakest link** because it's the only one that can't be mechanically enforced. Even with a perfect hook, agents must still execute `minion poll --agent <name>` as a CLI command. The hook can block the stop, but the agent might respond with something other than a poll command.

**Fix:** This cause is mitigated by fixing Causes 1 and 2. A working hook that checks for poll-alive (not just inbox) would mechanically force the agent to restart poll before it can go idle.

---

### Cause 4 (STALE INSTALL): Installed hook differs from repo version

**Evidence:** `diff` between `scripts/poll-on-stop.sh` and `~/.minion/hooks/poll-on-stop.sh` shows the installed copy is missing the SU-06 guards (lines 70-80 in repo version: `command -v minion` check and DB existence check). The installed version is older.

**Impact:** Minor — the missing guards are safety additions, not the core bug. But it indicates `minion install-hooks` hasn't been re-run after recent improvements.

**Fix:** Re-run `minion install-hooks` after fixing Cause 1.

---

## Summary

| # | Type | Severity | Description |
|---|------|----------|-------------|
| 1 | Bug | **Critical** | Hook format in settings.json is nested wrong — hook may never fire |
| 2 | Design gap | **High** | Hook checks inbox not poll-alive — one-shot, not perpetual |
| 3 | Prompt compliance | Medium | Agents don't reliably follow poll restart instructions |
| 4 | Stale install | Low | Installed hook script is behind repo version |

## Proposed Fix (Priority Order)

1. **Fix `install-hooks` in `src/minion/cli/top_level.py`** — write flat hook format, fix dedup logic
2. **Re-run `minion install-hooks`** to update settings.json and the installed script
3. **Modify `poll-on-stop.sh`** — check poll PID file alive instead of (or in addition to) inbox contents. Block stop whenever the agent is registered but has no active poll process.
4. **Test** — spawn a terminal agent, let it finish work, verify hook fires and forces poll restart

## Files Referenced

- `src/minion/cli/top_level.py` lines 105-213 — install-hooks command (Cause 1)
- `scripts/poll-on-stop.sh` — the stop hook script (Cause 2, 4)
- `~/.minion/hooks/poll-on-stop.sh` — installed copy (Cause 4)
- `~/.claude/settings.json` — hook registration (Cause 1)
- `src/minion/polling.py` lines 69-80 — `is_poll_alive()` function (useful for Cause 2 fix)
- `src/minion/polling.py` lines 409-414 — `transport_hint` in poll results (Cause 3)
- `src/minion/crew/terminal.py` lines 27-30 — env var injection at spawn time
- `CLAUDE.md` lines 100-178 — documented polling protocol and stop hook
