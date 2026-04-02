# Agent-Decides Generation: Scope & Estimate

> Status: Draft — needs implementation

## Current Flow (Button-Gated)

```
Frontend "Generate Trip Plan" button
  → generate_plan=True
  → POST /chat
  → run_agent_structured()
      Phase 1: tool loop (no schema) → gather flights, hotels, weather, attractions
      Phase 2: separate generate_content() with response_json_schema=TripItinerary
  → TripItinerary
```

**Key files:**

| File                                        | Role                                                                                               |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `frontend/src/components/chat/InputBar.tsx` | Button + `travelSettings` gating via `canGeneratePlan()`                                           |
| `frontend/src/hooks/useChat.ts`             | `generatePlan` branching: streaming (false) vs sync (true)                                         |
| `frontend/src/services/api.ts`              | `generate_plan` in `ChatRequest`                                                                   |
| `backend/app/api/routes/chat.py`            | `generate_plan` gate; rejects streaming with 400                                                   |
| `backend/app/schemas/chat.py`               | `generate_plan: bool`; `trip_parameters` required when true                                        |
| `backend/app/services/chat_service.py`      | `invoke_agent(generate_plan)` branches to `run_agent()` or `run_agent_structured()`                |
| `backend/app/services/streaming_service.py` | `stream_agent_response()` — SSE streaming with its own tool loop (separate from agent.py)          |
| `backend/app/agent/agent.py`                | `run_agent()` (chat, GEMINI_LITE_MODEL) vs `run_agent_structured()` (trip, GEMINI_MODEL + 2-phase) |

**Critical structural note:** There are **three** agent implementations, not two:

1. `streaming_service.stream_agent_response()` — SSE, uses GEMINI_LITE_MODEL, executes tools DURING stream
2. `agent.run_agent()` — sync, uses GEMINI_LITE_MODEL, plain chat
3. `agent.run_agent_structured()` — sync, uses GEMINI_MODEL, two-phase (gather → structured output)

---

## Target Flow (Agent-Directs)

**Single unified streaming loop** — replaces all three existing paths:

```
User message (any text)
  → POST /chat/stream
  → Unified streaming loop (streaming_service.py)
      ├── Agent calls tools (get_weather, search_flights, search_hotels, ...)
      ├── Tool results streamed back to user in real-time
      ├── Agent asks clarifying questions → streamed as text chunks
      │
      ├── When user says "generate the plan" or agent asks "shall I generate the plan?"
      │     → Agent calls finalize_trip_plan (registered as a Gemini tool with its name)
      │     → Streaming loop detects it by name match, calls it as a local Python function
      │     → finalize_trip_plan: makes ONE generate_content() call with schema,
      │          reuses all accumulated tool results from the information gathering phase
      │     → Returns { itinerary: TripItinerary }
      │     → SSE emits: { "message_type": "finalizing" }
      │     → SSE emits: { "message_type": "itinerary", "itinerary": { ...TripItinerary } }
      │     → Stream done
      │
      └── done
```

**All messages always saved to DB** — `saved_to_trips` flag determines Trip page visibility.

---

## Files to Change (~9 files)

| File                                        | Change                                                                                                                                                                                        | Complexity | Owner |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----- |
| `backend/app/services/streaming_service.py` | **PRIMARY CHANGE** — Replace current streaming loop with unified loop; implement `finalize_trip_plan` as local function; detect by name match → execute → emit `message_type=itinerary` event | **HIGH**   | David |
| `backend/app/agent/agent.py`                | Remove `run_agent()` and `run_agent_structured()` (dead code); no new code needed in this file for the new feature                                                                            | Low        | David |
| `backend/app/services/chat_service.py`      | Remove `generate_plan` param; always call unified streaming loop (or remove entirely if streaming_service handles everything)                                                                 | Medium     | David |
| `backend/app/api/routes/chat.py`            | Streaming becomes the only chat path; remove `/chat/stream` gate; the non-streaming `/chat` endpoint can be removed or kept for simple cases                                                  | Low        | David |
| `backend/app/schemas/chat.py`               | Remove `generate_plan`; `trip_parameters` stays optional; add `message_type: Literal["chat", "finalizing", "itinerary", "error"]` to SSE events                                               | Low        | David |
| `frontend/src/components/chat/InputBar.tsx` | Delete "Generate Trip Plan" button; remove `travelSettings` gating; all input goes through single send path                                                                                   | Low        | Xuan  |
| `frontend/src/hooks/useChat.ts`             | Remove `generatePlan` branching; handle new `message_type` SSE events (`finalizing`, `itinerary`); route itinerary events to `onItinerary`                                                    | Medium     | Xuan  |
| `frontend/src/services/api.ts`              | Remove `generate_plan` from `ChatRequest`; add `message_type` event parsing in `streamMessage()`                                                                                              | Low        | Xuan  |
| `frontend/src/types/trip.ts`                | `canGeneratePlan()` no longer needed (UI gating removed)                                                                                                                                      | Low        | Xuan  |

