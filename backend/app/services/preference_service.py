"""Preference extraction service — Gemini 3.1 Flash-Lite extracts preferences from chat history.

Triggered by POST /chat/sessions/{id}/end — user explicitly ends session, requests trip plan.

Extracts structured preferences from conversation and saves via preference_repo.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.preference_repo import upsert_preferences
from app.schemas.user import UserPreference

SYSTEM_PROMPT = (
    "You are a preference extraction assistant. Analyze the conversation and extract "
    "the user's travel preferences. Return ONLY a JSON object with these fields:\n"
    "  travel_style: one of adventure | relaxing | cultural | foodie | nature | shopping\n"
    "  dietary_restriction: one of none | vegetarian | vegan | halal | kosher | gluten_free\n"
    "  hotel_tier: one of budget | mid_range | luxury\n"
    "  budget_min_hkd: number (minimum budget in HKD)\n"
    "  budget_max_hkd: number (maximum budget in HKD)\n"
    "  max_flight_stops: 0 (direct) | 1 (one stop) | 2 (two stops)\n"
    "If no preference was expressed, use sensible defaults."
)


async def extract_and_save_preferences(
    db: Session,
    user_id: int,
    conversation_history: list[dict],
) -> UserPreference:
    """
    Call Gemini 3.1 Flash-Lite with conversation history to extract preferences.
    Save the result via preference_repo.

    conversation_history: list of {"role": "user"|"assistant", "content": "..."}
    """
    from google.genai import Client, types

    client = Client(api_key=settings.GEMINI_API_KEY)

    # Format conversation for the model
    history_text = "\n".join(
        f"{msg['role']}: {msg['content']}" for msg in conversation_history
    )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=UserPreference.model_json_schema(),
    )

    response = client.models.generate_content(
        model=settings.GEMINI_LITE_MODEL,
        contents=history_text,
        config=config,
    )

    try:
        prefs = UserPreference.model_validate_json(response.text)
        prefs_dict = prefs.model_dump()
    except Exception:
        # Fallback to defaults
        prefs_dict = UserPreference.model_dump()

    # Save to DB
    saved = upsert_preferences(db, user_id, prefs_dict)
    return saved
