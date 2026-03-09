# Cross-Cutting Concerns Survey

## Error Handling — TWO PATTERNS (violation of One Pattern Per Concern)

1. **Dict-return:** {"error": "..."} dicts from business logic, output.py detects "error" key → sys.exit(1). Dominant in CLI/tasks.
2. **Raise stdlib:** ValueError, FileNotFoundError, RuntimeError for config/loader errors. No custom exception classes.
3. **Broad except:** Exception:pass in daemon (intentional resilience, logged), coordinator (heartbeat), create_task (flow echo)

**No domain exception hierarchy.** Zero custom Exception subclasses in entire codebase.

## Logging — THREE PATTERNS (worst concern)

1. **logging.getLogger:** 3 files only (db/migrations.py, db/coordinator.py, intel/_frontmatter.py)
2. **print():** 57 calls across 23 files (server startup, daemon alerts, monitoring, tmux)
3. **click.echo():** 42 calls across 9 files (CLI output, auth)
4. **One structured log line:** server.py log_message() override → JSON with ts/level/component/client

No logging.basicConfig() anywhere. No log level config. No centralized log setup. The 3 getLogger instances write to root logger with no handlers.

## Config — MOSTLY ONE PATTERN

- defaults.py: single source for env var names + path resolvers (14 imports)
- 36 os.environ/os.getenv calls across 20 files — scattered direct reads
- YAML config: crew/config.py (canonical, dataclasses) and daemon/config.py (duplicates parsing logic)
- No .env files, no python-dotenv, no pydantic-settings
- Actual cascade: flags > env vars > hardcoded defaults (no config file layer)

## Auth — TWO TIERS (intentional)

- **CLI/local:** Class-based via MINION_CLASS env + require_class/require_scope decorators
- **Network/HTTP:** Bearer token from MINION_CLUSTER_TOKEN env
- Minor duplication: _check_token in server.py vs check_token in network/auth.py

## Database — ONE PATTERN (cleanest concern)

- get_db() factory → WAL-mode SQLite, Row factory, per-operation connections
- Two DBs: project-local (.work/minion.db), global coordinator (~/.minion/coordinator.db), network (~/.minion/network.db)
- Schema in db/schema.py (14 tables), migrations in db/migrations.py (v1-v13)
- No ORM, no repository layer, inline SQL everywhere

## One Pattern Per Concern Summary

| Concern | Single Pattern? | Severity |
|---|---|---|
| Error handling | NO — dict-return + raise stdlib | Major |
| Logging | NO — 3 patterns, no config | Critical |
| Config | MOSTLY — defaults.py is canonical, but daemon duplicates crew parsing | Minor |
| Auth | YES — two tiers is intentional | Clean |
| Database | YES — consistent get_db() + WAL + inline SQL | Clean |