## Not Affected

- Tool files (`backend/app/agent/tools/`) — unchanged, still called by name
- `trip_repo.py`, `trip_service.py` — unchanged (save_trip called from frontend, not backend)
- Most frontend components — unchanged

**Note:** `message_service.py` and the messages model ARE affected — `append_message` / `update_message_content` will write the new `message_type` field, and the DB schema needs a migration.

---

## Key Design Decisions

### 1. `finalize_trip_plan` is a local Python function — not a registered Gemini tool

**Context threading problem:** In Gemini's tool-calling model, tools are registered with a fixed JSON schema signature. The accumulated `messages` list lives in the streaming loop's local scope — it cannot be serialized and passed as a tool argument.

**Solution — Option A (adopted):** `finalize_trip_plan` is a **local Python function** in `streaming_service.py`. It IS declared as a Gemini tool schema (name + description + parameters) in `generate_content_config.tools` alongside `ALL_TOOLS`, so the model knows it exists and will emit a `finalize_trip_plan` function call. However, the streaming loop **intercepts** the execution — when `fc.name == "finalize_trip_plan"` is detected, the loop calls `finalize_trip_plan` as a local Python function and never looks it up in `TOOL_MAP`.

```
Tool declaration:  finalize_trip_plan_schema declared in tools= config
                  → Gemini sees it and can call it
Tool execution:   streaming loop intercepts by name match,
                  calls finalize_trip_plan(...) locally — not via TOOL_MAP
```

What `finalize_trip_plan` does:

1. Receives trip parameters from the model's function call args
2. Reads the accumulated `messages` list (information gathering tool results — naturally in scope)
3. Makes **exactly ONE `generate_content()` call** with `response_json_schema=TripItinerary`
4. Returns `{ itinerary: TripItinerary }`

It does **NOT** call any external APIs — all trip data (flights, hotels, weather, etc.) was already gathered during the information gathering phase and lives in the `messages` list.

**The key distinction from current architecture:** `run_agent_structured` does information gathering then a **completely separate** Phase 2 `generate_content()` that re-passes ALL data and asks the model to re-generate everything from scratch. `finalize_trip_plan` uses the already-accumulated `messages` list in a single call — no redundant data-fetching. The improvement is no redundant data-passing, not zero LLM calls (it still makes one schema-constrained call).

### 2. SSE `message_type` protocol

SSE events carry a `message_type` field so the frontend knows what to render:

| `message_type`   | SSE payload                                                          | Frontend action                                      |
| ---------------- | -------------------------------------------------------------------- | ---------------------------------------------------- |
| `chat` (default) | `{ chunk: string }`                                                  | Append text to assistant message (existing behavior) |
| `finalizing`     | `{ "message_type": "finalizing", "status": "generating_trip_plan" }` | Show "Generating your trip plan..." indicator        |
| `itinerary`      | `{ "message_type": "itinerary", "itinerary": TripItinerary }`        | Render trip card; call `onItinerary`                 |
| `error`          | `{ "message_type": "error", "error": string }`                       | Show error message                                   |

The `itinerary` event carries **only** the structured data — no `text` field. The frontend renders the card from the `itinerary` data alone, avoiding duplicate text rendering.

### 3. All conversations saved to DB, but only explicitly saved trips appear in Trip page

