from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user

router = APIRouter()


class UserResponse(BaseModel):
    id: int
    username: str
    email: str


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    # TODO: Fetch from DB via user_repo
    return UserResponse(id=1, username="demo", email="demo@example.com")
