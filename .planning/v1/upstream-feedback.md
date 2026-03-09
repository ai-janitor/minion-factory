# Upstream Feedback — v1

## Stage 3 (Research) Findings

### UF-001: Network API is not FastAPI (Clean Requirements Impact)
- **Layer wrong:** Clean requirements §2.1 assumed FastAPI
- **What happened:** Research discovered src/minion/network/ uses stdlib http.server
- **Impact:** fast-api skill (24 rules) is mostly N/A for current-state audit. ai-first-api partially applicable.
- **Resolution:** Audit fast-api as aspirational (migration path), not compliance. Note in decomposition.

### UF-002: Skill applicability varies by domain more than expected
- **Layer wrong:** Clean requirements §3 mapped primary skills per domain but research shows some mappings need adjustment
- **Impact:** D7 (Network API) should drop fast-api as primary, use ai-first-api + cs-foundations only. D10 (Prompts) is mostly .md files — implementation-coding-core headers don't apply to markdown.
- **Resolution:** Refine domain-to-skill mapping at decomposition stage.
