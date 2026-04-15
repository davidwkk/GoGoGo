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
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from google.genai import Client, types
from loguru import logger

from app.core.config import settings

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


# ── WebSocket endpoint ─────────────────────────────────────────────────────────


@router.websocket("/ws")
async def live_ws(
    ws: WebSocket,
    model: str | None = Query(default=None, alias="model"),
) -> None:
    # ── Resolve model ───────────────────────────────────────────────────────────
    live_model = model or settings.GEMINI_LIVE_MODEL
    user_selected = model is not None and model != settings.GEMINI_LIVE_MODEL
    connection_id = f"live_{id(ws)}"

    logger.bind(
        event="live_connect_start",
        connection_id=connection_id,
        requested_model=model,
        effective_model=live_model,
        default_model=settings.GEMINI_LIVE_MODEL,
        user_selected_model=user_selected,
        proxy_enabled=settings.LLM_PROXY_ENABLED,
        proxy_url=settings.SOCKS5_PROXY_URL if settings.LLM_PROXY_ENABLED else None,
    ).info(
        f"[{connection_id}] Live WS connecting — model={live_model} (user_selected={user_selected})"
    )

    await ws.accept()

    logger.bind(
        event="live_ws_accepted",
        connection_id=connection_id,
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

    logger.bind(
        event="live_session_connecting",
        connection_id=connection_id,
        model=live_model,
        config_response_modalities=["AUDIO"],
        config_input_transcription=True,
        config_output_transcription=True,
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
                model=live_model,
            ).info(f"[{connection_id}] ✅ Gemini Live session connected")

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
                            # Use realtime input for text as well (not send_client_content)
                            await session.send_realtime_input(text=text)
                            stats["text_messages_sent"] += 1
                            logger.bind(
                                event="live_text_sent",
                                connection_id=connection_id,
                                text_preview=text[:80],
                                text_length=len(text),
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
                            ).debug(f"[{connection_id}] → audio stream end sent")

                        elif mtype == "ping":
                            await ws.send_text(_ws_json({"type": "pong"}))
                            logger.bind(
                                event="live_pong_sent",
                                connection_id=connection_id,
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
                                    logger.bind(
                                        event="live_user_transcript",
                                        connection_id=connection_id,
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
                                    logger.bind(
                                        event="live_model_transcript",
                                        connection_id=connection_id,
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
