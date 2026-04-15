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
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from google.genai import Client, types

from app.core.config import settings

router = APIRouter()


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


@router.websocket("/ws")
async def live_ws(
    ws: WebSocket,
    model: str | None = Query(default=None, alias="model"),
) -> None:
    await ws.accept()

    live_model = model or settings.GEMINI_LIVE_MODEL

    http_opts = (
        types.HttpOptionsDict(client_args={"proxy": settings.SOCKS5_PROXY_URL})
        if settings.LLM_PROXY_ENABLED
        else None
    )
    client = Client(api_key=settings.GEMINI_API_KEY, http_options=http_opts)

    # Transcription events require explicit flags; see Live API "Audio transcriptions".
    config: types.LiveConnectConfigDict = {
        "response_modalities": [types.Modality.AUDIO],
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }

    async with client.aio.live.connect(model=live_model, config=config) as session:

        async def pump_client_to_gemini() -> None:
            try:
                while True:
                    raw = await ws.receive_text()
                    msg = json.loads(raw)
                    mtype = msg.get("type")

                    if mtype == "text":
                        text = str(msg.get("text") or "").strip()
                        if not text:
                            continue
                        # Do not mix send_client_content with send_realtime_input in the
                        # same session (can trigger 1007 invalid argument). Use realtime
                        # input for text as well.
                        await session.send_realtime_input(text=text)
                    elif mtype == "audio":
                        b64 = msg.get("data")
                        mime_type = msg.get("mimeType") or "audio/pcm;rate=16000"
                        if not isinstance(b64, str) or not b64:
                            continue
                        pcm = base64.b64decode(b64)
                        await session.send_realtime_input(
                            audio=types.Blob(data=pcm, mime_type=mime_type)
                        )
                    elif mtype == "audio_stream_end":
                        # Tell the server the client stopped sending audio.
                        await session.send_realtime_input(audio_stream_end=True)
                    elif mtype == "ping":
                        await ws.send_text(_ws_json({"type": "pong"}))
                    else:
                        await ws.send_text(
                            _ws_json(
                                {
                                    "type": "error",
                                    "message": f"Unknown message type: {mtype}",
                                }
                            )
                        )
            except Exception as e:
                # Upstream session may have closed (e.g., keepalive timeout) — notify client.
                try:
                    await ws.send_text(
                        _ws_json(
                            {"type": "error", "message": f"Live upstream error: {e}"}
                        )
                    )
                except Exception:
                    pass
                # Let the outer supervisor cancel both pumps.
                raise

        async def pump_gemini_to_client() -> None:
            # `AsyncSession.receive()` yields until one message has `turn_complete`, then stops.
            # Without an outer loop, we would stop reading after the first model turn (second
            # user message would hang with no forwarded audio/transcript).
            try:
                while True:
                    async for resp in session.receive():
                        content = resp.server_content
                        if content:
                            user_tx = content.input_transcription
                            user_text = user_tx.text if user_tx is not None else None
                            if user_text:
                                await ws.send_text(
                                    _ws_json(
                                        {
                                            "type": "transcript",
                                            "role": "user",
                                            "text": user_text,
                                        }
                                    )
                                )
                            model_tx = content.output_transcription
                            model_text = model_tx.text if model_tx is not None else None
                            if model_text:
                                await ws.send_text(
                                    _ws_json(
                                        {
                                            "type": "transcript",
                                            "role": "model",
                                            "text": model_text,
                                        }
                                    )
                                )

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
                                        await ws.send_text(
                                            _ws_json(
                                                {
                                                    "type": "audio",
                                                    "data": audio_b64,
                                                    "mimeType": getattr(
                                                        inline, "mime_type", None
                                                    )
                                                    or "audio/pcm;rate=24000",
                                                }
                                            )
                                        )

                        if content and getattr(content, "turn_complete", False):
                            await ws.send_text(_ws_json({"type": "turn_complete"}))
            except Exception as e:
                try:
                    await ws.send_text(
                        _ws_json(
                            {"type": "error", "message": f"Live receive error: {e}"}
                        )
                    )
                except Exception:
                    pass
                raise

        pump_tasks = [
            asyncio.create_task(pump_client_to_gemini()),
            asyncio.create_task(pump_gemini_to_client()),
        ]

        try:
            done, pending = await asyncio.wait(
                pump_tasks, return_when=asyncio.FIRST_EXCEPTION
            )
            for task in done:
                exc = task.exception()
                if exc:
                    raise exc
        except WebSocketDisconnect:
            return
        finally:
            for task in pump_tasks:
                task.cancel()
            await asyncio.gather(*pump_tasks, return_exceptions=True)
