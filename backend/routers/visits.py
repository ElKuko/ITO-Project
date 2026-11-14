"""Store visit submission and management endpoints.

4-Step Workflow (v2):
1. Start Visit (POST /start) - select store, arrival photo
2. SKUs & Gondolas (POST /{id}/photos) - unified screen with:
   - SKU checkboxes for multi-select
   - Bulk photo actions (before/after) linked to SKU groups via gondola_group_id
   - SKU status actions (Llena, Rellenó, Orden, Agotado)
3. Condition Checks (PUT /{id}/conditions)
4. Submit/Complete (PUT /{id}/complete)
"""

import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..database import get_db
from ..models import (
    StoreVisit, VisitSKUAction, VisitSKUCountEvent, VisitPhoto, PhotoSKULink, Store, SKU, StoreSKUApproval, User
)
from ..schemas import (
    StoreVisitOut, VisitPhotoOut, VisitStartRequest, VisitStartResponse,
    VisitCompleteRequest, VisitConditionChecks, SKUOut, SkuReportSave, VisitNotesUpdate
)
from ..auth import get_current_user
from ..cv.void_detector import analyze_shelf_image
from ..storage import storage

router = APIRouter(prefix="/api/visits", tags=["visits"])

SEGMENTS = ("produce", "provisiones", "congelados")


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

    # Check for duplicate visit to same store today
    today = datetime.utcnow().date()
    existing_visit = db.query(StoreVisit).filter(
        StoreVisit.store_id == req.store_id,
        StoreVisit.user_id == current_user.id,
        func.date(StoreVisit.start_time) == today,
        StoreVisit.status == "submitted",
    ).first()

    if existing_visit:
        raise HTTPException(
            status_code=400,
            detail="Ya existe una visita completada para esta tienda hoy"
        )

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


# ── Photo Upload with Gondola Grouping ───────────────────────────────────

