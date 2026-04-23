"""Live router — Gemini Live (WebSocket) proxy.

Client connects to this backend WS, backend connects to Gemini Live using the
google-genai SDK. We forward:
- client text + mic PCM chunks -> session.send_realtime_input(...)
- model audio chunks + transcriptions -> client
"""

from __future__ import annotations

import asyncio
import base64
import json
import traceback
import time
from typing import Any, Literal, TypedDict
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from google.genai import Client, types
from loguru import logger

from app.core.config import settings
from app.db.session import get_db
from app.api.deps import get_current_user_optional, verify_user_exists
from app.schemas.chat import ChatRequest
from app.services.message_service import append_message, resolve_session
from app.services.streaming_service import stream_agent_response

router = APIRouter()

# ── Helpers ────────────────────────────────────────────────────────────────────


def _ws_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _b64_data(data: Any) -> str | None:
    """
    Gemini Live inline audio payloads may arrive as base64 strings or raw bytes
    depending on SDK/version. Ensure we always forward base64 *string* to client.
    """
    if data is None:
        return None
    if isinstance(data, str):
        return data
    if isinstance(data, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(data)).decode("ascii")
    return None


# ── In-memory session context (best-effort) ────────────────────────────────────
#
# Gemini Live sessions are not resumable. To keep continuity across reconnects
# within the same "live chat session", we store a lightweight text transcript
# (user/model/system) keyed by `session_id`, and replay it as a compact context
# prompt when a client reconnects.
#
# This is intentionally in-memory (per backend process). Multiple uvicorn/gunicorn
# workers or replicas do NOT share this store — use a single process or add Redis/DB
# for shared session_id context in production.


class _CtxMsg(TypedDict):
    role: Literal["user", "model", "system"]
    text: str
    ts: float


_CTX_TTL_S = 60 * 60  # 1 hour
_CTX_MAX_MESSAGES = 80
_CTX_LOCK = asyncio.Lock()
_CTX_STORE: dict[str, list[_CtxMsg]] = {}


# ── System prompt for Live sessions ─────────────────────────────────────────────
#
# Live mode returns transcripts (often from audio). To keep behavior consistent
# with the Chat page, we inject a compact system instruction into the first user
# turn for each WebSocket connection (and also include any replayed context).
#
# IMPORTANT: Keep instructions focused; longer blocks repeat when context is replayed.
_LIVE_SYSTEM_PROMPT = "\n".join(
    [
        "System: You are GoGoGo, a travel-agent assistant.",
        "System: Your goal is to help plan trips for Hong Kong users.",
        "System: Departure defaults to Hong Kong unless the user specifies otherwise.",
        "System: Transport preference order: Flight first, then High Speed Railway.",
        "System: Match the user's language (e.g. English or 中文) in your reply.",
        "",
        "System: When the user names a destination or says they want to travel, but dates / purpose / group / total budget (HKD) are still missing,",
        "System: respond warmly, acknowledge the destination in the opening line, then ask only for what you still need.",
        "System: CLARIFYING QUESTIONS — use Markdown. Put each missing item on its own line.",
        "System: Use a numbered list OR a bullet list (·). Each item MUST start with the number or bullet, then a space,",
        "System: then a bold label and colon, then the question, e.g. 1. **Dates:** …  or  · **Purpose:** …",
        "System: Put a blank line between the short intro paragraph and the list, and between the list and any closing line if needed.",
        "System: Typical labels (skip any the user already gave): **Dates:**, **Purpose:**, **Group:**, **Budget (HKD):**.",
        "System: Budget is required with the others: ask for total trip budget (min–max HKD) unless the user or Live lines already gave it.",
        "System: If a Live preference budget line exists, still include **Budget (HKD):** but phrase it as confirm or adjust that saved range.",
        "System: Live app preferences: Separate System lines in the same turn may list budget (HKD), travel style, diet,",
        "System: hotel tier, and max flight stops. If the user does not state those in chat, assume the values from those lines.",
        "System: If they state something different in chat, prefer the user's words.",
        "System: Do not ask to repeat **Dates:**, **Purpose:**, **Group:**, **Budget (HKD):**, or other preference items in the clarifying list if already covered by chat or by those Live lines.",
        "System: Example shape (adapt destination and wording; renumber if you skip items):",
        "System:   Opening: I'd love to help you plan your trip to Shanghai!",
        "System:   Blank line, then: To get started, could you share a few more details?",
        "System:   Blank line, then one line per item, for example:",
        "System:   1. **Dates:** What are your travel dates (start and end)?",
        "System:   2. **Purpose:** Is this for vacation, business, or something else?",
        "System:   3. **Group:** How many people are traveling, and what is your relationship (solo, couple, family, friends)?",
        "System:   4. **Budget (HKD):** What is your total budget range for this trip (minimum and maximum HKD)?",
        "System: Do not ask in one long comma-separated sentence; do not omit bold on the labels.",
        "System: You may include useful links (hotels/attractions) and maps when relevant.",
        "System: When the user asks to generate, create, or produce a **full itinerary** or **complete travel plan** with real flights, hotels, or weather,",
        "System: do NOT answer with a large invented ```json``` trip document as if it came from live APIs — this Live channel cannot call those tools.",
        "System: Instead, briefly ask them to send a short line such as **Generate plan** or **Generate itinerary** so the app runs the tool-backed planner and shows the travel card.",
        "System: For small structured snippets (not a full trip replacement), you may still use Markdown or a small fenced ```json``` block when helpful.",
    ]
)


