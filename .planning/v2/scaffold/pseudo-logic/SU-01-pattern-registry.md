# SU-01 Pseudo-Logic: Pattern Registry

## Target: `.work/pattern-registry.md`

No code logic — this is a documentation artifact. The "logic" is the research process:

### Assembly Steps
1. For each of 9 sections, grep codebase for current patterns:
   - Error handling: `grep -r "except " src/minion/ | head -20` per module group
   - DB access: `grep -r "get_db\|connect()" src/minion/`
   - Config: `grep -r "os.environ" src/minion/`
   - Logging: `grep -r "getLogger\|log\." src/minion/`
   - Auth: `grep -r "require_class\|require_scope" src/minion/`
   - Messages: read comms/delivery.py and comms/send.py
   - Assertions: `grep -r "^    assert " src/minion/`
   - Documentation: `grep -r "ASSUMPTION\|Time complexity" src/minion/`
   - Provider errors: read providers/codex.py and providers/gemini.py

2. For each section, identify the CANONICAL example (best current implementation)
3. Document: pattern, code example with file reference, rationale, deviation guidance
4. Cross-reference: each section must name which SU depends on it (SU-08, SU-09, SU-10, SU-14)

### Verification
- All 9 sections present
- Each section has at least one `src/minion/` file reference
- No code changes anywhere