Current: Only `generate_plan=True` responses are saved via `trip_service.save_trip()` in `invoke_agent()`.

New: **Every** LLM output is saved to the `messages` table via `append_message()` / `update_message_content()` in `streaming_service.py`. The `trips` table is only written when the user explicitly clicks "Save to My Trips" in the frontend.

```
Message flow in unified loop:
1. User message → append_message(role=user, content=message)
2. Assistant text chunks → update_message_content() incrementally (existing behavior)
3. finalize_trip_plan result → update_message_content() with itinerary JSON
4. Stream done
```

**Schema change — add `message_type` column to `messages` table:**

```python
# In the messages model, add:
message_type: str | None = Field(default=None)  # "chat" | "itinerary" | None
```

Alembic migration:

```bash
alembic revision --autogenerate -m "add message_type to messages"
```

When an itinerary is stored, the `content` field uses a JSON wrapper:

```python
content = json.dumps({"__type": "itinerary", "data": itinerary.model_dump(mode="json")})
message_type = "itinerary"
```

This is unambiguous — no prefix-collision risk, and the `message_type` column provides a clean query filter for reloading past trips.

### 4. Trip parameters validation moves to the agent

Currently `canGeneratePlan(travelSettings)` gates the button in the UI (destination + start_date + end_date required). After migration:

- No UI gating — user can type anything
- Agent's system prompt (rule #7) already says: "If the user does NOT mention when the trip is, you MUST ask them for the trip dates before proceeding"
- If user says "plan a trip to Tokyo", agent asks for dates/purpose/group — no `finalize_trip_plan` until all required info collected

### 5. System prompt changes

Simplified prompt — avoid "two-mode" framing which can cause the model to over-index on mode-switching rather than natural conversation:

```
You are a travel planning assistant. Your goal is to help users plan trips.

During the conversation:
- Use get_weather, search_flights, search_hotels, get_attraction, get_transport
  to answer specific questions or gather trip information.
- If any required trip information is missing (destination, dates, purpose,
  group details), ask the user for it before proceeding.

**Before calling finalize_trip_plan, ensure you have called ALL of:**
  1. search_flights (at least once)
  2. search_hotels (at least once)
  3. get_weather (at least once)
  4. get_attraction (at least once)

**If any of these have not been called, call them first, then call finalize_trip_plan.**
**Do NOT summarize the trip in text. Always use finalize_trip_plan to produce the final plan.**

TRIGGER finalize_trip_plan when:
- User says "generate the plan", "create the itinerary", "plan my trip", etc.
- OR you asked "shall I generate the plan now?" and user confirmed "yes"

Do NOT trigger on "save to my trips" — that is a separate UI action for persisting a plan that already exists.

IMPORTANT:
- finalize_trip_plan does NOT call external APIs — it formats data already gathered.
- Do NOT call finalize_trip_plan with incomplete or invented parameters.
- Never invent dates, destinations, or prices.
```

---

## Implementation Details

### `finalize_trip_plan` function (in `streaming_service.py`)

`finalize_trip_plan` is a **local async Python function** — NOT registered as a Gemini tool. The streaming loop calls it directly when detected. The `messages` list is in natural loop scope.

