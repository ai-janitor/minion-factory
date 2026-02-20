# Auth — Agent Classes, Capabilities & Permissions

Every agent has a **class**. A class is a bundle of **capabilities**, permissions, resource constraints, and onboarding. The system routes work by capability, gates commands by class.

## Design Principles

1. **Class = capability bundle.** No separate concepts. A class IS what it can do.
2. **Generalists for small teams, specialists for large ones.** Combo classes (builder, recon) cover multiple capabilities so a 3-agent crew can run the full pipeline. Specialist classes (coder, oracle, auditor, planner) are luxuries for larger crews.
3. **Minimum viable crew = 3.** `lead + builder + recon` covers all non-plan capabilities. Every other composition is either bigger or has gaps.
4. **Single source of truth.** Classes, capabilities, and all policy live in `src/minion/auth.py`. Everything else derives.

## Capabilities

7 capabilities describe what agents can do. Defined as constants in `auth.py`.

| Constant | Value | Meaning |
|----------|-------|---------|
| `CAP_MANAGE` | `manage` | Task lifecycle, session orchestration |
| `CAP_CODE` | `code` | Write implementation code |
| `CAP_BUILD` | `build` | Package, deploy, release |
| `CAP_REVIEW` | `review` | Code review, quality checks |
| `CAP_TEST` | `test` | Run tests, verify builds |
| `CAP_INVESTIGATE` | `investigate` | External research, intel gathering |
| `CAP_PLAN` | `plan` | Specs, architecture, sequencing |

Query by capability:

```python
from minion.auth import classes_with, CAP_REVIEW

classes_with(CAP_REVIEW)  # → {"oracle", "recon", "auditor"}
```

## Classes

7 classes, each a unique capability mix.

| Class | Capabilities | Context Timeout | Model Restriction |
|-------|-------------|-----------------|-------------------|
| **lead** | manage, review | 15 min | opus, sonnet, gemini-pro |
| **coder** | code | 5 min | opus, sonnet, gemini-pro |
| **builder** | code, test, build | 5 min | any |
| **oracle** | review | 30 min | any |
| **recon** | review, test, investigate | 5 min | any |
| **planner** | plan | 15 min | opus, sonnet, gemini-pro |
| **auditor** | review, test | 5 min | any |

### Capability Coverage by Team Size

| Size | Crew | Capabilities Covered | Gaps |
|------|------|---------------------|------|
| **2** | lead + builder | manage, review, code, test, build | investigate, plan |
| **3** | lead + builder + recon | manage, review, code, build, test, investigate | plan |
| **4** | lead + builder + recon + planner | **all 7** | none |

Specialists (coder, oracle, auditor) add depth to larger crews — they never reduce minimum team size.

## Command Permissions

### Lead Only

```
create-task, assign-task, close-task
set-battle-plan, update-battle-plan-status
party-status, check-freshness, update-hp
debrief, end-session, clear-moon-crash
stand-down, retire-agent, rename
list-crews
```

### Coder / Builder / Planner Only

```
claim-file, release-file
```

### All Classes

```
register, deregister, set-context, set-status
send, check-inbox, get-history, purge-inbox
who, sitrep
pull-task, update-task, complete-task, submit-result
get-tasks, get-task, task-lineage
get-claims, log-raid, get-raid-log
cold-start, fenix-down
poll, tools
```

## Model Whitelist

- **lead, coder, planner** — opus, sonnet, gemini-pro (needs strong reasoning)
- **oracle, recon, builder, auditor** — any model (cheap is fine)

## How Auth Works

The `MINION_CLASS` env var is set when spawning agents. The `@require_class` decorator on CLI commands checks the caller's class before executing.

```bash
export MINION_CLASS=coder
minion create-task ...  # BLOCKED — coder can't create tasks
```

Capability queries use `classes_with()` for workflow routing:

```python
from minion.auth import CAP_REVIEW, classes_with

# Polling: which classes can review fixed tasks?
reviewers = classes_with(CAP_REVIEW)  # derives from CLASS_CAPABILITIES
```

## Adding a New Class

All in `src/minion/auth.py`:

1. Add to `VALID_CLASSES`
2. Add to `CLASS_CAPABILITIES` with capability constants
3. Add to `CLASS_MODEL_WHITELIST`
4. Add to `CLASS_STALENESS_SECONDS`
5. Add to `CLASS_BRIEFING_FILES`
6. Add class-specific entries in `TOOL_CATALOG` if needed
7. Create `docs/protocol-<class>.md`

Everything else (routing, polling, spawn, tmux colors) derives automatically.

## Source

`src/minion/auth.py` — classes, capabilities, permissions, model whitelist, `require_class()` decorator, `classes_with()` query helper.