def _live_preference_hint_block(msg: dict) -> str:
    """
    Client may send each Live text turn with the same fields as the Live preference bar:
    budget_min_hkd, budget_max_hkd, travel_style, dietary_restriction, hotel_tier, max_flight_stops.
    Injected as System lines so the model can assume them when the user does not state them in chat.
    """
    out: list[str] = []
    raw_min, raw_max = msg.get("budget_min_hkd"), msg.get("budget_max_hkd")
    if raw_min is not None or raw_max is not None:
        try:
            mn = float(raw_min) if raw_min is not None else None
            mx = float(raw_max) if raw_max is not None else None
        except (TypeError, ValueError):
            mn = mx = None
        if mn is not None and mx is not None and mn >= 0 and mx >= 0 and mn <= mx:
            out.append(
                f"System: Live preference budget (HKD): {int(mn)}–{int(mx)} total. "
                "If the user does not state a budget, use this range; if they state another amount, prefer theirs."
            )
    for key, label in (
        ("travel_style", "travel style"),
        ("dietary_restriction", "diet"),
        ("hotel_tier", "hotel tier"),
    ):
        v = msg.get(key)
        if not isinstance(v, str):
            continue
        s = v.strip()
        if not s or len(s) > 64:
            continue
        out.append(
            f"System: Live preference {label}: {s}. If the user does not specify this, assume this value; "
            "if they contradict it, prefer the user."
        )
    raw_stops = msg.get("max_flight_stops")
    if raw_stops is not None:
        try:
            stops = int(float(raw_stops))
        except (TypeError, ValueError):
            stops = None
        if stops in (0, 1, 2):
            label = {0: "direct flights only", 1: "up to 1 stop", 2: "up to 2 stops"}[stops]
            out.append(
                f"System: Live preference max flight stops: {stops} ({label}). If the user does not specify, assume this; "
                "if they want different routings, prefer the user."
            )
    if not out:
        return ""
    return "\n".join(out) + "\n"


def _ctx_prune(now: float) -> None:
    expired_keys: list[str] = []
    for k, msgs in _CTX_STORE.items():
        if not msgs:
            expired_keys.append(k)
            continue
        if now - msgs[-1]["ts"] > _CTX_TTL_S:
            expired_keys.append(k)
    for k in expired_keys:
        _CTX_STORE.pop(k, None)


