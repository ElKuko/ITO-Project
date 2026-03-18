"""Annotation router for image markup on visit photos."""

import os
import uuid
import json
import base64
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ImageAnnotation, VisitPhoto, StoreVisit, User
from ..schemas import AnnotationCreate, AnnotationOut
from .auth import get_current_user

router = APIRouter(prefix="/api/annotations", tags=["annotations"])

# Upload directory for annotation previews
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")


@router.post("/", response_model=AnnotationOut)
async def create_annotation(
    data: AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an annotation on a visit photo."""
    # Verify photo exists
    photo = db.query(VisitPhoto).filter(VisitPhoto.id == data.photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Verify visit exists
    visit = db.query(StoreVisit).filter(StoreVisit.id == data.visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    # Create annotation record
    annotation = ImageAnnotation(
        photo_id=data.photo_id,
        visit_id=data.visit_id,
        photo_type=data.photo_type,
        gondola_group_id=data.gondola_group_id,
        annotation_data=data.annotation_data,
        created_by=current_user.id,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)

    return annotation


@router.post("/{annotation_id}/preview")
async def save_annotation_preview(
    annotation_id: int,
    preview_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save the flattened annotation preview image (base64 encoded)."""
    annotation = db.query(ImageAnnotation).filter(ImageAnnotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    # Decode base64 image data
    image_data = preview_data.get("image_data", "")
    if not image_data:
        raise HTTPException(status_code=400, detail="No image data provided")

    # Remove data URL prefix if present
    if "," in image_data:
        image_data = image_data.split(",")[1]

    try:
        image_bytes = base64.b64decode(image_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    # Generate filename and save
    filename = f"annotation_{annotation_id}_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(UPLOAD_DIR, filename)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    # Update annotation with preview path
    annotation.preview_path = f"/uploads/{filename}"
    db.commit()
    db.refresh(annotation)

    return {"preview_path": annotation.preview_path}


@router.get("/{annotation_id}", response_model=AnnotationOut)
async def get_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an annotation by ID."""
    annotation = db.query(ImageAnnotation).filter(ImageAnnotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    return annotation


@router.get("/photo/{photo_id}", response_model=list[AnnotationOut])
async def get_photo_annotations(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all annotations for a specific photo."""
    annotations = (
        db.query(ImageAnnotation)
        .filter(ImageAnnotation.photo_id == photo_id)
        .order_by(ImageAnnotation.created_at.desc())
        .all()
    )
    return annotations
