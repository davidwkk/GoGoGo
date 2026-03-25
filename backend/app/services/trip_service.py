from typing import Any
from sqlalchemy.orm import Session

from app.repositories.trip_repo import trip_repo
from app.db.models.trip import Trip

class TripService:
    def save_trip(
        self,
        db: Session,
        user_id: int,
        session_id: int | None,
        title: str,
        destination: str,
        itinerary: Any  # Note: This will be David's 'TripItinerary' Pydantic model!
    ) -> Trip:
        """
        Takes the AI-generated itinerary, converts it to JSON, and saves the trip.
        """
        # INTEGRATION POINT WITH DAVID
        # Once David finishes the 'TripItinerary' model, it will be passed here.
        # We must use .model_dump(mode='json') to safely convert nested data to a database-ready format.
        if hasattr(itinerary, "model_dump"):
            itinerary_json = itinerary.model_dump(mode="json")
        else:
            # Fallback just in case a plain dictionary is passed during your early testing
            itinerary_json = itinerary 

        # Call the repository to actually save it to the database
        return trip_repo.create(
            db=db,
            user_id=user_id,
            session_id=session_id,
            title=title,
            destination=destination,
            itinerary_json=itinerary_json
        )

    def get_user_trips(self, db: Session, user_id: int) -> list[Trip]:
        """Retrieves a summary list of all trips belonging to a user."""
        return trip_repo.get_by_user(db, user_id)

    def get_trip_detail(self, db: Session, trip_id: int) -> Trip | None:
        """Retrieves the full details of a specific trip, including the itinerary."""
        return trip_repo.get_by_id(db, trip_id)

    def delete_trip(self, db: Session, trip_id: int) -> bool:
        """Deletes a trip from the database."""
        return trip_repo.delete(db, trip_id)

# Export a single instance to use in our API routes
trip_service = TripService()