def _ctx_compose_prompt(msgs: list[_CtxMsg]) -> str:
    """
    Compose a *minimal* reconnect context.

    We intentionally avoid replaying the full transcript, because Gemini Live
    often responds by recapping it. Instead, we provide only the most recent
    user/model exchanges and instruct the model NOT to recap.
    """
    user_msgs = [m for m in msgs if m["role"] == "user"]
    model_msgs = [m for m in msgs if m["role"] == "model"]

    last_users = user_msgs[-6:] if user_msgs else []
    last_model = model_msgs[-1:] if model_msgs else []

    lines: list[str] = [
        "System: Reconnect context for an ongoing live travel-planning session.",
        "System: CRITICAL: Do NOT recap, summarize, or read aloud the context below unless the user explicitly asks.",
        "System: Continue the same travel-planning thread. Do not re-ask for destination or for details the user",
        "System: already provided in the context; respond to their latest user message in continuation.",
        "",
        "Context (do not repeat):",
    ]
    for m in last_users + last_model:
        role = "User" if m["role"] == "user" else "Assistant"
        t = (m["text"] or "").strip()
        if not t:
            continue
        max_len = 1800 if m["role"] == "model" else 600
        if len(t) > max_len:
            t = t[:max_len] + "…"
        lines.append(f"- {role}: {t}")

    lines.append("")
    lines.append("System: End context.")
    return "\n".join(lines)


async def _ctx_append(
    session_id: str, role: Literal["user", "model", "system"], text: str
) -> None:
    t = (text or "").strip()
    if not session_id or not t:
        return
    now = time.time()
    async with _CTX_LOCK:
        _ctx_prune(now)
        msgs = _CTX_STORE.setdefault(session_id, [])
        if role == "model" and msgs and msgs[-1]["role"] == "model":
            # Coalesce: output_transcription is streamed as many chunks per turn; merge
            # into one message so _ctx_compose can see the full last assistant reply.
            prev = (msgs[-1].get("text") or "").strip()
            p_st, t_st = prev.strip(), t
            if not p_st:
                msgs[-1]["text"] = t_st
            elif t_st.startswith(p_st) and len(t_st) >= len(p_st):
                # Cumulative strings (entire line-so-far each time)
                msgs[-1]["text"] = t_st
            elif p_st in t_st and len(t_st) > len(p_st):
                msgs[-1]["text"] = t_st
            else:
                msgs[-1]["text"] = f"{p_st} {t_st}" if t_st else p_st
            msgs[-1]["ts"] = now
        else:
            msgs.append({"role": role, "text": t, "ts": now})
        if len(msgs) > _CTX_MAX_MESSAGES:
            _CTX_STORE[session_id] = msgs[-_CTX_MAX_MESSAGES:]


async def _ctx_get(session_id: str) -> list[_CtxMsg]:
    if not session_id:
        return []
    now = time.time()
    async with _CTX_LOCK:
        _ctx_prune(now)
        return list(_CTX_STORE.get(session_id, []))


# ── WebSocket endpoint ─────────────────────────────────────────────────────────


