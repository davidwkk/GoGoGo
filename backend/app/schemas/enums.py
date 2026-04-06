from enum import Enum
from typing import Literal


class TripPurpose(str, Enum):
    HONEYMOON = "honeymoon"
    GRADUATION_TRIP = "graduation_trip"
    FAMILY_VACATION = "family_vacation"
    SOLO_ADVENTURE = "solo_adventure"
    BUSINESS_TRIP = "business_trip"
    FIRST_TRIP = "first_trip"
    ANNIVERSARY = "anniversary"
    FRIENDS_GETAWAY = "friends_getaway"


class GroupType(str, Enum):
    SOLO = "solo"
    COUPLE = "couple"
    FAMILY = "family"
    FRIENDS = "friends"


class HotelTier(str, Enum):
    BUDGET = "budget"
    MID_RANGE = "mid_range"
    LUXURY = "luxury"


class TravelStyle(str, Enum):
    ADVENTURE = "adventure"
    RELAXING = "relaxing"
    CULTURAL = "cultural"
    FOODIE = "foodie"
    NATURE = "nature"
    SHOPPING = "shopping"
    NO_SPECIAL_STYLE = "no_special_style"


class FlightDirection(str, Enum):
    OUTBOUND = "outbound"
    RETURN = "return"


MaxStops = Literal[0, 1, 2]


class DietaryRestriction(str, Enum):
    NO_RESTRICTION = "none"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    HALAL = "halal"
    KOSHER = "kosher"
    GLUTEN_FREE = "gluten_free"


class ActivityCategory(str, Enum):
    SIGHTSEEING = "sightseeing"
    FOOD = "food"
    ADVENTURE = "adventure"
    CULTURE = "culture"
    SHOPPING = "shopping"
    TRANSPORT = "transport"
    OTHER = "other"


class CabinClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"
