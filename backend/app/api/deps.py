from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db

security = HTTPBearer()

# --- TEMPORARY MOCK FOR XUAN's TESTING ---
def get_current_user(
    # We comment this out so Swagger doesn't force you to provide a token
    # credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    
    # --- Minqi's Real Auth Logic (Commented Out) ---
    # token = credentials.credentials
    # payload = decode_access_token(token)
    # if payload is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid or expired token",
    #     )
    # return {"user_id": payload.get("sub")}
    
    # --- Xuan's Fake Data for Testing ---
    # We return a dummy dict with "id": 1 to match what your trips.py expects
    return {"id": 1, "username": "test_user"}