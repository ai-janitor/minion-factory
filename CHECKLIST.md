# Worker Checklist — sec-coder-1 [5/5-0NA]

## Item: No Content-Length limit on request body (#45)
- **Problem:** `_read_body()` in server.py reads arbitrary Content-Length with no upper bound, enabling DoS via huge payloads.
- **Files:** src/minion/network/server.py
- **Approach:** Added MAX_BODY_SIZE constant (1MB). _read_body() checks Content-Length against limit before reading.
- **Verify:** Tests verify oversized payloads get 413, normal payloads still work.
- [x] Implemented
- [x] Tested

## Item: Timing-unsafe token comparison (#46)
- **Problem:** Both server.py _check_token() and auth.py check_token() use == for token comparison, vulnerable to timing attacks.
- **Files:** src/minion/network/server.py, src/minion/network/auth.py, src/minion/network/handlers/compat.py
- **Approach:** Replaced all == comparisons with hmac.compare_digest() in all locations.
- **Verify:** Tests confirm auth works correctly with hmac.compare_digest.
- [x] Implemented
- [x] Tested

## Item: No input validation on /register endpoint (#47)
- **Problem:** /register accepts any JSON payload without validating field types, lengths, or values.
- **Files:** src/minion/network/handlers/core.py
- **Approach:** Added _REGISTER_SCHEMA + _validate_fields() for comprehensive field validation.
- **Verify:** Tests for missing name, long name, invalid class, non-numeric fields, invalid crash_rate.
- [x] Implemented
- [x] Tested

## Item: No input validation on /send and POST endpoints (#48)
- **Problem:** /send and /api/login accept arbitrary payloads without length/type validation.
- **Files:** src/minion/network/handlers/core.py, src/minion/network/handlers/compat.py
- **Approach:** /send: validates from/to/message are strings with length limits. /api/login: validates username/password are strings <= 256 chars.
- **Verify:** Tests for non-string fields, oversized fields, missing required fields.
- [x] Implemented
- [x] Tested

## Item: Server starts without auth token (#31)
- **Problem:** serve() starts happily without a token, leaving the server open to anyone.
- **Files:** src/minion/network/server.py, src/minion/cli/network_cmds.py
- **Approach:** serve() now refuses to start without token unless --no-auth or MINION_NETWORK_NO_AUTH=1.
- **Verify:** Tests verify SystemExit(1) without token, and explicit opt-in allows startup.
- [x] Implemented
- [x] Tested

## Final
- [x] All items implemented
- [x] `uv run pytest` passes
- [x] Changes committed
