"""Store visit submission and management endpoints."""

import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import StoreVisit, VisitSKUAction, VisitPhoto, Store, SKU, User
from ..schemas import StoreVisitCreate, StoreVisitOut, VisitPhotoOut
from ..auth import get_current_user, require_admin
from ..cv.void_detector import analyze_shelf_image

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")

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
    return q.order_by(StoreVisit.visited_at.desc()).offset(offset).limit(limit).all()


@router.get("/{visit_id}", response_model=StoreVisitOut)
def get_visit(visit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    visit = _visit_query(db).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return visit


@router.post("/", response_model=StoreVisitOut)
def create_visit(
    req: StoreVisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not db.query(Store).filter(Store.id == req.store_id).first():
        raise HTTPException(status_code=404, detail="Store not found")

    visit = StoreVisit(
        store_id=req.store_id,
        user_id=current_user.id,
        latitude=req.latitude,
        longitude=req.longitude,
        notes=req.notes,
    )
    db.add(visit)
    db.flush()

    for action in req.sku_actions:
        if not db.query(SKU).filter(SKU.id == action.sku_id).first():
            raise HTTPException(status_code=404, detail=f"SKU {action.sku_id} not found")
        if action.action_type not in ("needs_refill", "placed_on_shelf", "needs_order"):
            raise HTTPException(status_code=400, detail=f"Invalid action_type: {action.action_type}")
        db.add(VisitSKUAction(
            visit_id=visit.id,
            sku_id=action.sku_id,
            action_type=action.action_type,
            notes=action.notes,
        ))

    db.commit()
    return _visit_query(db).filter(StoreVisit.id == visit.id).first()


@router.post("/{visit_id}/photos", response_model=VisitPhotoOut)
async def upload_photo(
    visit_id: int,
    file: UploadFile = File(...),
    run_cv: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    ext = os.path.splitext(file.filename or "photo.jpg")[1] or ".jpg"
    filename = f"{visit_id}_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    cv_results = None
    cv_processed = False
    if run_cv:
        try:
            result = analyze_shelf_image(filepath)
            cv_results = json.dumps(result)
            cv_processed = True
        except Exception:
            pass  # CV failure should not block photo upload

    photo = VisitPhoto(
        visit_id=visit_id,
        file_path=f"/uploads/{filename}",
        cv_processed=cv_processed,
        cv_results=cv_results,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@router.post("/{visit_id}/photos/{photo_id}/reprocess")
def reprocess_photo(
    visit_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    photo = db.query(VisitPhoto).filter(
        VisitPhoto.id == photo_id, VisitPhoto.visit_id == visit_id
    ).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    abs_path = os.path.join(os.path.dirname(UPLOAD_DIR), photo.file_path.lstrip("/"))
    try:
        result = analyze_shelf_image(abs_path)
        photo.cv_results = json.dumps(result)
        photo.cv_processed = True
        db.commit()
        return {"detail": "Reprocessed", "cv_results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV processing failed: {str(e)}")
