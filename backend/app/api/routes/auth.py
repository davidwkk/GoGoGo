from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.repositories.user_repo import get_user_by_email, create_user
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter()


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    logger.bind(
        event="auth_register_attempt",
        layer="route",
        email=body.email,
        username=body.username,
    ).info(f"AUTH: Register attempt for email={body.email}")

    # Check if email already exists
    existing = get_user_by_email(db, body.email)
    if existing:
        logger.bind(
            event="auth_register_email_conflict",
            layer="route",
            email=body.email,
        ).warning(f"AUTH: Register failed — email already exists: {body.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash password and create user
    hashed = get_password_hash(body.password)
    user = create_user(
        db,
        username=body.username,
        email=body.email,
        hashed_password=hashed,
    )

    # Create token with user_id so deps.py can use it for DB lookups
    token = create_access_token(
        {"sub": body.email, "user_id": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    logger.bind(
        event="auth_register_success",
        layer="route",
        user_id=str(user.id),
        email=body.email,
    ).info(f"AUTH: User registered successfully — user_id={user.id}")
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    logger.bind(
        event="auth_login_attempt",
        layer="route",
        email=body.email,
    ).info(f"AUTH: Login attempt for email={body.email}")

    # Look up user by email
    user = get_user_by_email(db, body.email)
    if not user:
        logger.bind(
            event="auth_login_user_not_found",
            layer="route",
            email=body.email,
        ).warning(f"AUTH: Login failed — user not found: {body.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(body.password, user.hashed_password):
        logger.bind(
            event="auth_login_invalid_password",
            layer="route",
            email=body.email,
            user_id=str(user.id),
        ).warning(f"AUTH: Login failed — invalid password for user={user.id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Create token with user_id so deps.py can use it for DB lookups
    token = create_access_token(
        {"sub": body.email, "user_id": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    logger.bind(
        event="auth_login_success",
        layer="route",
        user_id=str(user.id),
        email=body.email,
    ).info(f"AUTH: User logged in successfully — user_id={user.id}")
    return TokenResponse(access_token=token)
