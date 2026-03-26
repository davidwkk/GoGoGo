#!/usr/bin/env python3
"""Seed the database with sample users for local development."""

from __future__ import annotations

import os
import sys
from uuid import uuid4

# Ensure app module is importable (works both locally and inside container)
# When run from backend/: __file__ = backend/scripts/seed_db.py
# When run from container: __file__ = /app/scripts/seed_db.py
_script_dir = os.path.dirname(__file__)
_backend_dir = os.path.dirname(_script_dir)  # .../backend/scripts -> .../backend
_root_dir = os.path.dirname(_backend_dir)  # .../backend -> repo root

sys.path.insert(0, _backend_dir)

# Try loading .env for local dev (outside container)
_env_path = os.path.join(_root_dir, ".env")
if os.path.exists(_env_path):
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_path)
    except ImportError:
        pass  # dotenv not installed, rely on environment variables

from app.core.security import get_password_hash  # noqa: E402
from app.db.models import User  # noqa: E402
from app.db.session import session_factory  # noqa: E402


SEED_USERS = [
    {"username": "testuser", "email": "user@gmail.com", "password": "user"},
]


def seed_users() -> None:
    """Insert seed users into the database, skipping those that already exist."""
    session = session_factory()
    try:
        for user_data in SEED_USERS:
            existing = (
                session.query(User).filter(User.email == user_data["email"]).first()
            )
            if existing:
                print(f"  Skipping {user_data['username']} (already exists)")
                continue

            hashed = get_password_hash(user_data["password"])
            user = User(
                id=uuid4(),
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=hashed,
            )
            session.add(user)
            print(f"  Created {user_data['username']} ({user_data['email']})")
        session.commit()
        print("Seed complete.")
    finally:
        session.close()


if __name__ == "__main__":
    print("Seeding database with sample users...")
    db_url = os.getenv("DATABASE_URL", "(not set - using container env)")
    print(
        f"  DATABASE_URL: {db_url[:50]}..."
        if db_url and len(db_url) > 50
        else f"  DATABASE_URL: {db_url}"
    )
    seed_users()