```python
async def finalize_trip_plan(
    destination: str,
    start_date: str,
    end_date: str,
    purpose: str,
    group_type: str,
    group_size: int,
    preferences: dict | None = None,
    messages: list[types.Content],  # In scope from the streaming loop
) -> dict:
    """
    Produces a structured TripItinerary from all information already gathered
    in the conversation. Does NOT call external APIs — all trip data was
    already fetched by the agent during the information gathering phase.

    Makes exactly ONE generate_content() call with response_json_schema=TripItinerary.
    The 'messages' parameter is the accumulated conversation state from the streaming loop.
    """
    # ── Validation guard: required trip parameters ──────────────────────────────
    if not all([destination, start_date, end_date, purpose, group_type]):
        return {
            "error": "Missing required trip parameters. "
                     "Required: destination, start_date, end_date, purpose, group_type. "
                     "Ask the user for any missing information."
        }

    # ── Validation guard: required tool results in context ─────────────────────
    # Bug 3 fix: Gemini SDK uses role="function" for tool responses, not "tool"
    # Defensive: check hasattr first since FunctionResponse shape varies by SDK version
    has_flights = any(
        getattr(part.function_response, "name", None) == "search_flights"
        for m in messages
        if m.role == "function"
        for part in m.parts
        if hasattr(part, "function_response") and part.function_response
    )
    has_hotels = any(
        getattr(part.function_response, "name", None) == "search_hotels"
        for m in messages
        if m.role == "function"
        for part in m.parts
        if hasattr(part, "function_response") and part.function_response
    )
    if not (has_flights and has_hotels):
        return {
            "error": "Not enough trip data gathered yet. "
                     "Please call search_flights and search_hotels before generating the plan."
        }

    # ── Build focused prompt using accumulated conversation context ─────────────
    context_prompt = (
        "Based on all the information gathered in this conversation, "
        "produce a complete trip itinerary as a TripItinerary JSON object.\n\n"
        f"Trip parameters:\n"
        f"  Destination: {destination}\n"
        f"  Dates: {start_date} to {end_date}\n"
        f"  Purpose: {purpose}\n"
        f"  Group: {group_type} ({group_size} people)\n\n"
        "All necessary data (flights, hotels, attractions, weather, transport) "
        "was already fetched by the agent and is available in the conversation history below. "
        "Use that data to populate every field of the itinerary."
    )

    # NOTE: finalize_trip_plan is intentionally NOT in ALL_TOOLS.
    # It is intercepted locally by the streaming loop — never dispatched via TOOL_MAP.
    # It uses client.aio (the async sub-client) for non-blocking LLM access.
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=TripItinerary.model_json_schema(),
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
    )

    response = await client.aio.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=messages + [types.Content(role="user", parts=[types.Part.from_text(context_prompt)])],
        config=config,
    )

    text = response.text or ""
    itinerary = TripItinerary.model_validate_json(text)
    return {"itinerary": itinerary.model_dump(mode="json")}
```

**Note on `messages`:** `messages` is passed as a parameter to `finalize_trip_plan`. At the call site in the streaming loop, the loop's local `messages` variable is passed directly: `result = await finalize_trip_plan(..., messages=messages)`. No closure hack needed — the loop scope is clean.

### Unified streaming loop flow (streaming_service.py)

**Important: `finalize_trip_plan` is detected AFTER the stream is fully drained** — not mid-stream. Gemini streams function calls across multiple chunks; the full argument payload arrives only when the stream completes.

