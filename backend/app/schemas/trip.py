from datetime import datetime as DateTime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


# Lightweight schema for the list view (hides the heavy AI JSON)
class TripSummary(BaseModel):
    id: int
    title: str
    destination: str
    created_at: DateTime

    model_config = ConfigDict(from_attributes=True)


# Full schema for the detail view
class TripOut(TripSummary):
    user_id: UUID
    session_id: int | None = None
    itinerary_json: dict[str, Any]  # This holds the generated AI plan
