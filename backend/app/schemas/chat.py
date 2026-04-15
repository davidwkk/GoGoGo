from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPreference


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    session_id: str | None = Field(
        default=None,
        description="None on first message; UUID anonymous token or logged-in session",
    )
    force_new_session: bool = Field(
        default=False,
        description="If true, backend will create a new session even when an active one exists",
    )
    user_preferences: UserPreference = Field(default_factory=UserPreference)
    llm_model: str | None = Field(
        default=None,
        description="Gemini model to use for streaming. Defaults to GEMINI_LITE_MODEL setting.",
    )
