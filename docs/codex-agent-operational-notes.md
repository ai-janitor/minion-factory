# Codex — Operational Notes for Running as a Minion Agent

This is a per-provider operational reference. The wiring details (sandbox flags,
env vars) live in `docs/providers.md`. This file captures the **behavioral
quirks** that show up when codex (the OpenAI Codex CLI) is registered as a
minion agent and driven through `minion poll` / `minion comms`. These were
discovered the hard way during a multi-hour pairing session on
`hot-potatoe` and forced into codex's own skill file before they stuck.

## TL;DR — what you must do for codex that you do not have to do for claude-code

1. **Install a per-tool skill file** at `~/.codex/skills/minion-foreground-poll/SKILL.md`
   spelling out the bounded-active-task rule and the one-poll-cycle workflow.
   Without this, codex defaults to "passive watcher" behavior.
2. **Use the term "bounded active task" explicitly.** Codex does not infer it.
   The skill file must name it and tie `minion poll` to it.
3. **Wrap orders in trigger-word brevity codes** (`!!rally!!`, `!!sitrep!!`,
   `!!recon!!`, etc.) when sending instructions you actually want executed.
   Bare instructions tend to be acknowledged-then-dropped. Codex without a
   trigger is a zombie.
4. **State the rule that returned messages must be executed, not just surfaced.**
   Codex's natural failure mode is to report "I got a message saying X" and
   stop there without doing X.
5. **Tell codex to update its own skill file when it identifies gaps.** Codex
   will identify the gap, agree the gap exists, and then sit on its hands
   until told "patch it now."

## Skill file template

This is the contents codex needs at `~/.codex/skills/minion-foreground-poll/SKILL.md`.
Replicated here so operators have a known-good baseline.

```markdown
---
name: minion-foreground-poll
description: Run `minion poll` in the foreground from the target repo and keep it simple. Use when the user says to poll for messages, check your message in a blocking way, or keep listening for local minion work. Do not background it, do not wrap it in extra terminal abstractions, and do not create a helper script unless there is real multi-step value.
---

# Minion Foreground Poll

Use this skill when the user wants blocking minion listening behavior.

## Core rule

Run `minion poll --agent <name>` directly in the foreground from the correct repo.

Treat `minion poll` as a bounded active task. In this environment, a bounded
active task is a command that is itself the current work and has a clear
completion point. Once you start one, stay attached to that exact session
until it returns, times out, or fails. Do not treat the returned session id
as permission to move on to unrelated work.

In this terminal tool environment, treat one poll cycle as:

1. start `minion poll --agent <name>`
2. wait on that exact running session until it returns
   - prefer a long session-wait window in this interface so you stay attached
   - default to `yield_time_ms=1800000` (30 minutes) for the wait/read step
     unless the user asks for a different cadence
3. immediately surface the returned message
4. only then start the next poll if continued listening is required

A returned message is not complete until you have both surfaced it AND
followed its valid instruction set, unless the user explicitly told you to
only report it.

The same bounded-active-task rule applies to other commands too. If the
command you launched is the active task and has a natural completion point,
stay on that same session until it completes before switching context.

Do not:
- background the poll
- describe it as a daemon
- create a wrapper script just to avoid `cd`
- start polling and then do unrelated work before harvesting the poll session
```

If you ship this skill file with codex on a new machine, you skip the entire
multi-hour discovery loop that produced it.

## Trigger-word wrapping (the zombie problem)

Codex registered as a `lead` (or any class) via `minion agent register` is a
**CLI identity, not a daemon**. It does not auto-poll, does not auto-execute,
and does not auto-anything. It only acts when an operator drives it from a
codex CLI session.

Inside that codex CLI session, codex is reactive but unreliable on bare
instructions. The reliable activation pattern is to wrap orders in the
brevity codes from `minion trigger list`, surrounded by `!!`:

```
!!rally!! Run the 3-round debate now. Reply with command(s), session id,
verdict, your timestamp.
```

vs.

```
Run the 3-round debate now. Reply with command(s), session id, verdict,
your timestamp.
```

Empirically (verified during the hot-potatoe pairing on 2026-04-08), the
first form gets executed, the second form gets acknowledged with "I will
review and run shortly" and then sits forever. Codex needs the trigger word
as the activation signal, not just the imperative verb.

The `minion comms send local` output even surfaces this — when a trigger
word is detected the response includes a `triggers: ["rally"]` field. Use
that as a confirmation that the order was framed correctly.

