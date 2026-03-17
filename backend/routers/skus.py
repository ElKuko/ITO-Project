"""SKU CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SKU
from ..schemas import SKUCreate, SKUOut
from ..auth import get_current_user, require_admin

router = APIRouter(prefix="/api/skus", tags=["skus"])


@router.get("/", response_model=list[SKUOut])
def list_skus(
    brand: str = None,
    category: str = None,
    section: str = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List SKUs. Admins can include inactive SKUs."""
    q = db.query(SKU)
    # Only admins can see inactive SKUs
    if not include_inactive or current_user.role != "admin":
        q = q.filter(SKU.is_active == True)
    if brand:
        q = q.filter(SKU.brand == brand)
    if category:
        q = q.filter(SKU.category == category)
    if section:
        q = q.filter(SKU.section == section)
    return q.order_by(SKU.name).all()


@router.get("/{sku_id}", response_model=SKUOut)
def get_sku(sku_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    return sku


@router.post("/", response_model=SKUOut)
def create_sku(req: SKUCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    sku = SKU(**req.model_dump())
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return sku


@router.put("/{sku_id}", response_model=SKUOut)
def update_sku(sku_id: int, req: SKUCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    for key, val in req.model_dump().items():
        setattr(sku, key, val)
    db.commit()
    db.refresh(sku)
    return sku


@router.delete("/{sku_id}")
def deactivate_sku(sku_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Deactivate a SKU (soft delete to preserve historical data)."""
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    sku.is_active = False
    db.commit()
    return {"detail": "SKU deactivated"}


@router.post("/{sku_id}/activate", response_model=SKUOut)
def activate_sku(sku_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Reactivate a previously deactivated SKU."""
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    sku.is_active = True
    db.commit()
    db.refresh(sku)
    return sku
