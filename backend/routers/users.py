"""User management endpoints for admin console."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import UserOut, UserCreate, UserUpdate
from ..auth import get_current_user, require_admin, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/", response_model=list[UserOut])
def list_users(
    role: str = None,
    region: str = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """List all users (admin only)."""
    q = db.query(User)
    if not include_inactive:
        q = q.filter(User.is_active == True)
    if role:
        q = q.filter(User.role == role)
    if region:
        q = q.filter(User.region == region)
    return q.order_by(User.full_name).all()


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Get a specific user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", response_model=UserOut)
def create_user(req: UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Create a new user (admin only)."""
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Validate role
    valid_roles = ["merchandiser", "supervisor", "admin"]
    if req.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")

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


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, req: UserUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Update a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate role if provided
    if req.role is not None:
        valid_roles = ["merchandiser", "supervisor", "admin"]
        if req.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")
        user.role = req.role

    if req.full_name is not None:
        user.full_name = req.full_name
    if req.region is not None:
        user.region = req.region
    if req.password is not None:
        user.password_hash = hash_password(req.password)
    if req.is_active is not None:
        user.is_active = req.is_active

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def deactivate_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Deactivate a user (admin only). Cannot deactivate yourself."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()
    return {"detail": "User deactivated"}


@router.post("/{user_id}/activate", response_model=UserOut)
def activate_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Reactivate a previously deactivated user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@router.get("/regions/list")
def list_user_regions(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Get list of unique regions assigned to users."""
    rows = db.query(User.region).filter(User.region != None).distinct().all()
    return [r[0] for r in rows if r[0]]
