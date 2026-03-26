"""Auth schemas — request/response models for authentication endpoints."""

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    """Registration payload."""

    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """Login payload."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
