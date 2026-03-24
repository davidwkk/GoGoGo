from datetime import timedelta

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest):
    # TODO: Save user to DB via repository
    _hashed = get_password_hash(body.password)  # Pending DB save
    token = create_access_token(
        {"sub": body.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    # TODO: Verify credentials via repository
    # For now, accept any valid email format
    token = create_access_token(
        {"sub": body.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(access_token=token)
