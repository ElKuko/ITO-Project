"""Store CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Store
from ..schemas import StoreCreate, StoreOut
from ..auth import get_current_user, require_admin

router = APIRouter(prefix="/api/stores", tags=["stores"])


@router.get("/", response_model=list[StoreOut])
def list_stores(
    region: str = None,
    chain: str = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List stores. Admins can include inactive stores."""
    q = db.query(Store)
    # Only admins can see inactive stores
    if not include_inactive or current_user.role != "admin":
        q = q.filter(Store.is_active == True)
    if region:
        q = q.filter(Store.region == region)
    if chain:
        q = q.filter(Store.chain == chain)
    return q.order_by(Store.name).all()


@router.get("/{store_id}", response_model=StoreOut)
def get_store(store_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.post("/", response_model=StoreOut)
def create_store(req: StoreCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    store = Store(**req.model_dump())
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@router.put("/{store_id}", response_model=StoreOut)
def update_store(store_id: int, req: StoreCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    for key, val in req.model_dump().items():
        setattr(store, key, val)
    db.commit()
    db.refresh(store)
    return store


@router.delete("/{store_id}")
def delete_store(store_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Deactivate a store (soft delete to preserve historical data)."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    store.is_active = False
    db.commit()
    return {"detail": "Store deactivated"}


@router.post("/{store_id}/activate", response_model=StoreOut)
def activate_store(store_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Reactivate a previously deactivated store."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    store.is_active = True
    db.commit()
    db.refresh(store)
    return store


@router.get("/chains")
def list_chains(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Get list of unique store chains."""
    rows = db.query(Store.chain).filter(Store.chain != None).distinct().all()
    return [r[0] for r in rows if r[0]]
