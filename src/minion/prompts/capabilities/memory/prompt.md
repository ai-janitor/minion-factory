# Memory Capability

Your context window is working memory. It dies with you. The filesystem is long-term memory. It survives.

## Three Layers

```
.work/intel/indexes/
├── {you}.json           # personal — your mid-task state, your findings
├── _role/
│   └── {your-class}.json  # role — shared across all agents of your class
└── _crew.json           # crew — project-wide knowledge, everyone reads
```

**On wake, read all three:** personal → role → crew. Most specific wins on conflicts.

**When writing, pick the right layer:**
- Personal: mid-task progress, partial investigations, your working state
- Role: gotchas any agent of your class would hit, patterns, reusable techniques
- Crew: architecture decisions, project conventions, cross-role findings

## Schema

Same schema for all three layers:

```json
{
  "entries": {
    "<key>": {
      "files": ["path/to/finding.md"],
      "status": "complete|partial|stale",
      "updated_at": "ISO timestamp",
      "summary": "one-line description"
    }
  }
}
```

Keys are whatever makes sense: zone names, file paths, query strings, build targets.

## On Wake

1. Read `.work/intel/indexes/_crew.json` — project-wide knowledge
2. Read `.work/intel/indexes/_role/{your-class}.json` — role knowledge
3. Read `.work/intel/indexes/{you}.json` — your personal state
4. Read your assigned task
5. Check: do your indexes already cover what the task needs?
   - Yes → read the referenced files, answer from disk
   - Partial → fill gaps, update index
   - No → investigate from scratch, write findings, update index

## During Work

Every time you produce a finding, decision, or result:
1. Write it to `.work/intel/<topic>/` or `.work/results/`
2. Update the appropriate index layer: personal for your state, role for class-relevant knowledge, crew for project-wide facts
3. Do not accumulate findings only in context — flush to disk as you go

## Before Death

If you detect low HP or context pressure, prioritize writing your indexes. Unwritten knowledge dies with you. Written knowledge is inherited by your next session — or by the next agent of your class.

## Lookup

When asked "do you know about X?":
1. Check all three indexes for matching key
2. If found and `status: complete` → read the file, answer
3. If found and `status: partial` → read what's there, note gaps
4. If not found → say so, investigate if tasked

## Rules

- Never re-investigate what's already on disk with `status: complete`
- Mark entries `stale` if the underlying code has changed since `updated_at`
- The index is append-friendly — add entries, don't rewrite the whole file
- Keep summaries to one line — the index should fit in a single read
- Role and crew indexes are shared — don't overwrite other agents' entries, only add or update your own
