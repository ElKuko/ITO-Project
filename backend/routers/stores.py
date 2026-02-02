"""Store CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Store
from ..schemas import StoreCreate, StoreOut
from ..auth import get_current_user, require_admin

router = APIRouter(prefix="/api/stores", tags=["stores"])


@router.get("/", response_model=list[StoreOut])
def list_stores(region: str = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(Store).filter(Store.is_active == True)
    if region:
        q = q.filter(Store.region == region)
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
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    store.is_active = False
    db.commit()
    return {"detail": "Store deactivated"}