@router.post("/{visit_id}/photos", response_model=VisitPhotoOut)
async def upload_photo(
    visit_id: int,
    file: UploadFile = File(...),
    photo_type: str = Form(default="shelf"),  # arrival_proof | gondola_before | gondola_after
    gondola_group_id: str = Form(default=None),  # UUID linking before/after photos
    sku_ids: str = Form(default=""),  # Comma-separated SKU IDs this photo represents
    segment: str = Form(default=None),
    latitude: str = Form(default=None),
    longitude: str = Form(default=None),
    gps_accuracy: str = Form(default=None),
    captured_at: str = Form(default=None),
    run_cv: str = Form(default="false"),  # Disabled for MVP - enable when ML pipeline is ready
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a photo for the visit with optional gondola grouping and SKU linking."""
    # Convert string form values to proper types
    lat = float(latitude) if latitude and latitude.strip() else None
    lng = float(longitude) if longitude and longitude.strip() else None
    gps_acc = float(gps_accuracy) if gps_accuracy and gps_accuracy.strip() else None
    should_run_cv = run_cv.lower() in ("true", "1", "yes") if isinstance(run_cv, str) else bool(run_cv)
    group_id = gondola_group_id if gondola_group_id and gondola_group_id.strip() else None

    # Parse SKU IDs from comma-separated string
    linked_sku_ids = []
    if sku_ids and sku_ids.strip():
        try:
            linked_sku_ids = [int(s.strip()) for s in sku_ids.split(",") if s.strip()]
        except ValueError:
            pass

    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate photo type
    valid_types = ("arrival_proof", "gondola_before", "gondola_after", "shelf_before", "shelf_after", "shelf", "work_item_before", "work_item_after", "sku_photo")
    if photo_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid photo_type. Must be one of: {valid_types}")
    photo_segment = segment if segment and segment.strip() else None
    if photo_segment and photo_segment not in SEGMENTS:
        raise HTTPException(status_code=400, detail=f"Invalid segment. Must be one of: {SEGMENTS}")

    ext = os.path.splitext(file.filename or "photo.jpg")[1] or ".jpg"
    filename = f"{visit_id}_{photo_type}_{uuid.uuid4().hex}{ext}"
    content_type = file.content_type or "image/jpeg"

    contents = await file.read()
    file_url = await storage.upload(contents, filename, content_type)

    # Parse captured_at if provided
    photo_captured_at = datetime.utcnow()
    if captured_at:
        try:
            photo_captured_at = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Run CV on gondola photos (only works with local storage)
    cv_results = None
    cv_processed = False
    if should_run_cv and photo_type in ("gondola_before", "gondola_after", "shelf_before", "shelf_after", "shelf"):
        # CV analysis requires local file access - skip for cloud storage
        if file_url.startswith("/uploads/"):
            try:
                from ..config import UPLOAD_DIR
                local_path = os.path.join(UPLOAD_DIR, filename)
                result = analyze_shelf_image(local_path)
                cv_results = json.dumps(result)
                cv_processed = True
            except Exception:
                pass

    photo = VisitPhoto(
        visit_id=visit_id,
        photo_type=photo_type,
        file_path=file_url,
        segment=photo_segment,
        gondola_group_id=group_id,
        captured_at=photo_captured_at,
        latitude=lat,
        longitude=lng,
        gps_accuracy=gps_acc,
        cv_processed=cv_processed,
        cv_results=cv_results,
    )
    db.add(photo)
    db.flush()  # Get the photo.id

    # Create SKU links for this photo
    for sku_id in linked_sku_ids:
        link = PhotoSKULink(photo_id=photo.id, sku_id=sku_id)
        db.add(link)

    db.commit()
    db.refresh(photo)
    return photo


@router.get("/{visit_id}/gondola-groups")
def get_gondola_groups(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get gondola photo groups for a visit - shows which groups need after photos."""
    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get all gondola photos grouped by gondola_group_id
    photos = db.query(VisitPhoto).filter(
        VisitPhoto.visit_id == visit_id,
        VisitPhoto.gondola_group_id != None
    ).all()

    groups = {}
    for photo in photos:
        gid = photo.gondola_group_id
        if gid not in groups:
            groups[gid] = {
                "gondola_group_id": gid,
                "before_photo": None,
                "after_photo": None,
                "sku_ids": [],
            }

        if photo.photo_type in ("gondola_before", "shelf_before"):
            groups[gid]["before_photo"] = {
                "id": photo.id,
                "file_path": photo.file_path,
                "captured_at": photo.captured_at.isoformat() if photo.captured_at else None,
            }
            # Get SKU IDs from this photo
            groups[gid]["sku_ids"] = [link.sku_id for link in photo.sku_links]
        elif photo.photo_type in ("gondola_after", "shelf_after"):
            groups[gid]["after_photo"] = {
                "id": photo.id,
                "file_path": photo.file_path,
                "captured_at": photo.captured_at.isoformat() if photo.captured_at else None,
            }

    return {
        "groups": list(groups.values()),
        "pending_after_count": sum(1 for g in groups.values() if g["before_photo"] and not g["after_photo"]),
    }


# ── Per-SKU Box Report ───────────────────────────────────────────────────
#
# A SKU is "registered" in a visit once it has a VisitSKUAction row with both
# counts entered (0 is a valid entry). A segment is complete when every SKU that
# applies to it is registered. Every change to a count is appended to
# VisitSKUCountEvent, so the full history is preserved.

COUNT_FIELDS = ("cajas_puestas", "cajas_faltaron")


def _get_own_visit(db: Session, visit_id: int, current_user: User) -> StoreVisit:
    visit = db.query(StoreVisit).filter(StoreVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    if current_user.role == "merchandiser" and visit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return visit


def _check_segment(segment: str):
    if segment not in SEGMENTS:
        raise HTTPException(status_code=400, detail=f"Invalid segment. Must be one of: {SEGMENTS}")


def _current_quarter() -> str:
    now = datetime.utcnow()
    return f"{now.year}-Q{(now.month - 1) // 3 + 1}"


def _report_actions(db: Session, visit_id: int, segment: str):
    return db.query(VisitSKUAction).filter(
        VisitSKUAction.visit_id == visit_id,
        VisitSKUAction.segment == segment,
        VisitSKUAction.work_item_id == None,
    )


def _segment_photos(db: Session, visit_id: int, segment: str):
    return db.query(VisitPhoto).filter(
        VisitPhoto.visit_id == visit_id,
        VisitPhoto.photo_type == "sku_photo",
        VisitPhoto.segment == segment,
    )


def _is_submitted(visit: StoreVisit) -> bool:
    return visit.status in ("submitted", "reviewed")


def _approved_skus(db: Session, store_id: int, segment: str) -> list[SKU]:
    return db.query(SKU).join(StoreSKUApproval).filter(
        StoreSKUApproval.store_id == store_id,
        StoreSKUApproval.quarter == _current_quarter(),
        SKU.section == segment,
        SKU.is_active == True,
    ).order_by(SKU.name).all()


def _segment_skus(db: Session, visit: StoreVisit, segment: str, actions: dict) -> list[dict]:
    """The SKUs a segment report covers.

    Draft visits: the store's currently approved SKUs. Submitted visits: exactly
    the SKUs recorded at submission, with their names as they were then, so later
    catalog changes don't alter history.
    """
    if _is_submitted(visit):
        rows = sorted(actions.values(), key=lambda a: (a.sku_name or a.sku.name).lower())
        return [
            {
                **SKUOut.model_validate(a.sku).model_dump(),
                "name": a.sku_name or a.sku.name,
                "barcode": a.sku_code if a.sku_code is not None else a.sku.barcode,
            }
            for a in rows
        ]
    return [SKUOut.model_validate(s).model_dump() for s in _approved_skus(db, visit.store_id, segment)]


def _is_registered(action) -> bool:
    return action is not None and action.cajas_puestas is not None and action.cajas_faltaron is not None


def _segment_state(total: int, registered: int) -> str:
    if total == 0:
        return "no_aplica"
    if registered == 0:
        return "pendiente"
    if registered < total:
        return "en_progreso"
    return "completado"


def _segment_summary(db: Session, visit: StoreVisit, segment: str) -> dict:
    actions = {a.sku_id: a for a in _report_actions(db, visit.id, segment).all()}
    sku_ids = [s["id"] for s in _segment_skus(db, visit, segment, actions)]
    registered = [actions[i] for i in sku_ids if _is_registered(actions.get(i))]
    return {
        "segment": segment,
        "status": _segment_state(len(sku_ids), len(registered)),
        "skus_total": len(sku_ids),
        "skus_reported": len(registered),
        "cajas_puestas": sum(a.cajas_puestas for a in registered),
        "cajas_faltaron": sum(a.cajas_faltaron for a in registered),
        "photos": _segment_photos(db, visit.id, segment).count(),
    }


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


@router.get("/{visit_id}/sku-report")
def get_sku_report(
    visit_id: int,
    segment: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The SKUs of a segment with the box counts entered so far (null = not entered)."""
    _check_segment(segment)
    visit = _get_own_visit(db, visit_id, current_user)

    actions = {a.sku_id: a for a in _report_actions(db, visit_id, segment).options(joinedload(VisitSKUAction.sku)).all()}
    skus = _segment_skus(db, visit, segment, actions)
    photos = _segment_photos(db, visit_id, segment).options(joinedload(VisitPhoto.sku_links)).all()

    def counts(sku_id):
        a = actions.get(sku_id)
        if not _is_registered(a):
            return {"cajas_puestas": None, "cajas_faltaron": None,
                    "cajas_puestas_at": None, "cajas_faltaron_at": None}
        return {
            "cajas_puestas": a.cajas_puestas,
            "cajas_faltaron": a.cajas_faltaron,
            "cajas_puestas_at": _iso(a.cajas_puestas_at),
            "cajas_faltaron_at": _iso(a.cajas_faltaron_at),
        }

    return {
        "segment": segment,
        "editable": not _is_submitted(visit) or current_user.role == "admin",
        "skus": [{**s, **counts(s["id"])} for s in skus],
        "photos": [
            {"id": p.id, "file_path": p.file_path, "sku_ids": [link.sku_id for link in p.sku_links]}
            for p in photos
        ],
    }


@router.put("/{visit_id}/sku-report")
def save_sku_report(
    visit_id: int,
    req: SkuReportSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a segment's box counts and photo-to-SKU links.

    Items with both counts entered are registered; items with neither only carry
    photo links. Counts are updated in place: a field's timestamp changes only when
    its value changes, and every change is appended to the count history.
    Submitted visits can only be changed by an admin.
    """
    _check_segment(req.segment)
    visit = _get_own_visit(db, visit_id, current_user)
    submitted = _is_submitted(visit)
    if submitted and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="La visita ya fue enviada")

    items = {}
    for item in req.items:
        if (item.cajas_puestas is None) != (item.cajas_faltaron is None):
            raise HTTPException(status_code=400, detail=f"SKU {item.sku_id}: ingrese ambas cantidades")
        items[item.sku_id] = item

    existing = {a.sku_id: a for a in _report_actions(db, visit_id, req.segment).all()}
    allowed = {s["id"]: s for s in _segment_skus(db, visit, req.segment, existing)}
    unknown = set(items) - set(allowed)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"SKUs no aprobados para esta tienda en {req.segment}: {sorted(unknown)}",
        )

    now = datetime.utcnow()

    def log(sku_id, field, old, new):
        db.add(VisitSKUCountEvent(
            visit_id=visit.id, store_id=visit.store_id, segment=req.segment, sku_id=sku_id,
            field=field, old_value=old, new_value=new, changed_by=current_user.id,
            changed_at=now, after_submission=submitted,
        ))

    for sku_id, sku in allowed.items():
        item = items.get(sku_id)
        action = existing.get(sku_id)
        registered = item is not None and item.cajas_puestas is not None

        if not registered:
            # Un-registering a SKU after submission would make the visit incomplete
            if action is not None and not submitted:
                for field in COUNT_FIELDS:
                    if getattr(action, field) is not None:
                        log(sku_id, field, getattr(action, field), None)
                db.delete(action)
            continue

        if action is None:
            action = VisitSKUAction(
                visit_id=visit.id, store_id=visit.store_id, sku_id=sku_id, segment=req.segment,
                sku_name=sku["name"], sku_code=sku.get("barcode"),
            )
            db.add(action)
        changed = False
        for field in COUNT_FIELDS:
            old, new = getattr(action, field), getattr(item, field)
            if old != new:
                setattr(action, field, new)
                setattr(action, f"{field}_at", now)
                log(sku_id, field, old, new)
                changed = True
        if changed:
            action.updated_at = now

    segment_photo_ids = {p.id for p in _segment_photos(db, visit_id, req.segment).all()}
    if segment_photo_ids:
        db.query(PhotoSKULink).filter(PhotoSKULink.photo_id.in_(segment_photo_ids)).delete(synchronize_session=False)
    for item in req.items:
        for photo_id in set(item.photo_ids) & segment_photo_ids:
            db.add(PhotoSKULink(photo_id=photo_id, sku_id=item.sku_id))

    db.commit()
    return _segment_summary(db, visit, req.segment)


@router.get("/{visit_id}/sku-report/summary")
def get_sku_report_summary(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-segment completion status and totals of the box report."""
    visit = _get_own_visit(db, visit_id, current_user)
    return [_segment_summary(db, visit, segment) for segment in SEGMENTS]


@router.get("/{visit_id}/sku-report/history")
def get_sku_report_history(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every change made to the visit's box counts, oldest first."""
    _get_own_visit(db, visit_id, current_user)
    events = db.query(VisitSKUCountEvent).options(joinedload(VisitSKUCountEvent.user)).filter(
        VisitSKUCountEvent.visit_id == visit_id
    ).order_by(VisitSKUCountEvent.changed_at, VisitSKUCountEvent.id).all()
    names = dict(db.query(SKU.id, SKU.name).filter(SKU.id.in_({e.sku_id for e in events})).all()) if events else {}
    # Prefer the name recorded with the visit over the current catalog name
    names.update({
        a.sku_id: a.sku_name for a in db.query(VisitSKUAction).filter(
            VisitSKUAction.visit_id == visit_id, VisitSKUAction.sku_name != None
        )
    })
    return [
        {
            "segment": e.segment,
            "sku_id": e.sku_id,
            "sku_name": names.get(e.sku_id),
            "field": e.field,
            "old_value": e.old_value,
            "new_value": e.new_value,
            "changed_by": e.user.full_name if e.user else None,
            "changed_at": _iso(e.changed_at),
            "after_submission": e.after_submission,
        }
        for e in events
    ]


@router.put("/{visit_id}/notes")
def update_visit_notes(
    visit_id: int,
    req: VisitNotesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit the visit's comments. Merchandisers before submission, admins any time."""
    visit = _get_own_visit(db, visit_id, current_user)
    if _is_submitted(visit) and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="La visita ya fue enviada")
    visit.notes = req.notes
    db.commit()
    return {"detail": "Observaciones guardadas"}


# ── Condition Checks ─────────────────────────────────────────────────────

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
    visit.gondola_space_gained = req.gondola_space_gained
    visit.condition_notes = req.notes
    db.commit()

    return {"detail": "Condition checks updated"}


# ── Step 5: Complete Visit ───────────────────────────────────────────────

@router.put("/{visit_id}/complete", response_model=StoreVisitOut)
async def complete_visit(
    visit_id: int,
    req: VisitCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete/submit the visit with all SKU actions and final data.

    Idempotent: submitting a visit that was already submitted (double tap, network
    retry) returns it unchanged without creating records or notifications.
    """
    visit = _get_own_visit(db, visit_id, current_user)
    if _is_submitted(visit):
        return _visit_query(db).filter(StoreVisit.id == visit.id).first()

    incomplete = [
        s for s in (_segment_summary(db, visit, seg) for seg in SEGMENTS)
        if s["status"] in ("pendiente", "en_progreso")
    ]
    if incomplete:
        detail = "; ".join(
            f"{s['segment'].capitalize()}: {s['skus_total'] - s['skus_reported']} SKU(s) sin registrar"
            for s in incomplete
        )
        raise HTTPException(status_code=400, detail=f"Faltan secciones por completar — {detail}")

    # Claim the submission atomically so concurrent retries can't both submit
    claimed = db.query(StoreVisit).filter(
        StoreVisit.id == visit.id, StoreVisit.status == "in_progress"
    ).update({StoreVisit.status: "submitted"}, synchronize_session=False)
    if not claimed:
        db.rollback()
        return _visit_query(db).filter(StoreVisit.id == visit.id).first()
    db.refresh(visit)

    # Update per-section conditions if provided (new format)
    if req.section_conditions:
        import json
        visit.section_conditions = json.dumps(req.section_conditions)

    # Update legacy condition checks if provided (backwards compatibility)
    if req.prices_on_gondola is not None:
        visit.prices_on_gondola = req.prices_on_gondola
    if req.pop_material_present is not None:
        visit.pop_material_present = req.pop_material_present
    if req.product_presentable is not None:
        visit.product_presentable = req.product_presentable
    if req.gondola_space_gained is not None:
        visit.gondola_space_gained = req.gondola_space_gained
    if req.condition_notes:
        visit.condition_notes = req.condition_notes

    visit.notes = req.notes
    visit.flags = req.flags
    visit.end_time = datetime.utcnow()
    visit.status = "submitted"

    # Replace legacy whole-visit SKU actions only; work-item and box-report rows are kept
    if req.sku_actions:
        db.query(VisitSKUAction).filter(
            VisitSKUAction.visit_id == visit_id,
            VisitSKUAction.work_item_id == None,
            VisitSKUAction.segment == None,
        ).delete(synchronize_session=False)

    valid_actions = ("gondola_llena", "se_relleno", "orden", "agotado", "unknown")
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

    # Get the complete visit with all relations for notification
    completed_visit = _visit_query(db).filter(StoreVisit.id == visit.id).first()

    # Calculate summary data for notification
    photos = db.query(VisitPhoto).filter(VisitPhoto.visit_id == visit_id).all()
    gondola_groups = set()
    complete_groups = 0
    for p in photos:
        if p.gondola_group_id:
            gondola_groups.add(p.gondola_group_id)

    # Count complete groups (have both before and after)
    for group_id in gondola_groups:
        group_photos = [p for p in photos if p.gondola_group_id == group_id]
        has_before = any(p.photo_type in ("gondola_before", "shelf_before") for p in group_photos)
        has_after = any(p.photo_type in ("gondola_after", "shelf_after") for p in group_photos)
        if has_before and has_after:
            complete_groups += 1

    report_actions = [a for a in completed_visit.sku_actions if a.segment]
    summary_data = {
        "photo_groups_complete": complete_groups,
        "photo_groups_total": len(gondola_groups),
        "photo_count": len(photos),
        "sku_actions_count": len(req.sku_actions) or len(report_actions),
        "cajas_puestas": sum(a.cajas_puestas or 0 for a in report_actions),
        "cajas_faltaron": sum(a.cajas_faltaron or 0 for a in report_actions),
    }

    # Create and broadcast notification
    try:
        from .notifications import create_and_broadcast_notification
        await create_and_broadcast_notification(
            db=db,
            event_type="visit_completed",
            visit=completed_visit,
            summary_data=summary_data,
        )
    except Exception:
        # Don't fail the visit completion if notification fails
        pass

    return completed_visit


# ── Reprocess Photo CV ───────────────────────────────────────────────────

@router.post("/{visit_id}/photos/{photo_id}/reprocess")
def reprocess_photo(
    visit_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Re-run CV analysis on a photo (only works with local storage)."""
    photo = db.query(VisitPhoto).filter(
        VisitPhoto.id == photo_id, VisitPhoto.visit_id == visit_id
    ).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # CV analysis requires local file access
    if not photo.file_path.startswith("/uploads/"):
        raise HTTPException(
            status_code=400,
            detail="CV reprocessing not available for cloud-stored images"
        )

    from ..config import UPLOAD_DIR
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