@router.websocket("/ws")
async def live_ws(
    ws: WebSocket,
    model: str | None = Query(default=None, alias="model"),
    session_id: str | None = Query(default=None, alias="session_id"),
    voice: str | None = Query(default=None, alias="voice"),
) -> None:
    # ── Resolve model ───────────────────────────────────────────────────────────
    live_model = model or settings.GEMINI_LIVE_MODEL
    user_selected = model is not None and model != settings.GEMINI_LIVE_MODEL
    connection_id = f"live_{id(ws)}"
    sid = (session_id or "").strip() or None
    voice_name = (voice or "").strip() or None

    allowed_voices = {
        "Zephyr",
        "Puck",
        "Charon",
        "Fenrir",
        "Kore",
    }
    if voice_name and voice_name not in allowed_voices:
        logger.bind(
            event="live_invalid_voice",
            connection_id=connection_id,
            session_id=sid,
            requested_voice=voice_name,
        ).warning(f"[{connection_id}] Invalid voice requested: {voice_name}")
        voice_name = None

    logger.bind(
        event="live_connect_start",
        connection_id=connection_id,
        session_id=sid,
        requested_model=model,
        effective_model=live_model,
        default_model=settings.GEMINI_LIVE_MODEL,
        user_selected_model=user_selected,
        requested_voice=voice_name,
        proxy_enabled=settings.LLM_PROXY_ENABLED,
        proxy_url=settings.SOCKS5_PROXY_URL if settings.LLM_PROXY_ENABLED else None,
    ).info(
        f"[{connection_id}] Live WS connecting — model={live_model} (user_selected={user_selected})"
    )

    await ws.accept()

    logger.bind(
        event="live_ws_accepted",
        connection_id=connection_id,
        session_id=sid,
        model=live_model,
    ).info(f"[{connection_id}] WS accepted, connecting to Gemini Live")

    # ── Build client & config ──────────────────────────────────────────────────
    http_opts = (
        types.HttpOptionsDict(client_args={"proxy": settings.SOCKS5_PROXY_URL})
        if settings.LLM_PROXY_ENABLED
        else None
    )
    client = Client(api_key=settings.GEMINI_API_KEY, http_options=http_opts)

    config: types.LiveConnectConfigDict = {
        "response_modalities": [types.Modality.AUDIO],
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }
    if voice_name:
        config["speech_config"] = {
            "voice_config": {
                "prebuilt_voice_config": {"voice_name": voice_name},
            }
        }

    logger.bind(
        event="live_session_connecting",
        connection_id=connection_id,
        session_id=sid,
        model=live_model,
        config_response_modalities=["AUDIO"],
        config_input_transcription=True,
        config_output_transcription=True,
        config_voice=voice_name,
    ).info(f"[{connection_id}] Connecting to Gemini Live session")

    # Track stats for this session
    stats = {
        "text_messages_sent": 0,
        "audio_chunks_sent": 0,
        "user_transcripts_received": 0,
        "model_transcripts_received": 0,
        "audio_chunks_received": 0,
        "turns_completed": 0,
    }

    try:
        async with client.aio.live.connect(model=live_model, config=config) as session:
            logger.bind(
                event="live_session_connected",
                connection_id=connection_id,
                session_id=sid,
                model=live_model,
            ).info(f"[{connection_id}] ✅ Gemini Live session connected")

            # NOTE: Gemini Live sessions are not resumable. We keep an in-memory
            # transcript per session_id and inject it (plus the fixed system prompt)
            # on every user text we forward, so the model never sees a bare user line
            # after a reconnect and preferences always apply.

            # ── pump: client → gemini ─────────────────────────────────────────
            async def pump_client_to_gemini() -> None:
                nonlocal stats
                try:
                    while True:
                        raw = await ws.receive_text()
                        msg = json.loads(raw)
                        mtype = msg.get("type")

                        logger.bind(
                            event="live_ws_client_message",
                            connection_id=connection_id,
                            message_type=mtype,
                            message_keys=list(msg.keys()),
                        ).debug(f"[{connection_id}] ← WS client msg type={mtype}")

                        if mtype == "text":
                            text = str(msg.get("text") or "").strip()
                            if not text:
                                continue
                            pref_hint = _live_preference_hint_block(msg)
                            ph_block = ("\n" + pref_hint) if pref_hint else ""
                            ctx_block = ""
                            ctx_msg_count = 0
                            if sid:
                                prior_ctx = await _ctx_get(sid)
                                ctx_msg_count = len(prior_ctx)
                                if prior_ctx:
                                    ctx_block = "\n" + _ctx_compose_prompt(prior_ctx)
                            send_text = (
                                _LIVE_SYSTEM_PROMPT + ph_block + ctx_block + "\nUser: " + text
                            )
                            if sid and ctx_block:
                                logger.bind(
                                    event="live_context_injected_with_text",
                                    connection_id=connection_id,
                                    session_id=sid,
                                    context_messages=ctx_msg_count,
                                    injected_chars=len(send_text),
                                ).info(
                                    f"[{connection_id}] Injected {ctx_msg_count} context msgs with user text"
                                )
                            if sid:
                                await _ctx_append(sid, "user", text)
                            # Use realtime input for text as well (not send_client_content)
                            await session.send_realtime_input(text=send_text)
                            stats["text_messages_sent"] += 1
                            logger.bind(
                                event="live_text_sent",
                                connection_id=connection_id,
                                session_id=sid,
                                text_preview=text[:80],
                                text_length=len(text),
                                forwarded_length=len(send_text),
                                total_text_sent=stats["text_messages_sent"],
                            ).debug(f"[{connection_id}] → sent text: {text[:60]}")

                        elif mtype == "audio":
                            b64 = msg.get("data")
                            mime_type = msg.get("mimeType") or "audio/pcm;rate=16000"
                            if not isinstance(b64, str) or not b64:
                                continue
                            pcm = base64.b64decode(b64)
                            await session.send_realtime_input(
                                audio=types.Blob(data=pcm, mime_type=mime_type)
                            )
                            stats["audio_chunks_sent"] += 1
                            logger.bind(
                                event="live_audio_sent",
                                connection_id=connection_id,
                                mime_type=mime_type,
                                audio_size_bytes=len(pcm),
                                total_audio_sent=stats["audio_chunks_sent"],
                            ).debug(
                                f"[{connection_id}] → sent audio chunk {stats['audio_chunks_sent']}, "
                                f"size={len(pcm)} bytes, mime={mime_type}"
                            )

                        elif mtype == "audio_stream_end":
                            await session.send_realtime_input(audio_stream_end=True)
                            logger.bind(
                                event="live_audio_stream_end",
                                connection_id=connection_id,
                                session_id=sid,
                            ).debug(f"[{connection_id}] → audio stream end sent")

                        elif mtype == "ping":
                            await ws.send_text(_ws_json({"type": "pong"}))
                            logger.bind(
                                event="live_pong_sent",
                                connection_id=connection_id,
                                session_id=sid,
                            ).debug(f"[{connection_id}] → pong replied")

                        else:
                            logger.bind(
                                event="live_unknown_message_type",
                                connection_id=connection_id,
                                unknown_type=mtype,
                            ).warning(f"[{connection_id}] Unknown WS msg type: {mtype}")
                            await ws.send_text(
                                _ws_json(
                                    {
                                        "type": "error",
                                        "message": f"Unknown message type: {mtype}",
                                    }
                                )
                            )
                except WebSocketDisconnect:
                    logger.bind(
                        event="live_ws_client_disconnected",
                        connection_id=connection_id,
                    ).info(f"[{connection_id}] WS client disconnected")
                    raise
                except Exception as e:
                    logger.bind(
                        event="live_pump_client_error",
                        connection_id=connection_id,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    ).error(f"[{connection_id}] pump_client_to_gemini error: {e}")
                    try:
                        await ws.send_text(
                            _ws_json(
                                {
                                    "type": "error",
                                    "message": f"Live upstream error: {e}",
                                }
                            )
                        )
                    except Exception:
                        pass
                    raise

            # ── pump: gemini → client ─────────────────────────────────────────
            async def pump_gemini_to_client() -> None:
                nonlocal stats
                try:
                    while True:
                        async for resp in session.receive():
                            content = resp.server_content

                            logger.bind(
                                event="live_gemini_response",
                                connection_id=connection_id,
                                has_content=content is not None,
                                turn_complete=getattr(content, "turn_complete", False)
                                if content
                                else None,
                            ).debug(f"[{connection_id}] ← Gemini response received")

                            if content:
                                # User transcription
                                user_tx = content.input_transcription
                                user_text = (
                                    user_tx.text if user_tx is not None else None
                                )
                                if user_text:
                                    stats["user_transcripts_received"] += 1
                                    if sid:
                                        await _ctx_append(sid, "user", user_text)
                                    logger.bind(
                                        event="live_user_transcript",
                                        connection_id=connection_id,
                                        session_id=sid,
                                        transcript_preview=user_text[:80],
                                        total_user_transcripts=stats[
                                            "user_transcripts_received"
                                        ],
                                    ).debug(
                                        f"[{connection_id}] ← user transcript: {user_text[:60]}"
                                    )
                                    await ws.send_text(
                                        _ws_json(
                                            {
                                                "type": "transcript",
                                                "role": "user",
                                                "text": user_text,
                                            }
                                        )
                                    )

                                # Model transcription
                                model_tx = content.output_transcription
                                model_text = (
                                    model_tx.text if model_tx is not None else None
                                )
                                if model_text:
                                    stats["model_transcripts_received"] += 1
                                    if sid:
                                        await _ctx_append(sid, "model", model_text)
                                    logger.bind(
                                        event="live_model_transcript",
                                        connection_id=connection_id,
                                        session_id=sid,
                                        transcript_preview=model_text[:80],
                                        total_model_transcripts=stats[
                                            "model_transcripts_received"
                                        ],
                                    ).debug(
                                        f"[{connection_id}] ← model transcript: {model_text[:60]}"
                                    )
                                    await ws.send_text(
                                        _ws_json(
                                            {
                                                "type": "transcript",
                                                "role": "model",
                                                "text": model_text,
                                            }
                                        )
                                    )

                                # Audio data
                                model_turn = getattr(content, "model_turn", None)
                                parts = (
                                    getattr(model_turn, "parts", None)
                                    if model_turn
                                    else None
                                )
                                if parts:
                                    for part in parts:
                                        inline = getattr(part, "inline_data", None)
                                        if inline and getattr(inline, "data", None):
                                            audio_b64 = _b64_data(
                                                getattr(inline, "data", None)
                                            )
                                            if not audio_b64:
                                                continue
                                            stats["audio_chunks_received"] += 1
                                            mime = (
                                                getattr(inline, "mime_type", None)
                                                or "audio/pcm;rate=24000"
                                            )
                                            logger.bind(
                                                event="live_audio_received",
                                                connection_id=connection_id,
                                                session_id=sid,
                                                mime_type=mime,
                                                audio_size_b64=len(audio_b64),
                                                total_audio_received=stats[
                                                    "audio_chunks_received"
                                                ],
                                            ).debug(
                                                f"[{connection_id}] ← audio chunk {stats['audio_chunks_received']}, "
                                                f"b64_size={len(audio_b64)}, mime={mime}"
                                            )
                                            await ws.send_text(
                                                _ws_json(
                                                    {
                                                        "type": "audio",
                                                        "data": audio_b64,
                                                        "mimeType": mime,
                                                    }
                                                )
                                            )

                            # Turn complete
                            if content and getattr(content, "turn_complete", False):
                                stats["turns_completed"] += 1
                                logger.bind(
                                    event="live_turn_complete",
                                    connection_id=connection_id,
                                    session_id=sid,
                                    turns_completed=stats["turns_completed"],
                                ).info(
                                    f"[{connection_id}] ← turn_complete #{stats['turns_completed']}"
                                )
                                await ws.send_text(_ws_json({"type": "turn_complete"}))

                except Exception as e:
                    logger.bind(
                        event="live_pump_gemini_error",
                        connection_id=connection_id,
                        error_type=type(e).__name__,
                        error_message=str(e),
                        text_messages_sent=stats["text_messages_sent"],
                        audio_chunks_sent=stats["audio_chunks_sent"],
                        user_transcripts=stats["user_transcripts_received"],
                        model_transcripts=stats["model_transcripts_received"],
                        audio_received=stats["audio_chunks_received"],
                        turns_completed=stats["turns_completed"],
                    ).error(f"[{connection_id}] pump_gemini_to_client error: {e}")
                    try:
                        await ws.send_text(
                            _ws_json(
                                {"type": "error", "message": f"Live receive error: {e}"}
                            )
                        )
                    except Exception:
                        pass
                    raise

            # ── Run both pumps ─────────────────────────────────────────────────
            pump_tasks = [
                asyncio.create_task(pump_client_to_gemini()),
                asyncio.create_task(pump_gemini_to_client()),
            ]

            logger.bind(
                event="live_pumps_started",
                connection_id=connection_id,
                model=live_model,
            ).info(f"[{connection_id}] Both pumps started, waiting for finish...")

            try:
                done, _ = await asyncio.wait(
                    pump_tasks, return_when=asyncio.FIRST_EXCEPTION
                )
                for task in done:
                    exc = task.exception()
                    if exc:
                        logger.bind(
                            event="live_task_exception",
                            connection_id=connection_id,
                            exception_type=type(exc).__name__,
                            exception_message=str(exc),
                            close_code=getattr(exc, "args", [None])[0],
                        ).debug(f"[{connection_id}] Task ended with exception: {exc}")
                        raise exc
            except WebSocketDisconnect:
                logger.bind(
                    event="live_ws_disconnected",
                    connection_id=connection_id,
                    text_messages_sent=stats["text_messages_sent"],
                    audio_chunks_sent=stats["audio_chunks_sent"],
                    user_transcripts=stats["user_transcripts_received"],
                    model_transcripts=stats["model_transcripts_received"],
                    audio_received=stats["audio_chunks_received"],
                    turns_completed=stats["turns_completed"],
                ).info(f"[{connection_id}] WS disconnected — session stats: {stats}")
                return
            finally:
                for task in pump_tasks:
                    task.cancel()
                await asyncio.gather(*pump_tasks, return_exceptions=True)

    except Exception as e:
        tb_str = traceback.format_exc()
        logger.bind(
            event="live_session_error",
            connection_id=connection_id,
            error_type=type(e).__name__,
            error_message=str(e),
            traceback=tb_str,
            model=live_model,
            stats=stats,
        ).error(f"[{connection_id}] Live session error: {e}")
        try:
            await ws.send_text(
                _ws_json({"type": "error", "message": f"Live connection error: {e}"})
            )
        except Exception:
            pass
        raise


@router.post("/plan/stream")
async def live_plan_stream(
    body: ChatRequest,
    current_user: dict | None = Depends(get_current_user_optional),
    db=Depends(get_db),
):
    """
    POST /live/plan/stream — tool-enriched travel planning for Live page (SSE).

    Rationale: Gemini Live WS is optimized for audio + transcript, but does not
    execute our tool pipeline. This endpoint reuses the existing chat streaming
    agent loop (tools + TripItinerary schema) and returns SSE events.

    NOTE: auto_save_trip is disabled here. The Live UI saves explicitly via
    POST /trips after the user confirms.
    """
    user_id = current_user["user_id"] if current_user else None
    trace_id = str(uuid4())

    verify_user_exists(user_id, db)

    session = await resolve_session(
        db, body.session_id, user_id, force_new_session=body.force_new_session
    )
    append_message(db, session_id=session.id, role="user", content=body.message)
    prefs_dict = body.user_preferences.model_dump() if body.user_preferences else None

    return StreamingResponse(
        stream_agent_response(
            message=body.message,
            session_id=session.id,
            db=db,
            preferences=prefs_dict,
            trace_id=trace_id,
            user_id=user_id,
            model=body.llm_model,
            auto_save_trip=False,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
