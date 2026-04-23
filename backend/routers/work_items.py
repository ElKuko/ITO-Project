"""Work items API for segment-based photo workflow.

Each photo taken becomes a work item that groups:
- Before photo
- SKU selections with estado/trabajo
- Condition check questions
- After photo
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from ..database import get_db
from ..models import (
    WorkItem, VisitSKUAction, VisitPhoto, StoreVisit,
    SKU, StoreSKUApproval, User
)
from ..schemas import (
    WorkItemCreate, WorkItemUpdate, WorkItemComplete, WorkItemOut,
    SegmentAvailableSKUs, SegmentSummary, SKUOut, VisitPhotoOut
)
from ..auth import get_current_user

router = APIRouter(prefix="/api/work-items", tags=["work-items"])

VALID_SEGMENTS = ("produce", "provisiones", "congelados")
VALID_ESTADO = ("llena", "semi", "agotada")
VALID_TRABAJO = ("organice", "rellene", "ordene")


def _get_current_quarter() -> str:
    now = datetime.utcnow()
    quarter = (now.month - 1) // 3 + 1
    return f"{now.year}-Q{quarter}"


def _work_item_query(db: Session):
    return db.query(WorkItem).options(
        joinedload(WorkItem.before_photo),
        joinedload(WorkItem.after_photo),
        joinedload(WorkItem.sku_actions).joinedload(VisitSKUAction.sku),
    )


@router.get("/visit/{visit_id}", response_model=list[WorkItemOut])
def list_work_items(
    visit_id: int,
    segment: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all work items for a visit, optionally filtered by segment."""
    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    query = _work_item_query(db).filter(WorkItem.visit_id == visit_id)
    if segment:
        if segment not in VALID_SEGMENTS:
            raise HTTPException(status_code=400, detail=f"Invalid segment. Must be one of: {VALID_SEGMENTS}")
        query = query.filter(WorkItem.segment == segment)

    return query.order_by(WorkItem.created_at).all()


