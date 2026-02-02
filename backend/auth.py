"""Simple JWT-based authentication with role-based access."""

import hashlib
import hmac
import json
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .models import User

SECRET_KEY = "ito-mvp-secret-change-in-production"
TOKEN_EXPIRY = 86400  # 24 hours

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(password), hashed)


def create_token(user_id: int, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": int(time.time()) + TOKEN_EXPIRY,
    }
    payload_json = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        SECRET_KEY.encode(), payload_json.encode(), hashlib.sha256
    ).hexdigest()
    import base64
    token_data = base64.urlsafe_b64encode(payload_json.encode()).decode()
    return f"{token_data}.{signature}"


def decode_token(token: str) -> Optional[dict]:
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_json = base64.urlsafe_b64decode(parts[0]).decode()
        expected_sig = hmac.new(
            SECRET_KEY.encode(), payload_json.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, parts[1]):
            return None
        payload = json.loads(payload_json)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
