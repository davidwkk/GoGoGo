"""Tests for authentication: register, login endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import get_password_hash


class TestRegister:
    """Tests for POST /auth/register."""

    def test_register_success(self, db_session: Session):
        """New user registration returns a JWT token and creates a DB row."""
        from app.api.routes.auth import get_db, router

        def override_get_db():
            yield db_session

        app = FastAPI()
        app.include_router(router, prefix="/auth")
        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        response = client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify user was written to db
        row = db_session.execute(
            text("SELECT username, email FROM users WHERE email = :email"),
            {"email": "test@example.com"},
        ).fetchone()
        assert row is not None
        assert row.username == "testuser"
        assert row.email == "test@example.com"

    def test_register_duplicate_email(self, db_session: Session):
        """Registering with an existing email returns 409 Conflict."""
        from app.api.routes.auth import get_db, router

        def override_get_db():
            yield db_session

        # Pre-insert a user with the same email
        db_session.execute(
            text(
                """
                INSERT INTO users (username, email, hashed_password)
                VALUES (:username, :email, :hashed_password)
                """
            ),
            {
                "username": "existing",
                "email": "taken@example.com",
                "hashed_password": get_password_hash("existingpass"),
            },
        )
        db_session.commit()

        app = FastAPI()
        app.include_router(router, prefix="/auth")
        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        response = client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "email": "taken@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]


class TestLogin:
    """Tests for POST /auth/login."""

    def test_login_success(self, db_session: Session):
        """Valid credentials return a JWT token."""
        from app.api.routes.auth import get_db, router

        def override_get_db():
            yield db_session

        # Pre-insert user
        db_session.execute(
            text(
                """
                INSERT INTO users (username, email, hashed_password)
                VALUES (:username, :email, :hashed_password)
                """
            ),
            {
                "username": "logintest",
                "email": "login@example.com",
                "hashed_password": get_password_hash("correctpassword"),
            },
        )
        db_session.commit()

        app = FastAPI()
        app.include_router(router, prefix="/auth")
        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        response = client.post(
            "/auth/login",
            json={
                "email": "login@example.com",
                "password": "correctpassword",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, db_session: Session):
        """Wrong password returns 401 Unauthorized."""
        from app.api.routes.auth import get_db, router

        def override_get_db():
            yield db_session

        db_session.execute(
            text(
                """
                INSERT INTO users (username, email, hashed_password)
                VALUES (:username, :email, :hashed_password)
                """
            ),
            {
                "username": "wrongpw",
                "email": "wrongpw@example.com",
                "hashed_password": get_password_hash("thecorrectpassword"),
            },
        )
        db_session.commit()

        app = FastAPI()
        app.include_router(router, prefix="/auth")
        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        response = client.post(
            "/auth/login",
            json={
                "email": "wrongpw@example.com",
                "password": "thewrongpassword",
            },
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_nonexistent_user(self, db_session: Session):
        """Login with non-existent email returns 401 Unauthorized."""
        from app.api.routes.auth import get_db, router

        def override_get_db():
            yield db_session

        app = FastAPI()
        app.include_router(router, prefix="/auth")
        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        response = client.post(
            "/auth/login",
            json={
                "email": "ghost@example.com",
                "password": "anypassword",
            },
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]


class TestTokenResponse:
    """Tests for TokenResponse schema."""

    def test_token_response_model(self):
        """TokenResponse fields are correct."""
        from app.schemas.auth import TokenResponse

        response = TokenResponse(access_token="abc123")
        assert response.access_token == "abc123"
        assert response.token_type == "bearer"

    def test_token_response_default_type(self):
        """TokenResponse defaults to bearer token type."""
        from app.schemas.auth import TokenResponse

        response = TokenResponse(access_token="xyz")
        assert response.token_type == "bearer"


class TestRegisterRequest:
    """Tests for RegisterRequest schema validation."""

    def test_register_request_valid(self):
        """Valid register request parses correctly."""
        from app.schemas.auth import RegisterRequest

        req = RegisterRequest(
            username="alice",
            email="alice@example.com",
            password="password123",
        )
        assert req.username == "alice"
        assert req.email == "alice@example.com"
        assert req.password == "password123"

    def test_register_request_invalid_email(self):
        """Invalid email is rejected."""
        from pydantic import ValidationError
        from app.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError):
            RegisterRequest(
                username="alice",
                email="not-an-email",
                password="password123",
            )


class TestLoginRequest:
    """Tests for LoginRequest schema validation."""

    def test_login_request_valid(self):
        """Valid login request parses correctly."""
        from app.schemas.auth import LoginRequest

        req = LoginRequest(email="alice@example.com", password="password123")
        assert req.email == "alice@example.com"
        assert req.password == "password123"

    def test_login_request_invalid_email(self):
        """Invalid email is rejected."""
        from pydantic import ValidationError
        from app.schemas.auth import LoginRequest

        with pytest.raises(ValidationError):
            LoginRequest(email="not-email", password="password")
