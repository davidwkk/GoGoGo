from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


# Lightweight schema for the list view (hides the heavy AI JSON)
class TripSummary(BaseModel):
    id: int
    title: str
    destination: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Full schema for the detail view
class TripOut(TripSummary):
    user_id: UUID
    session_id: Optional[int] = None
    itinerary_json: dict | Any  # This holds David's generated AI plan
