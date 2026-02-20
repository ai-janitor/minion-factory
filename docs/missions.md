# Missions — Capability-Driven Team Composition

A mission declares what capabilities are needed. The system derives the slots, you draft the characters.

## Three-Layer Model

```
Mission   →  what you WILL do   (required capabilities, team slots)
Class     →  what you CAN do    (capabilities, permissions, routing)
Character →  who you ARE         (name, system prompt, pre-loaded skills)
```

**Mission** picks capability slots to fill. **Class** filters which characters qualify for each slot. **Character** brings the specialization — pre-prompted with specific skills, tools, and domain knowledge.

Same class, different characters:

| Character | Crew | Class | Specialization |
|-----------|------|-------|---------------|
| ba | ateam | builder | Python, infrastructure |
| barret | ff7 | builder | TypeScript, frontend |
| yang | ff1 | builder | Rust, systems |
| cloud | ff7 | coder | Full-stack, general |

All builders can `code + test + build`. But BA knows infra, Barret knows frontend. The mission says "I need a builder" — you pick the one with the right skills for this particular job.

## Party Selection

Like Kingdom Hearts — pick your world (mission), draft your party (characters).

```bash
# 1. Pick mission type
minion mission spawn bugfix

# 2. System resolves capability slots
#    bugfix needs: manage, investigate, code, test, review
#    Minimum slots: lead + builder + recon

# 3. System shows eligible characters from ALL crews
#    lead slot:    murdock (ateam), cecil (ff1), cloud (ff7)
#    builder slot: ba (ateam), yang (ff1), barret (ff7)
#    recon slot:   face (ateam), edward (ff1), yuffie (ff7)

# 4. You pick your party
minion mission spawn bugfix --party murdock,ba,face

# 5. System spawns with each character's pre-loaded system prompt
```

Mix and match across crews. The crew is the roster, not the team. Your party is mission-specific.

## Mission Templates

| Mission | Requires | Min Slots | Size |
|---------|----------|-----------|------|
| **prototype** | manage, code, build | lead + builder | 2 |
| **dependency-upgrade** | manage, code, test, build, review | lead + builder | 2 |
| **code-audit** | manage, review, investigate | lead + recon | 2 |
| **security-review** | manage, investigate, review | lead + recon | 2 |
| **documentation** | manage, investigate, review | lead + recon | 2 |
| **bugfix** | manage, investigate, code, test, review | lead + builder + recon | 3 |
| **migration** | manage, plan, code, test, build | lead + builder + planner | 3 |
| **bd-research** | manage, investigate, review, plan | lead + recon + planner | 3 |
| **competitive-analysis** | manage, investigate, plan | lead + recon + planner | 3 |
| **incident-response** | manage, investigate, code, test, build, review | lead + builder + recon | 3 |
| **new-feature** | manage, plan, code, test, build, review | lead + builder + recon + planner | 4 |

## Template Format

```yaml
# missions/bugfix.yaml
name: bugfix
description: Find bug, fix code, test, review fix
requires:
  - manage
  - investigate
  - code
  - test
  - review
```

## Slot Resolution

Given required capabilities, the resolver finds the minimum set of classes:

1. Start with `lead` (always required — owns `manage`)
2. Greedy: pick the class that covers the most uncovered capabilities
3. Repeat until all capabilities covered
4. Return the slots

7 capabilities, 7 classes — brute force is fine.

## Scaling Up

Min crew is the floor. Add specialists to let generalists focus:

- Heavy codebase → add **coder** (frees builder for build/test)
- Complex review → add **oracle** or **auditor** (frees lead for manage)
- Deep research → add extra **recon** for parallel investigation
- Multiple reviewers → add **auditor** for independent verification

## Character Design

Characters are defined in crew YAMLs. The system prompt is the specialization:

```yaml
# crews/ateam.yaml
agents:
  ba:
    role: builder
    system: |
      You are ba (builder class). The A-Team's muscle and mechanic.
      You build things, write code, run tests, deploy...
      # ^^^ This is the character. Class is just "builder".
```

When designing characters:
- **Class** handles permissions and routing — don't repeat that in the prompt
- **System prompt** handles personality, domain skills, tool preferences
- Characters from different crews can have wildly different prompts for the same class
- A good character prompt makes the agent effective at a specific type of work within its class

## Auto-Draft: AI Assembles the Team

Full automation — user describes the job, AI picks the party.

### Flow

```
User: "bugfix in this project"
  → AI scans project: Python, React, PostgreSQL, Docker
  → AI picks mission: bugfix
  → AI resolves slots: lead + builder + recon
  → AI scans ALL character rosters for skill match:
      builder slot: ba (python, docker, postgres) ✓  barret (typescript, react) partial
      recon slot:   face (api-research, docs) ✓  yuffie (codebase-exploration) ✓
      lead slot:    murdock (general) ✓
  → AI drafts: murdock + ba + face
  → Spawn
```

No manual selection. The AI is the matchmaker.

### Character Skills Metadata

Characters get `skills:` tags in crew YAMLs — searchable metadata the matchmaker reads:

```yaml
agents:
  ba:
    role: builder
    skills: [python, infrastructure, docker, postgres]
    system: |
      You are ba (builder class). The A-Team's muscle and mechanic...

  barret:
    role: builder
    skills: [typescript, react, nextjs, vercel]
    system: |
      You are barret (builder class). AVALANCHE's heavy gunner...
```

Same class, different skills. The matchmaker picks the character whose skills overlap most with the project's stack.

### Project Scan

The matchmaker reads the project to detect stack:

- `pyproject.toml`, `requirements.txt` → Python
- `package.json` → JavaScript/TypeScript, specific frameworks
- `Dockerfile`, `docker-compose.yaml` → container infra
- `Cargo.toml` → Rust
- `go.mod` → Go
- `.sql`, ORM configs → database type
- CI config → deployment target

### Matching Algorithm

1. Scan project → extract tech stack tags
2. Resolve mission → get capability slots
3. For each slot, score eligible characters: `overlap(character.skills, project.stack)`
4. Pick highest-scoring character per slot
5. Tiebreak: prefer characters from the same crew (team chemistry)
6. Validate coverage, spawn

### Spawn Modes

```bash
# Full auto — AI picks everything
minion mission auto "bugfix in this project"

# Semi-auto — AI suggests, you confirm
minion mission suggest bugfix

# Manual — you pick the party
minion mission spawn bugfix --party murdock,ba,face

# Legacy — spawn a whole crew (unchanged)
minion spawn-party --crew ateam
```

## Source

Mission templates: `missions/` directory (YAML files).
Capability constants: `src/minion/auth.py`.
Character roster: `crews/` directory (YAML files).
Resolver: TBD — `src/minion/missions/` when implemented.
