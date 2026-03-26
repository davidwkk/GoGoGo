"""Pytest fixtures for backend tests."""

from __future__ import annotations

import os
from typing import Generator

# Set test environment variables BEFORE any app imports
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("SERPAPI_KEY", "test-serpapi-key")
os.environ.setdefault("TAVILY_API_KEY", "test-tavily-key")
os.environ.setdefault("OPENWEATHER_API_KEY", "test-openweather-key")
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test-maps-key")

import pytest
from sqlalchemy import MetaData, Table, Column, Integer, String, DateTime, text
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


# Create users table directly (avoids importing Trip which uses PostgreSQL JSONB)
_test_metadata = MetaData()
_users_table = Table(
    "users",
    _test_metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String(50), unique=True, nullable=False),
    Column("email", String(100), unique=True, nullable=False),
    Column("hashed_password", String(255), nullable=False),
    Column("created_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
)


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _test_metadata.create_all(bind=engine)
    yield engine
    _test_metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Provide a transactional db session for each test."""
    TestSession = sessionmaker(bind=test_engine, expire_on_commit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
