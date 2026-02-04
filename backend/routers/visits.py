"""Store visit submission and management endpoints.

New 6-step workflow:
1. Start Visit (POST /start) - creates visit, uploads arrival photo
2. Before Photo (POST /{id}/photos with type=shelf_before)
3. Condition Checks (PUT /{id}/conditions)
4. SKU Actions - added on complete
5. After Photo (POST /{id}/photos with type=shelf_after)
6. Submit/Complete (PUT /{id}/complete)
"""

import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import StoreVisit, VisitSKUAction, VisitPhoto, Store, SKU, User
from ..schemas import (
    StoreVisitOut, VisitPhotoOut, VisitStartRequest, VisitStartResponse,
    VisitCompleteRequest, VisitConditionChecks
)
from ..auth import get_current_user
from ..cv.void_detector import analyze_shelf_image

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "uploads")

router = APIRouter(prefix="/api/visits", tags=["visits"])


def _visit_query(db: Session):
    return db.query(StoreVisit).options(
        joinedload(StoreVisit.sku_actions).joinedload(VisitSKUAction.sku),
        joinedload(StoreVisit.photos),
        joinedload(StoreVisit.store),
        joinedload(StoreVisit.user),
    )


@router.get("/", response_model=list[StoreVisitOut])
def list_visits(
    store_id: int = None,
    user_id: int = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _visit_query(db)
    if current_user.role == "merchandiser":
        q = q.filter(StoreVisit.user_id == current_user.id)
    elif user_id:
        q = q.filter(StoreVisit.user_id == user_id)
    if store_id:
        q = q.filter(StoreVisit.store_id == store_id)
    if status:
        q = q.filter(StoreVisit.status == status)
    return q.order_by(StoreVisit.start_time.desc()).offset(offset).limit(limit).all()


@router.get("/{visit_id}", response_model=StoreVisitOut)
def get_visit(visit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    visit = _visit_query(db).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return visit


# ── Step 1: Start Visit ──────────────────────────────────────────────────

@router.post("/start", response_model=VisitStartResponse)
def start_visit(
    req: VisitStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new store visit. Creates the visit record with start time and GPS."""
    if not db.query(Store).filter(Store.id == req.store_id).first():
        raise HTTPException(status_code=404, detail="Store not found")

    visit = StoreVisit(
        store_id=req.store_id,
        user_id=current_user.id,
        start_time=datetime.utcnow(),
        latitude=req.latitude,
        longitude=req.longitude,
        gps_accuracy=req.gps_accuracy,
        status="in_progress",
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)

    return VisitStartResponse(
        visit_id=visit.id,
        store_id=visit.store_id,
        start_time=visit.start_time,
    )


# ── Step 2 & 5: Photo Upload ─────────────────────────────────────────────

@router.post("/{visit_id}/photos", response_model=VisitPhotoOut)
async def upload_photo(
    visit_id: int,
    file: UploadFile = File(...),
    photo_type: str = Form(default="shelf"),  # arrival_proof | shelf_before | shelf_after
    latitude: float = Form(default=None),
    longitude: float = Form(default=None),
    gps_accuracy: float = Form(default=None),
    captured_at: str = Form(default=None),  # ISO datetime string
    run_cv: bool = Form(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a photo for the visit. Photo type determines its purpose."""
    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate photo type
    valid_types = ("arrival_proof", "shelf_before", "shelf_after", "shelf")
    if photo_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid photo_type. Must be one of: {valid_types}")

    ext = os.path.splitext(file.filename or "photo.jpg")[1] or ".jpg"
    filename = f"{visit_id}_{photo_type}_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    # Parse captured_at if provided
    photo_captured_at = datetime.utcnow()
    if captured_at:
        try:
            photo_captured_at = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Run CV on shelf photos (before/after), not arrival proof
    cv_results = None
    cv_processed = False
    if run_cv and photo_type in ("shelf_before", "shelf_after", "shelf"):
        try:
            result = analyze_shelf_image(filepath)
            cv_results = json.dumps(result)
            cv_processed = True
        except Exception:
            pass  # CV failure should not block photo upload

    photo = VisitPhoto(
        visit_id=visit_id,
        photo_type=photo_type,
        file_path=f"/uploads/{filename}",
        captured_at=photo_captured_at,
        latitude=latitude,
        longitude=longitude,
        gps_accuracy=gps_accuracy,
        cv_processed=cv_processed,
        cv_results=cv_results,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


# ── Step 3: Condition Checks ─────────────────────────────────────────────

@router.put("/{visit_id}/conditions")
def update_condition_checks(
    visit_id: int,
    req: VisitConditionChecks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the condition check answers for a visit."""
    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    visit.prices_on_gondola = req.prices_on_gondola
    visit.pop_material_present = req.pop_material_present
    visit.product_presentable = req.product_presentable
    visit.condition_notes = req.notes
    db.commit()

    return {"detail": "Condition checks updated"}


# ── Step 6: Complete Visit ───────────────────────────────────────────────

@router.put("/{visit_id}/complete", response_model=StoreVisitOut)
def complete_visit(
    visit_id: int,
    req: VisitCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete/submit the visit with all SKU actions and final data."""
    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Update condition checks if provided
    if req.prices_on_gondola is not None:
        visit.prices_on_gondola = req.prices_on_gondola
    if req.pop_material_present is not None:
        visit.pop_material_present = req.pop_material_present
    if req.product_presentable is not None:
        visit.product_presentable = req.product_presentable
    if req.condition_notes:
        visit.condition_notes = req.condition_notes

    visit.notes = req.notes
    visit.flags = req.flags
    visit.end_time = datetime.utcnow()
    visit.status = "submitted"

    # Clear existing SKU actions and add new ones
    db.query(VisitSKUAction).filter(VisitSKUAction.visit_id == visit_id).delete()

    valid_actions = ("gondola_llena", "se_relleno", "orden", "unknown")
    for action in req.sku_actions:
        if not db.query(SKU).filter(SKU.id == action.sku_id).first():
            raise HTTPException(status_code=404, detail=f"SKU {action.sku_id} not found")
        if action.action_type not in valid_actions:
            raise HTTPException(status_code=400, detail=f"Invalid action_type: {action.action_type}")
        db.add(VisitSKUAction(
            visit_id=visit.id,
            sku_id=action.sku_id,
            action_type=action.action_type,
            facings_count=action.facings_count,
            notes=action.notes,
        ))

    db.commit()
    return _visit_query(db).filter(StoreVisit.id == visit.id).first()


# ── Reprocess Photo CV ───────────────────────────────────────────────────

@router.post("/{visit_id}/photos/{photo_id}/reprocess")
def reprocess_photo(
    visit_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Re-run CV analysis on a photo."""
    photo = db.query(VisitPhoto).filter(
        VisitPhoto.id == photo_id, VisitPhoto.visit_id == visit_id
    ).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    abs_path = os.path.join(UPLOAD_DIR, os.path.basename(photo.file_path))
    try:
        result = analyze_shelf_image(abs_path)
        photo.cv_results = json.dumps(result)
        photo.cv_processed = True
        db.commit()
        return {"detail": "Reprocessed", "cv_results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV processing failed: {str(e)}")


# ── Delete Visit (cancel in-progress) ────────────────────────────────────

@router.delete("/{visit_id}")
def delete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete/cancel an in-progress visit."""
    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if visit.status == "submitted" and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot delete submitted visit")

    db.delete(visit)
    db.commit()
    return {"detail": "Visit deleted"}