@router.get("/visit/{visit_id}/segments", response_model=list[SegmentSummary])
def get_segment_summaries(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get summary of work items per segment for a visit."""
    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    summaries = []
    for segment in VALID_SEGMENTS:
        work_items = db.query(WorkItem).filter(
            WorkItem.visit_id == visit_id,
            WorkItem.segment == segment
        ).all()

        summaries.append(SegmentSummary(
            segment=segment,
            total_work_items=len(work_items),
            completed_work_items=sum(1 for w in work_items if w.status == "completed"),
            pending_work_items=sum(1 for w in work_items if w.status == "created"),
            in_progress_work_items=sum(1 for w in work_items if w.status == "in_progress"),
        ))

    return summaries


@router.get("/visit/{visit_id}/segment/{segment}/available-skus", response_model=SegmentAvailableSKUs)
def get_available_skus(
    visit_id: int,
    segment: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get SKUs available for assignment in a segment (excludes already assigned SKUs)."""
    if segment not in VALID_SEGMENTS:
        raise HTTPException(status_code=400, detail=f"Invalid segment. Must be one of: {VALID_SEGMENTS}")

    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    quarter = _get_current_quarter()

    approved_skus = db.query(SKU).join(StoreSKUApproval).filter(
        StoreSKUApproval.store_id == visit.store_id,
        StoreSKUApproval.quarter == quarter,
        SKU.section == segment,
        SKU.is_active == True,
    ).all()

    assigned_sku_ids = db.query(VisitSKUAction.sku_id).join(WorkItem).filter(
        WorkItem.visit_id == visit_id,
        WorkItem.segment == segment,
    ).distinct().all()
    assigned_ids = [s[0] for s in assigned_sku_ids]

    available_skus = [s for s in approved_skus if s.id not in assigned_ids]

    return SegmentAvailableSKUs(
        segment=segment,
        skus=[SKUOut.model_validate(s) for s in available_skus],
        assigned_sku_ids=assigned_ids,
    )


@router.post("/visit/{visit_id}", response_model=WorkItemOut)
def create_work_item(
    visit_id: int,
    req: WorkItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new work item from a photo."""
    if req.segment not in VALID_SEGMENTS:
        raise HTTPException(status_code=400, detail=f"Invalid segment. Must be one of: {VALID_SEGMENTS}")

    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    photo = db.query(VisitPhoto).filter(VisitPhoto.id == req.photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    if photo.visit_id != visit_id:
        raise HTTPException(status_code=400, detail="Photo does not belong to this visit")

    photo.segment = req.segment
    photo.photo_type = "work_item_before"

    work_item = WorkItem(
        visit_id=visit_id,
        segment=req.segment,
        before_photo_id=req.photo_id,
        status="created",
    )
    db.add(work_item)
    db.commit()
    db.refresh(work_item)

    return _work_item_query(db).filter(WorkItem.id == work_item.id).first()


@router.get("/{work_item_id}", response_model=WorkItemOut)
def get_work_item(
    work_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single work item."""
    work_item = _work_item_query(db).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")

    visit = db.query(StoreVisit).filter(StoreVisit.id == work_item.visit_id).first()
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return work_item


@router.put("/{work_item_id}", response_model=WorkItemOut)
def update_work_item(
    work_item_id: int,
    req: WorkItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a work item with SKU actions and condition checks."""
    work_item = db.query(WorkItem).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")

    visit = db.query(StoreVisit).filter(StoreVisit.id == work_item.visit_id).first()
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    for action in req.sku_actions:
        if action.estado_gondola and action.estado_gondola not in VALID_ESTADO:
            raise HTTPException(status_code=400, detail=f"Invalid estado_gondola: {action.estado_gondola}")
        for t in action.trabajo:
            if t not in VALID_TRABAJO:
                raise HTTPException(status_code=400, detail=f"Invalid trabajo: {t}")
        # orden_cantidad_cajas and orden_fecha_llegada are optional even when ordene is selected

    existing_action_ids = db.query(VisitSKUAction.sku_id).join(WorkItem).filter(
        WorkItem.visit_id == work_item.visit_id,
        WorkItem.segment == work_item.segment,
        WorkItem.id != work_item_id,
    ).all()
    existing_ids = {s[0] for s in existing_action_ids}

    for action in req.sku_actions:
        if action.sku_id in existing_ids:
            raise HTTPException(
                status_code=400,
                detail=f"SKU {action.sku_id} is already assigned to another work item in this segment"
            )

    db.query(VisitSKUAction).filter(VisitSKUAction.work_item_id == work_item_id).delete()

    for action in req.sku_actions:
        sku = db.query(SKU).filter(SKU.id == action.sku_id).first()
        if not sku:
            raise HTTPException(status_code=404, detail=f"SKU {action.sku_id} not found")

        trabajo_str = ",".join(action.trabajo) if action.trabajo else ""
        has_ordene = "ordene" in action.trabajo
        db.add(VisitSKUAction(
            visit_id=work_item.visit_id,
            work_item_id=work_item_id,
            sku_id=action.sku_id,
            estado_gondola=action.estado_gondola,
            trabajo=trabajo_str,
            orden_cantidad_cajas=action.orden_cantidad_cajas if has_ordene else None,
            orden_fecha_llegada=action.orden_fecha_llegada if has_ordene else None,
            notes=action.notes,
        ))

    if req.prices_on_gondola is not None:
        work_item.prices_on_gondola = req.prices_on_gondola
    if req.pop_material_present is not None:
        work_item.pop_material_present = req.pop_material_present
    if req.product_presentable is not None:
        work_item.product_presentable = req.product_presentable
    if req.gondola_space_gained is not None:
        work_item.gondola_space_gained = req.gondola_space_gained
    if req.condition_notes is not None:
        work_item.condition_notes = req.condition_notes

    if req.sku_actions and work_item.status == "created":
        work_item.status = "in_progress"

    db.commit()
    return _work_item_query(db).filter(WorkItem.id == work_item_id).first()


@router.post("/{work_item_id}/complete", response_model=WorkItemOut)
def complete_work_item(
    work_item_id: int,
    req: WorkItemComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete a work item by attaching the after photo."""
    work_item = db.query(WorkItem).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")

    visit = db.query(StoreVisit).filter(StoreVisit.id == work_item.visit_id).first()
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    photo = db.query(VisitPhoto).filter(VisitPhoto.id == req.after_photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    if photo.visit_id != work_item.visit_id:
        raise HTTPException(status_code=400, detail="Photo does not belong to this visit")

    photo.segment = work_item.segment
    photo.photo_type = "work_item_after"

    work_item.after_photo_id = req.after_photo_id
    work_item.status = "completed"
    db.commit()

    return _work_item_query(db).filter(WorkItem.id == work_item_id).first()


@router.post("/{work_item_id}/reopen", response_model=WorkItemOut)
def reopen_work_item(
    work_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reopen a completed work item for editing."""
    work_item = db.query(WorkItem).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")

    visit = db.query(StoreVisit).filter(StoreVisit.id == work_item.visit_id).first()
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if visit.status == "submitted":
        raise HTTPException(status_code=400, detail="Cannot reopen work item after visit is submitted")

    work_item.status = "in_progress"
    db.commit()

    return _work_item_query(db).filter(WorkItem.id == work_item_id).first()


@router.delete("/{work_item_id}")
def delete_work_item(
    work_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a work item."""
    work_item = db.query(WorkItem).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")

    visit = db.query(StoreVisit).filter(StoreVisit.id == work_item.visit_id).first()
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if visit.status == "submitted":
        raise HTTPException(status_code=400, detail="Cannot delete work item after visit is submitted")

    db.delete(work_item)
    db.commit()

    return {"detail": "Work item deleted"}
