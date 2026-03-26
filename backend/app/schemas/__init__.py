from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    TripParameters,
)
from app.schemas.enums import (
    DietaryRestriction,
    FlightDirection,
    GroupType,
    HotelTier,
    MaxStops,
    TravelStyle,
    TripPurpose,
)
from app.schemas.itinerary import (
    Activity,
    DayPlan,
    FlightInfo,
    FlightStop,
    HotelInfo,
    TripItinerary,
)
from app.schemas.user import UserCreate, UserPreference, UserResponse, UserUpdate

__all__ = [
    # Auth
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    # Enums
    "DietaryRestriction",
    "FlightDirection",
    "GroupType",
    "HotelTier",
    "MaxStops",
    "TravelStyle",
    "TripPurpose",
    # User
    "UserCreate",
    "UserPreference",
    "UserResponse",
    "UserUpdate",
    # Itinerary
    "Activity",
    "DayPlan",
    "FlightInfo",
    "FlightStop",
    "HotelInfo",
    "TripItinerary",
    # Chat
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "TripParameters",
]
