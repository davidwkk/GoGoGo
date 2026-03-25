from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.trip import Trip

class TripRepository:
    def create(
        self, 
        db: Session, 
        user_id: int, 
        session_id: int | None, 
        title: str, 
        destination: str, 
        itinerary_json: dict
    ) -> Trip:
        """Saves a new trip and its AI-generated itinerary into the database."""
        db_trip = Trip(
            user_id=user_id,
            session_id=session_id,
            title=title,
            destination=destination,
            itinerary_json=itinerary_json
        )
        db.add(db_trip)
        db.commit()
        db.refresh(db_trip)
        return db_trip

    def get_by_id(self, db: Session, trip_id: int) -> Trip | None:
        """Fetches a single trip by its ID."""
        statement = select(Trip).where(Trip.id == trip_id)
        return db.execute(statement).scalar_one_or_none()

    def get_by_user(self, db: Session, user_id: int) -> list[Trip]:
        """Fetches all trips belonging to a specific user, newest first."""
        statement = select(Trip).where(Trip.user_id == user_id).order_by(Trip.created_at.desc())
        return list(db.execute(statement).scalars().all())

    def delete(self, db: Session, trip_id: int) -> bool:
        """Deletes a trip from the database. Returns True if successful."""
        db_trip = self.get_by_id(db, trip_id)
        if db_trip:
            db.delete(db_trip)
            db.commit()
            return True
        return False

# Export a single instance to use throughout the app
trip_repo = TripRepository()