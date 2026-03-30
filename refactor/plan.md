# Refactor Plan: `chat.py` Router Split

## Goal

Split the monolithic `chat.py` router into focused, single-responsibility modules.

## Migration Map

| Item                     | From      | To                              | Rename                  |
| ------------------------ | --------- | ------------------------------- | ----------------------- |
| `_sync_stream_to_async`  | `chat.py` | `utils/stream_utils.py`         | —                       |
| `_is_proxy_reachable`    | `chat.py` | `utils/stream_utils.py`         | —                       |
| `_stream_agent_thoughts` | `chat.py` | `services/streaming_service.py` | `stream_agent_response` |
| `_resolve_session`       | `chat.py` | `services/message_service.py`   | `resolve_session`       |
| `tool_map` dict          | `chat.py` | `services/streaming_service.py` | —                       |
| `_verify_user_exists`    | `chat.py` | `api/deps.py`                   | `verify_user_exists`    |

## Steps

### Step 1: Create `app/utils/stream_utils.py`

- [ ] Move `_sync_stream_to_async()`
- [ ] Move `_is_proxy_reachable()`
- [ ] Add docstrings
- [ ] Update imports

### Step 2: Create `app/services/streaming_service.py`

- [ ] Move `tool_map` dict
- [ ] Move `_stream_agent_thoughts` → rename to `stream_agent_response`
- [ ] Update imports to use `stream_utils`
- [ ] Keep all tool execution logic

### Step 3: Update `app/services/message_service.py`

- [ ] Move `_resolve_session` → rename to `resolve_session`
- [ ] Add to exports

### Step 4: Update `app/api/deps.py`

- [ ] Move `_verify_user_exists` → rename to `verify_user_exists`
- [ ] Add to exports

### Step 5: Slim `app/api/routes/chat.py`

- [ ] Remove moved functions
- [ ] Update imports to use new locations
- [ ] Slim route handlers to 10-15 lines each
- [ ] Keep `router`, `test_llm`, `chat_stream`, `chat`

### Step 6: Validate

- [ ] Run pyright type check
- [ ] Run ruff check/format
- [ ] Verify no broken imports
- [ ] Ensure tests pass

## Confidence: 90%

Grey area: `_verify_user_exists` placement — deps.py is cleaner long-term.
