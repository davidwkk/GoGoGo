from enum import Enum


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


class FlightDirection(str, Enum):
    OUTBOUND = "outbound"
    RETURN = "return"


class MaxStops(int, Enum):
    DIRECT = 0
    ONE_STOP = 1
    TWO_STOPS = 2


class DietaryRestriction(str, Enum):
    NONE = "none"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    HALAL = "halal"
    KOSHER = "kosher"
    GLUTEN_FREE = "gluten_free"