```python
import asyncio

async def stream_agent_response(...):
    # Setup: client, system_instruction, messages[], MAX_TOOL_ROUNDS=20
    # Create assistant message in DB: append_message(role=assistant, content="")
    # accumulated_text grows across all rounds of this assistant turn (intentional — same as existing behavior)
    accumulated_text = ""

    # ── Declare finalize_trip_plan as a Gemini tool so the model knows it exists ────
    # NOTE: finalize_trip_plan is intentionally NOT in ALL_TOOLS.
    # It is intercepted locally by the streaming loop by name match — never dispatched via TOOL_MAP.
    # If someone later adds it to ALL_TOOLS by mistake, Gemini will see it declared twice
    # and may error or behave unexpectedly.
    finalize_trip_plan_decl = types.FunctionDeclaration(
        name="finalize_trip_plan",
        description=(
            "Call this when you have all required trip information (destination, dates, purpose, "
            "group details) and the user wants a complete trip itinerary. "
            "Before calling this function, ensure you have called ALL of: "
            "search_flights, search_hotels, get_weather, get_attraction (at least once each). "
            "Do NOT call this with incomplete or invented parameters."
        ),
        parameters=types.Schema(
            type="object",
            properties={
                "destination":  types.Schema(type="STRING"),
                "start_date":   types.Schema(type="STRING"),
                "end_date":     types.Schema(type="STRING"),
                "purpose":      types.Schema(type="STRING"),
                "group_type":   types.Schema(type="STRING"),
                "group_size":   types.Schema(type="INTEGER"),
            },
            required=["destination", "start_date", "end_date", "purpose", "group_type", "group_size"],
        ),
    )

    try:
        async with asyncio.timeout(120):  # 2-minute wall-clock cap for entire stream
            while tool_round < MAX_TOOL_ROUNDS:
            # ── Step 1: Stream — drain generate_content_stream completely ─────────────────
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[*ALL_TOOLS, finalize_trip_plan_decl],  # NOTE: finalize_trip_plan NOT in ALL_TOOLS — intercepted locally
                thinking_config=types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.MINIMAL,
                    include_thoughts=False,
                ),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            )

            # Bug 1 fix: use client.aio for true async iteration — allows await inside the loop
            stream = client.aio.models.generate_content_stream(
                model=model,
                contents=messages,
                config=config,
            )

            round_text_parts = []
            round_func_parts = []

            # Bug 2 fix: drain the full stream first before extracting function calls.
            # Gemini can emit function calls split across chunks; the final chunk or the
            # response object aggregates them once the stream is complete.
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)
                if chunk.text:
                    round_text_parts.append(chunk.text)
                    accumulated_text += chunk.text
                    yield SSE({"chunk": chunk.text})

            # Now extract consolidated function calls from the drained chunks.
            # Gemini SDK aggregates function calls on the final response object.
            for chunk in chunks:
                if chunk.function_calls:
                    for fc in chunk.function_calls:
                        # Bug 6 fix: don't emit tool_call SSE for finalize_trip_plan
                        if fc.name != "finalize_trip_plan":
                            yield SSE({"tool_call": fc.name, "args": fc.args})
                        round_func_parts.append(fc)

            # Issue 1 fix: explicit exit for text-only rounds (no function calls).
            # Write DB first, then decide whether to continue or exit.
            # Bug 7 fix: write to DB once per round, not per chunk
            update_message_content(msg_id, accumulated_text)

            if not round_func_parts:
                if not round_text_parts:
                    # Empty response — safety filter, network hiccup, etc.
                    yield SSE({"message_type": "error", "error": "Empty response from model."})
                    yield SSE({"done": True})
                    return
                # Pure text response — agent turn complete, stream ends cleanly.
                yield SSE({"done": True})
                return

            # ── Step 2: Detect — check for finalize_trip_plan AFTER draining ────────────
            finalize_fc = next((fc for fc in round_func_parts
                                 if fc.name == "finalize_trip_plan"), None)

            if finalize_fc:
                # Bug 4 fix: append model's finalize_trip_plan turn to messages FIRST
                model_parts = []
                for t in round_text_parts:
                    model_parts.append(types.Part.from_text(text=t))
                for fc in round_func_parts:
                    model_parts.append(types.Part(function_call=fc))
                if model_parts:
                    messages.append(types.Content(role="model", parts=model_parts))

                # Now call finalize_trip_plan with complete messages context
                result = await finalize_trip_plan(
                    **finalize_fc.args,
                    messages=messages,
                )

                if "error" in result:
                    # Feed back to agent as a function response — let it recover
                    messages.append(types.Content(
                        role="function",
                        parts=[types.Part.from_function_response(
                            name="finalize_trip_plan",
                            response={"error": result["error"]},
                        )],
                    ))
                    tool_round += 1
                    continue  # Back to top of while loop — agent sees the error and retries

                yield SSE({"message_type": "finalizing",
                           "status": "generating_trip_plan"})

                yield SSE({"message_type": "itinerary",
                           "itinerary": result["itinerary"]})

                # Store itinerary in DB — JSON wrapper + message_type column
                update_message_content(msg_id, json.dumps({
                    "__type": "itinerary",
                    "data": result["itinerary"]
                }), message_type="itinerary")

                yield SSE({"done": True})
                return  # Stream complete

            # ── Step 3: Execute — run regular tools (not finalize_trip_plan) ───────────
            # Bug 2 fix: append model turn BEFORE tool results (correct turn order)
            model_parts = []
            for t in round_text_parts:
                model_parts.append(types.Part.from_text(text=t))
            for fc in round_func_parts:
                model_parts.append(types.Part(function_call=fc))
            if model_parts:
                messages.append(types.Content(role="model", parts=model_parts))

            for fc in round_func_parts:
                if fc.name == "finalize_trip_plan":
                    continue  # Already handled in Step 2
                result = await TOOL_MAP[fc.name](**fc.args)
                yield SSE({"tool_result": fc.name, "result": result})
                # Bug 3 fix: role is "function", not "tool"
                messages.append(types.Content(
                    role="function",
                    parts=[types.Part.from_function_response(
                        name=fc.name,
                        response=result,
                    )],
                ))

            tool_round += 1

        yield SSE({"error": "Max tool rounds reached — please try a more specific request."})
        yield SSE({"done": True})

    except asyncio.TimeoutError:
        # TimeoutError kills the stream silently without done:true — explicitly yield error first
        yield SSE({"message_type": "error", "error": "Request timed out. Please try again."})
        yield SSE({"done": True})
```

