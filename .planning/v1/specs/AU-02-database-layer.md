# AU-02: Database Layer Deep Dive

## Purpose

Line-by-line audit of the database layer against applicable skill checklists. The db package is the data foundation — schema, migrations, connection management, and query patterns.

## Scope

| Directory/File | Description |
|----------------|-------------|
| `src/minion/db/__init__.py` | Package exports, get_db() |
| `src/minion/db/schema.py` | Table definitions (14 tables) |
| `src/minion/db/migrations.py` | Migration system (v1-v13) |
| `src/minion/db/queries.py` | Shared query functions |
| `src/minion/db/project_db.py` | Project-level DB operations (if exists) |
| `src/minion/db/coordinator_db.py` | Coordinator DB operations (if exists) |
| `src/minion/db/utils.py` | DB utilities (if exists) |

**Also check for DB pattern compliance in:**
- `src/minion/tasks/db.py` — task-specific DB operations (boundary B-06 with AU-04)
- `src/minion/network/project_db.py` — network DB operations (boundary B-04 with AU-06)

Read ALL files in `src/minion/db/`. Then spot-check tasks/db.py and network/project_db.py for pattern consistency.

## Skills to Evaluate

### CS Foundations — Data Architecture (CS-DATA, all 6 rules)
- **DATA-1:** Data ownership — which component owns which data (single writer)?
  - **How to check:** Read schema.py. Map each table to the package that writes to it. Check for multiple writers to the same table.
  - **Evidence for YES:** Each table written by one package only.
  - **Evidence for NO:** Multiple packages INSERT/UPDATE the same table.
- **DATA-2:** State model — current-state snapshot, event log, or hybrid?
  - **How to check:** Check if tables store current state or append-only event logs. Check for audit columns (created_at, updated_at).
- **DATA-3:** Storage choice justified — relational, document, key-value, graph, file?
  - **How to check:** SQLite is relational. Check for JSON columns (hybrid). Assess whether choice fits the use case.
- **DATA-4:** Schema strategy — schema-on-write (strict) or schema-on-read (flexible)?
  - **How to check:** Read schema.py CREATE TABLE statements. Check column types and constraints.
- **DATA-5:** Data lifecycle — creation, mutation rules, archival, deletion?
  - **How to check:** Search for DELETE statements. Check for cleanup/archival logic. Check for TTL or retention policy.
- **DATA-6:** Derived data identified — what is computed from other data vs stored directly?
  - **How to check:** Check for computed columns, views, or query-time aggregations.

### CS Foundations — Consistency & State (CS-CONSIST, all 5 rules)
- **CONSIST-1:** Consistency model — strong, eventual, or per-aggregate?
  - **How to check:** SQLite provides strong consistency per DB. Check for cross-DB operations.
- **CONSIST-2:** Transaction boundaries — what must succeed or fail atomically?
  - **How to check:** Grep for `with conn:` or `conn.commit()`. Check if multi-step operations use transactions.
- **CONSIST-3:** Concurrency strategy — locks, optimistic concurrency, actors, channels, none?
  - **How to check:** Check for WAL mode configuration. Check for threading locks. Check for version columns.
- **CONSIST-4:** Idempotency — which operations must be safely retriable?
  - **How to check:** Check migrations for IF NOT EXISTS. Check for upsert patterns (INSERT OR REPLACE).
- **CONSIST-5:** Ordering guarantees — does message/event order matter? How enforced?
  - **How to check:** Check for ORDER BY in queries. Check for timestamp or sequence columns.

### Clean Architecture (selected rules)
- **CA-DEP-1:** Source code dependencies point only inward — db/ should have zero imports from higher layers
  - **How to check:** `grep -r "from minion" src/minion/db/` — should only import from stdlib or db/ itself.
- **CA-DEP-2:** Entities have zero external/framework imports — db models should be clean
- **CA-BOUND-3:** Data crossing boundaries is simple structures — check what db functions return (dicts, Rows, or domain objects)

