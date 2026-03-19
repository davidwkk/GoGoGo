from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import asyncio
import json

from app.api.deps import get_current_user

router = APIRouter()


class ChatStreamRequest(BaseModel):
    message: str
    session_id: int | None = None


async def generate_response(message: str, user_id: int):
    # TODO: Integrate LangChain agent here
    # This is a placeholder that streams back the received message
    response_text = f"You said: {message}. The agent is not yet integrated."
    for chunk in response_text.split():
        await asyncio.sleep(0.05)
        yield {"event": "message", "data": json.dumps({"content": chunk + " "})}
    yield {"event": "done", "data": json.dumps({"session_id": 1})}


@router.post("/stream")
async def chat_stream(
    body: ChatStreamRequest,
    current_user: dict = Depends(get_current_user),
):
    async def event_generator():
        async for event in generate_response(body.message, current_user["user_id"]):
            yield event

    return EventSourceResponse(event_generator())