```

**Key implementation notes:**

- `MAX_TOOL_ROUNDS = 20` (raised from 5) — complex trips need more rounds
- **Wall-clock timeout** (`asyncio.timeout(120)`) — hard 2-minute cap prevents demo hang; wrapped in try/except to yield `error` + `done: true` on timeout
- **Step 1**: Stream is fully drained before any detection or execution
- `finalize_trip_plan` is **declared** in `generate_content_config.tools` alongside `ALL_TOOLS` — the model knows it exists and will call it; the streaming loop **intercepts** the call and executes it locally (never reaches `TOOL_MAP`)
- **Guard error recovery**: if `finalize_trip_plan` returns an error (missing params or missing tool results), the error is fed back to the agent as a `function_response` and the loop continues — the agent can retry with correct context
- No duplicate text: `itinerary` event has no `text` field
- **No message truncation** — keeping all messages ensures tool results are always available for `finalize_trip_plan`
- **Correct message order**: model turn is appended to `messages` BEFORE tool results (per Gemini conversation format)
- **`tool_call` SSE** is not emitted for `finalize_trip_plan` mid-stream — prevents spurious frontend indicators
- **DB writes** happen once per round, not per chunk — reduces database load
- **`update_message_content(message_type=...)`** — `message_service.py` must be updated FIRST to add `message_type: str | None = None` parameter before `streaming_service.py` uses it
- **`accumulated_text`** grows across all rounds of a single assistant turn — this is intentional (same as existing `assistant_text` in the current streaming_service.py). The DB message content is the full accumulated assistant response, not per-round.
- **`client.aio`** is used for both the streaming loop (`generate_content_stream`) and `finalize_trip_plan` (`generate_content`) to avoid blocking the event loop — never use the sync `client.models` inside an async function

---

## Migration Steps

### Phase 1: Backend — streaming + `finalize_trip_plan` tool

1. **DB schema migration**: Add `message_type` column to `messages` table (`"chat" | "itinerary | None`); run `alembic revision --autogenerate -m "add message_type to messages"`
2. Add `finalize_trip_plan` as a local Python function in `streaming_service.py` (NOT in `ALL_TOOLS` or Gemini tool registry)
3. Implement `finalize_trip_plan` — one `generate_content()` with schema, no external API calls; includes two guards: (a) required trip parameters, (b) required tool results in context
4. Add `message_type` field to SSE event schema (`chat`, `finalizing`, `itinerary`, `error`)
5. Update `streaming_service.py`:
   - Raise `MAX_TOOL_ROUNDS` from 5 to 20
   - In Step 2 (Detect): match `fc.name == "finalize_trip_plan"`, call it as local function with `messages` in scope
   - On detection: execute tool, emit `finalizing` + `itinerary` events, end stream
   - **No message truncation** — keep all messages
6. Update system prompt with simplified instructions (remove "save my trip" from triggers)
7. Update `chat_service.py` — remove `generate_plan` branch
8. **Remove `run_agent_structured()` and `run_agent()` from `agent.py`** (dead code cleanup — done in same phase)

### Phase 2: Schema + frontend cleanup

