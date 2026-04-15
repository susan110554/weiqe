"""
Authentication utilities for IC3 Admin Web Controller.

Thin wrappers around PyJWT – all token logic lives here so
main.py and future routes can import without repetition.
"""
from datetime import datetime, timedelta
from typing import Optional
import os
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY      = os.getenv("WEB_SECRET_KEY", "change-me-in-production")
ALGORITHM       = "HS256"
EXPIRE_MINUTES  = int(os.getenv("JWT_EXPIRE_MINUTES", 480))   # 8 h

_bearer = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT containing *data*."""
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=EXPIRE_MINUTES))
    return jwt.encode({**data, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """FastAPI dependency – resolves to the decoded JWT payload."""
    payload = decode_access_token(credentials.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload
