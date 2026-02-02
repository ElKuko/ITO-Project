"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserCreate, UserOut
from ..auth import hash_password, verify_password, create_token, get_current_user, require_admin

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    token = create_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/register", response_model=UserOut)
def register(req: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
        region=req.region,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