1. Remove `generate_plan` from `schemas/chat.py`
2. Remove `generate_plan` from `frontend/src/services/api.ts` `ChatRequest`
3. Remove `generate_plan` from `frontend/src/hooks/useChat.ts` branching
4. Remove "Generate Trip Plan" button from `InputBar.tsx`
5. Remove `canGeneratePlan()` from `frontend/src/types/trip.ts`
6. In `useChat.ts`, handle new `message_type` SSE events (`finalizing`, `itinerary`)
7. In `api.ts` `streamMessage()`, add `message_type` parsing and yielding
8. Route `message_type=itinerary` event to `onItinerary` callback
9. Remove `generate_plan` logging throughout backend

---

## Risk Areas

| Risk                                                                  | Mitigation                                                                                           |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `agent.py` + `streaming_service.py` major重构 — David owns both       | Coordinate with team; no parallel edits to same files                                                |
| `useChat.ts` + streaming changes — Xuan may be working here           | Communicate the SSE `message_type` protocol early; share the SSE event spec                          |
| `finalize_trip_plan` tool may time out for complex trips              | `asyncio.timeout(120)` wrapped in try/except; yields `error` + `done: true` on timeout               |
| Agent doesn't call `finalize_trip_plan` naturally                     | Explicit BEFORE-call checklist in system prompt + ThinkingLevel.MINIMAL; test with various phrasings |
| Guard error causes confusing agent loops                              | Guard errors fed back to agent as function_response, loop continues — agent can recover              |
| Frontend `onItinerary` doesn't fire because stream ended unexpectedly | Ensure `message_type=itinerary` is always emitted before `done: true`                                |
| Single LLM call in `finalize_trip_plan` for day planning may be slow  | Stream `finalizing` status to user while awaiting                                                    |

---

## Test Coverage

### Backend unit tests

- `tests/unit/test_agent.py` — `finalize_trip_plan` tool: mock all sub-tools, verify `TripItinerary` returned with correct schema
- `tests/unit/test_agent.py` — verify `finalize_trip_plan` is added to tool map
- `tests/unit/test_streaming_service.py` — SSE event emission: verify `message_type=finalizing` and `message_type=itinerary` events are emitted when `finalize_trip_plan` is called

### Backend integration tests

- `tests/integration/test_chat_stream.py` — full flow: user → streaming → `finalize_trip_plan` called → `message_type=itinerary` SSE event received with valid TripItinerary
- `tests/integration/test_chat_stream.py` — clarifying questions flow: no `finalize_trip_plan` called until all required params are in conversation
- `tests/integration/test_chat_stream.py` — explicit trigger: user says "generate the plan" → `finalize_trip_plan` called immediately

### Frontend tests

- `useChat.test.ts` — verify `message_type=itinerary` SSE event routes to `onItinerary` callback with correct data
- `useChat.test.ts` — verify `message_type=finalizing` SSE event is handled (shows loading indicator)
- `InputBar.test.tsx` — verify "Generate Trip Plan" button no longer exists in the DOM

---

## Appendix: Architecture Comparison

| Aspect                    | Current (Button-Gated)                                 | Target (Agent-Directs)                                                                                                                                        |
| ------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Entry point               | `/chat` (sync) or `/chat/stream` (SSE)                 | `/chat/stream` only                                                                                                                                           |
| Agent mode                | Set by frontend `generate_plan` flag                   | Agent decides at runtime                                                                                                                                      |
| Structured output trigger | Phase 2 separate `generate_content()` call with schema | `finalize_trip_plan` makes one schema-constrained `generate_content()` using accumulated context                                                              |
| 2nd LLM call              | Yes (Phase 2 with `response_json_schema`)              | Yes, but scoped — one schema-constrained `generate_content()` reusing all Phase 1 tool results (no redundant data-fetching or re-passing of gathered context) |
| Frontend gating           | `canGeneratePlan()` required                           | None                                                                                                                                                          |
| All messages → DB         | No (only `generate_plan=True`)                         | Yes (every response saved to messages table)                                                                                                                  |
| Trip page visibility      | Always shown after generation                          | Only after "Save to My Trips" click                                                                                                                           |
| Streaming                 | Separate path (`/chat/stream`)                         | Unified with all tool calls + `finalize_trip_plan`                                                                                                            |
| Trip parameters collected | Via UI form (travelSettings)                           | By agent asking questions (no UI gating)                                                                                                                      |
```
