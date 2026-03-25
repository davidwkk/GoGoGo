from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict

# 1. Base properties shared across all trip schemas
class TripBase(BaseModel):
    title: str
    destination: str

# 2. Schema for creating a new trip
class TripCreate(TripBase):
    # We accept the complex JSON output from David's AI agent here
    itinerary_json: dict[str, Any]

# 3. Schema for the Trip List View (Lightweight)
class TripSummary(TripBase):
    id: int
    created_at: datetime
    
    # This config tells Pydantic it's okay to read data directly from our SQLAlchemy models
    model_config = ConfigDict(from_attributes=True)

# 4. Schema for the Full Trip Detail View (Heavy)
class TripOut(TripSummary):
    itinerary_json: dict[str, Any]