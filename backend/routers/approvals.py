"""Store-SKU approval management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import StoreSKUApproval, Store, SKU
from ..schemas import ApprovalCreate, ApprovalOut
from ..auth import get_current_user, require_admin

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("/", response_model=list[ApprovalOut])
def list_approvals(
    store_id: int = None,
    quarter: str = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(StoreSKUApproval).options(
        joinedload(StoreSKUApproval.sku),
        joinedload(StoreSKUApproval.store),
    )
    if store_id:
        q = q.filter(StoreSKUApproval.store_id == store_id)
    if quarter:
        q = q.filter(StoreSKUApproval.quarter == quarter)
    return q.all()


@router.post("/", response_model=ApprovalOut)
def create_approval(req: ApprovalCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if not db.query(Store).filter(Store.id == req.store_id).first():
        raise HTTPException(status_code=404, detail="Store not found")
    if not db.query(SKU).filter(SKU.id == req.sku_id).first():
        raise HTTPException(status_code=404, detail="SKU not found")
    existing = db.query(StoreSKUApproval).filter(
        StoreSKUApproval.store_id == req.store_id,
        StoreSKUApproval.sku_id == req.sku_id,
        StoreSKUApproval.quarter == req.quarter,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Approval already exists for this store/SKU/quarter")
    approval = StoreSKUApproval(**req.model_dump())
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return db.query(StoreSKUApproval).options(
        joinedload(StoreSKUApproval.sku),
        joinedload(StoreSKUApproval.store),
    ).filter(StoreSKUApproval.id == approval.id).first()


@router.delete("/{approval_id}")
def delete_approval(approval_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    approval = db.query(StoreSKUApproval).filter(StoreSKUApproval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    db.delete(approval)
    db.commit()
    return {"detail": "Approval removed"}