### Pragmatic Programmer (selected rules)
- **PP-DRY-1:** Single authoritative representation — is get_db() the one way to get a connection?
  - **How to check:** Grep for `sqlite3.connect` across the codebase. Should only be in db/ package.
- **PP-DRY-2:** No inter-developer duplication — check tasks/db.py and network/project_db.py for reimplemented patterns.
- **PP-ORTH-1:** Components self-contained — db/ package is independent.
- **PP-CRAFT-5:** Names reveal intent — check function and table names.

### Implementation Coding Core (selected rules)
- **IC-HDR-1 through IC-HDR-5:** File headers — reference AU-00 systemic finding. Note db-specific details only.

## Audit Procedure

### Step 1: Schema Analysis
1. Read `src/minion/db/schema.py` in full
2. List all 14 tables with their columns, types, and constraints
3. Map each table to its owning package (who writes to it)
4. Check for: foreign keys, indexes, NOT NULL constraints, defaults

### Step 2: Migration System Review
1. Read `src/minion/db/migrations.py` in full
2. Verify: each migration is in a transaction
3. Verify: migrations are idempotent (IF NOT EXISTS, IF NOT COLUMN)
4. Check version tracking mechanism
5. Check: can migrations be re-run safely?

### Step 3: Connection Pattern Review
1. Read `src/minion/db/__init__.py` — find get_db()
2. Check: WAL mode enabled? Row factory set?
3. Check: per-operation connections or connection pooling?
4. Check: proper cleanup (connection close)?
5. Grep entire codebase for `sqlite3.connect` to find any bypass of get_db()

### Step 4: Query Pattern Review
1. Read all query functions in db/
2. Check: parameterized queries (no string formatting with user input)?
3. Check: consistent return types (Row objects, dicts, or tuples)?
4. Check: error handling on queries (what happens on sqlite3.Error?)

### Step 5: Cross-Package DB Pattern Check (Boundary B-06)
1. Read `src/minion/tasks/db.py` — does it follow db/ patterns?
2. Read `src/minion/network/project_db.py` — does it follow db/ patterns?
3. Check: do they import from db/ or reimplemented get_db()?
4. Check: same connection pattern, same Row factory?

### Step 6: Rule-by-Rule Evaluation
For each rule above, evaluate YES/NO/N/A with specific evidence.

## Expected Findings from Research

1. **DB pattern is clean** — get_db(), WAL, Row factory consistently used. Likely mostly PASS.
2. **Migration system works** — versioned v1-v13, idempotent, transactional. PASS.
3. **Three separate DBs** — project, coordinator, network. Data ownership clear. PASS.
4. **Inline SQL everywhere** — no repository abstraction. This is a style choice, not necessarily a finding.
5. **Per-operation connections** — no connection pooling. At this scale, not a problem. Note as SCALE observation.
6. **DATA-5 partial:** No archival/deletion strategy. No TTL on messages. Minor finding.
7. **CONSIST-2 partial:** Some callers don't use `with conn:` for transactions. Needs deep dive to identify which.
8. **CONSIST-4 NO:** Core operations (task create, agent register) not explicitly idempotent.
9. **Boundary B-06:** tasks/db.py may diverge from canonical db/ patterns — needs verification.

## Output Format

```markdown
# AU-02 Database Layer Audit Results

## Schema Summary
[14 tables, ownership map]

## Filled Checklist

### CS Foundations — Data Architecture
| Rule | Status | Evidence |
|------|--------|----------|
| DATA-1 | YES/NO/N/A | [specific evidence] |
...

### CS Foundations — Consistency & State
...

### Clean Architecture (DB-applicable subset)
...

### Pragmatic Programmer (DB-applicable subset)
...

### Implementation Coding Core (DB-applicable subset)
...

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
...

## Strengths
- [patterns the DB layer gets right]

## Boundary Check: B-06 (Task Engine DB)
[Consistency assessment between db/ and tasks/db.py]
```
