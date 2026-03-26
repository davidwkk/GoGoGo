#!/usr/bin/env python3
"""Seed the database with sample users for local development."""

from __future__ import annotations

import os
import sys

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

from sqlalchemy import text  # noqa: E402

from app.core.security import get_password_hash  # noqa: E402
from app.db.session import session_factory  # noqa: E402


SEED_USERS = [
    {"username": "alice", "email": "alice@example.com", "password": "password123"},
    {"username": "bob", "email": "bob@example.com", "password": "password123"},
    {"username": "charlie", "email": "charlie@example.com", "password": "password123"},
]


def seed_users() -> None:
    """Insert seed users into the database, skipping those that already exist."""
    session = session_factory()
    try:
        for user_data in SEED_USERS:
            existing = session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": user_data["email"]},
            ).fetchone()

            if existing:
                print(f"  Skipping {user_data['username']} (already exists)")
                continue

            hashed = get_password_hash(user_data["password"])
            session.execute(
                text(
                    """
                    INSERT INTO users (username, email, hashed_password, created_at)
                    VALUES (:username, :email, :hashed_password, NOW())
                    """
                ),
                {
                    "username": user_data["username"],
                    "email": user_data["email"],
                    "hashed_password": hashed,
                },
            )
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
