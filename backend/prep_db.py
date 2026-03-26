"""Standalone DB bootstrap script.

Run this ONCE before starting the app for the first time, or after
`docker-compose down -v` to recreate the database.

Usage:
    uv run python prep_db.py

This creates all tables via SQLAlchemy (same as the legacy init_db()).
For ongoing schema management, use Alembic:
    docker-compose exec backend alembic upgrade head
    docker-compose exec backend alembic revision --autogenerate -m "description"
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402


def main() -> None:
    print("Connecting to database...")
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. All tables created successfully.")


if __name__ == "__main__":
    main()
