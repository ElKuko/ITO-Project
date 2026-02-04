"""Store-SKU approval management endpoints.

Workflow A: Merchandisers can maintain the approved SKU list for each store.
Changes are tracked in the audit log.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import StoreSKUApproval, ApprovalAuditLog, Store, SKU, User
from ..schemas import ApprovalCreate, ApprovalOut, ApprovalBulkUpdate, ApprovalAuditOut
from ..auth import get_current_user

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("/", response_model=list[ApprovalOut])
def list_approvals(
    store_id: int = None,
    quarter: str = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """List approved SKUs, optionally filtered by store and quarter."""
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
def create_approval(
    req: ApprovalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a single SKU approval for a store. Logs the change."""
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

    approval = StoreSKUApproval(
        store_id=req.store_id,
        sku_id=req.sku_id,
        quarter=req.quarter,
        approved_by=current_user.id,
    )
    db.add(approval)

    # Audit log
    db.add(ApprovalAuditLog(
        store_id=req.store_id,
        user_id=current_user.id,
        action="added",
        sku_id=req.sku_id,
        quarter=req.quarter,
    ))

    db.commit()
    db.refresh(approval)
    return db.query(StoreSKUApproval).options(
        joinedload(StoreSKUApproval.sku),
        joinedload(StoreSKUApproval.store),
    ).filter(StoreSKUApproval.id == approval.id).first()


@router.delete("/{approval_id}")
def delete_approval(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a single SKU approval. Logs the change."""
    approval = db.query(StoreSKUApproval).filter(StoreSKUApproval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    # Audit log
    db.add(ApprovalAuditLog(
        store_id=approval.store_id,
        user_id=current_user.id,
        action="removed",
        sku_id=approval.sku_id,
        quarter=approval.quarter,
    ))

    db.delete(approval)
    db.commit()
    return {"detail": "Approval removed"}


@router.put("/bulk", response_model=list[ApprovalOut])
def bulk_update_approvals(
    req: ApprovalBulkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Replace all approved SKUs for a store/quarter with the provided list.
    Tracks additions and removals in the audit log.
    """
    if not db.query(Store).filter(Store.id == req.store_id).first():
        raise HTTPException(status_code=404, detail="Store not found")

    # Validate all SKU IDs
    for sku_id in req.sku_ids:
        if not db.query(SKU).filter(SKU.id == sku_id).first():
            raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")

    # Get current approvals
    current_approvals = db.query(StoreSKUApproval).filter(
        StoreSKUApproval.store_id == req.store_id,
        StoreSKUApproval.quarter == req.quarter,
    ).all()
    current_sku_ids = {a.sku_id for a in current_approvals}
    new_sku_ids = set(req.sku_ids)

    # Determine additions and removals
    to_add = new_sku_ids - current_sku_ids
    to_remove = current_sku_ids - new_sku_ids

    # Remove old approvals
    for approval in current_approvals:
        if approval.sku_id in to_remove:
            db.add(ApprovalAuditLog(
                store_id=req.store_id,
                user_id=current_user.id,
                action="removed",
                sku_id=approval.sku_id,
                quarter=req.quarter,
            ))
            db.delete(approval)

    # Add new approvals
    for sku_id in to_add:
        db.add(StoreSKUApproval(
            store_id=req.store_id,
            sku_id=sku_id,
            quarter=req.quarter,
            approved_by=current_user.id,
        ))
        db.add(ApprovalAuditLog(
            store_id=req.store_id,
            user_id=current_user.id,
            action="added",
            sku_id=sku_id,
            quarter=req.quarter,
        ))

    db.commit()

    # Return updated list
    return db.query(StoreSKUApproval).options(
        joinedload(StoreSKUApproval.sku),
        joinedload(StoreSKUApproval.store),
    ).filter(
        StoreSKUApproval.store_id == req.store_id,
        StoreSKUApproval.quarter == req.quarter,
    ).all()


@router.get("/audit", response_model=list[ApprovalAuditOut])
def list_audit_log(
    store_id: int = None,
    quarter: str = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Get the audit log of approval changes."""
    q = db.query(ApprovalAuditLog).options(
        joinedload(ApprovalAuditLog.sku),
        joinedload(ApprovalAuditLog.user),
    )
    if store_id:
        q = q.filter(ApprovalAuditLog.store_id == store_id)
    if quarter:
        q = q.filter(ApprovalAuditLog.quarter == quarter)
    return q.order_by(ApprovalAuditLog.timestamp.desc()).limit(limit).all()
