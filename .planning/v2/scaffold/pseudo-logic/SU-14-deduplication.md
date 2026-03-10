# SU-14 Pseudo-Logic: Code Deduplication

## Duplication 1: _append_error_log

### NEW: src/minion/providers/_shared_error_log.py
```python
"""Shared error logging for provider modules.
Purpose: Single implementation of error log appending, used by codex.py and gemini.py.
"""

def append_error_log(log_dir: str, error_type: str, details: dict) -> None:
    """Append error details to JSONL log file.

    # 1. Construct log file path: os.path.join(log_dir, "errors.jsonl")
    # 2. Build log entry: {"timestamp": iso_now(), "type": error_type, **details}
    # 3. Append as JSON line to file
    # 4. Handle: OSError (log dir missing) — create dir, retry
    # 5. Handle: PermissionError — log warning, don't crash
    """
```

### MODIFY: codex.py, gemini.py
```python
# Replace inline _append_error_log with:
# from minion.providers._shared_error_log import append_error_log
# Delete local _append_error_log function
```

## Duplication 2: Role prompt self-service block

### Step 1: Identify the common block
```
# diff the 7 role prompt .md files:
# diff src/minion/prompts/roles/coder/prompt.md src/minion/prompts/roles/lead/prompt.md
# Identify the identical section (likely polling instructions, set-context, inbox discipline)
```

### Step 2: Extract
```
# The common block is already in _self_service_chore_block.md at the roles/ level
# Verify: is this file used? grep for its name in roles/__init__.py or prompt loaders
# IF already used: verify all 7 role prompts reference it (not inline duplicate)
# IF not used: wire it into the prompt loader to inject into all role prompts
```

### MODIFY: src/minion/prompts/roles/__init__.py
```python
# In the role prompt assembly function:
# 1. Load role-specific prompt.md
# 2. Load _self_service_chore_block.md (shared)
# 3. Concatenate: role_prompt + "\n\n" + self_service_block
# 4. Return combined prompt
```

## Duplication 3: DBMixin pattern

```
# Audit: grep -r "sqlite3.connect\|conn.cursor\|conn.close" src/minion/
# Count instances outside of db/connection.py
# IF >3 instances: extract to use get_db()/connect() from connection.py
# IF already reduced to 2-3: document as "verified complete"
```

## Duplication 4: Provider error classifiers

### NEW: src/minion/providers/_shared_error_classifier.py
```python
"""Shared error classification for provider modules.
Purpose: Single implementation of HTTP error classification.
"""

def classify_error(status_code: int, error_body: str = "") -> str:
    """Classify HTTP error into category.

    # 429 -> "rate_limit"
    # 401, 403 -> "auth"
    # 400, 404, 422 -> "permanent"
    # 500, 502, 503, 504 -> "transient"
    # Other 4xx -> "permanent"
    # Other 5xx -> "transient"
    # Default -> "permanent"
    #
    # Returns one of: "transient", "permanent", "auth", "rate_limit"
    """
```

### MODIFY: codex.py, gemini.py
```python
# Replace inline classification logic with:
# from minion.providers._shared_error_classifier import classify_error
# Provider-specific overrides: if provider has unique codes, extend base classifier
```