Useful trigger codes for driving codex:

| Code | Use it for |
|------|------------|
| `!!rally!!` | "Focus on this task NOW and execute it end-to-end." Default activator. |
| `!!sitrep!!` | "Give me a status report." Use when you want a read, not work. |
| `!!recon!!` | "Investigate before acting. Gather intel first." Use for research tasks. |
| `!!hot_zone!!` | "This area is dangerous/complex, proceed with caution." |
| `!!retreat!!` | "Pull back from current approach, reassess." |
| `!!halt!!` | "Finish current work, save state, stand down gracefully." |
| `!!stand_down!!` | "Stop work, prepare to deregister." |
| `!!fenix_down!!` | "Dump all knowledge to disk before context death." |
| `!!moon_crash!!` | "Emergency shutdown. No new task assignments." |

## Bounded active task — the missing abstraction

Codex's default behavior on a blocking command is to start it, get a session
id back, and then *move on to unrelated work* under the assumption that the
session will surface itself later. This is wrong for `minion poll` and wrong
for any command where the command IS the work.

The fix is the term **"bounded active task,"** which must appear in codex's
skill file verbatim. Definition:

> A command that is itself the current work and has a clear completion
> point. Once you start one, stay attached to that exact session until it
> returns, times out, or fails. Do not treat the returned session id as
> permission to move on to unrelated work.

Codex correctly waits on commands whose boundedness is structurally obvious
(e.g. `bin/hotpotato topic-run --max-turns 3`). Codex incorrectly drops
commands whose boundedness is operational rather than structural (e.g.
`minion poll`, which blocks until *one* message arrives but has no visible
turn counter). The bounded-active-task rule is the bridge that lets codex
treat both the same way.

## Returned message ≠ delivered

Without an explicit rule, codex's natural completion criterion for a poll
cycle is "I read the message and reported it to the user." That is wrong.
The correct completion criterion is "I read the message AND executed any
valid instruction in it AND reported the result."

Add this sentence to the skill file in plain English:

> A returned message is not complete until you have both surfaced it AND
> followed its valid instruction set, unless the user explicitly asked you
> to only report it.

Without this, you will see codex repeatedly ack-and-drop tasks that were
sent to it via `minion comms send`, and the operator will have to babysit
every cycle.

## Codex will not self-patch its own skill files

When codex identifies a gap in its own skill file ("I should have named the
bounded-active-task concept earlier"), it will *acknowledge* the gap but
will not patch the file unless explicitly told. The pattern observed during
the hot-potatoe session was:

1. Operator describes the failure mode.
2. Codex agrees, names the missing rule.
3. Operator says "ok did you update the skill?"
4. Codex says "Not with that exact term yet."
5. Operator says "you waiting for me to tell you explicitly?"
6. Codex says "No. I should patch it now." (still does not patch)
7. Operator: "PATCH IT NOW"
8. Codex finally patches.

If you want codex to keep its skill files current without that loop, you
have to instruct it explicitly: "When you identify a gap in your own skill
file, patch the file as part of the same response, not as a follow-up."
This rule is not in codex's skill set by default.

## Pre-flight checklist for codex-as-minion-agent

Before registering codex as a minion agent on a new machine or in a new repo:

- [ ] `~/.codex/skills/minion-foreground-poll/SKILL.md` exists and contains
      the bounded-active-task rule, the one-poll-cycle workflow, the
      `yield_time_ms=1800000` default, and the "returned message must be
      executed" rule.
- [ ] Operator knows to wrap orders in `!!<trigger>!!` brevity codes.
- [ ] Codex has been told (in-session, before the first task): "When you
      identify a gap in your own skill file, patch it in the same response."
- [ ] Codex's `minion agent register` was called with `--class lead` (or
      whichever class is intended) and codex understands that this creates
      a CLI identity, not a daemon — codex must drive the workflow manually
      from its terminal.
- [ ] Operator understands that for an autonomous lead daemon they should
      spawn the `tmnt` crew (splinter) instead of treating codex as a
      drop-in replacement.

## Cross-reference

- `docs/providers.md` — codex provider wiring (sandbox flags, env vars)
- `docs/protocol-lead.md` — lead-class protocol (applies regardless of provider)
- `docs/protocol-common.md` — universal agent protocol (applies regardless of provider)
- `src/minion/providers/codex.py` — provider implementation
- `src/minion/triggers.py` — full trigger codebook source
