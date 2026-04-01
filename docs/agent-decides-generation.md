# Agent-Decides Generation: Scope & Estimate

## Current Flow (Button-Gated)

Frontend "Generate Trip Plan" button → `generate_plan=True` → `POST /chat` → `run_agent_structured()` (Phase 1: tool loop → Phase 2: structured output) → `TripItinerary`

**Key files:**

- `frontend/src/components/chat/InputBar.tsx` — button, `travelSettings` gated state
- `frontend/src/hooks/useChat.ts` — `generatePlan` branching (streaming vs sync)
- `frontend/src/services/api.ts` — `generate_plan` in `ChatRequest`
- `backend/app/api/routes/chat.py` — `generate_plan` gate, rejects streaming
- `backend/app/schemas/chat.py` — `generate_plan: bool`, `trip_parameters` required when true
- `backend/app/services/chat_service.py` — `invoke_agent(generate_plan)` branch
- `backend/app/agent/agent.py` — `run_agent()` (plain) vs `run_agent_structured()` (two-phase)

## Target Flow (Agent-Directs)

User sends message → agent gathers tools → agent autonomously calls `finalize_trip_plan` internal tool or emits a signal → loop intercepts → Phase 2 structured output → `TripItinerary`

No button, no `generate_plan` flag, no frontend gating.

## Files to Change (~8 files)

| File                                        | Change                                                                                                                                       | Complexity |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| `backend/app/agent/agent.py`                | Add `finalize_trip_plan` internal tool; merge `run_agent()` + `run_agent_structured()` into one loop; detect the tool call → trigger Phase 2 | High       |
| `backend/app/services/chat_service.py`      | Remove `generate_plan` param; always call unified loop                                                                                       | Medium     |
| `backend/app/api/routes/chat.py`            | Remove `generate_plan` gate; remove streaming rejection                                                                                      | Low        |
| `backend/app/schemas/chat.py`               | Remove `generate_plan`; `trip_parameters` stays optional                                                                                     | Low        |
| `frontend/src/components/chat/InputBar.tsx` | Delete "Generate Trip Plan" button; remove `travelSettings` gating state                                                                     | Low        |
| `frontend/src/hooks/useChat.ts`             | Remove `generatePlan` branching; streamline `sendMessage`                                                                                    | Low        |
| `frontend/src/services/api.ts`              | Remove `generate_plan` from `ChatRequest`                                                                                                    | Low        |
| `frontend/src/types/trip.ts`                | `canGeneratePlan()` no longer needed                                                                                                         | Low        |

## Not Affected

All tool files, `trip_repo.py`, `trip_service.py`, `message_service.py`, most frontend components.

## Risk Areas

- **`agent.py`** — highest重构; David owns this; no others should touch it simultaneously
- **`useChat.ts`** — Xuan may be preparing streaming UI here; coordinate to avoid conflicts

## Implementation Details

Add `finalize_trip_plan` as a no-op internal tool. Agent calls it when ready → loop detects it → runs Phase 2 with `response_json_schema=TripItinerary`.

```
Pros: Clean, explicit, easy to detect
Cons: Agent must be prompted to call it at the right moment
```

## Migration Steps

1. Add `finalize_trip_plan` internal tool to agent (no-op, just a signal)
2. Update system prompt to instruct agent to call `finalize_trip_plan` when user wants a trip plan
3. Merge the two loops in `agent.py` — single loop handles both cases
4. Remove `generate_plan` from `chat_service.py` and schema
5. Clean up frontend: remove button, simplify `useChat.ts`, update API types
