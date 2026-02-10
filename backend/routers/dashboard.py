"""Executive dashboard aggregation endpoints."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    StoreVisit, VisitSKUAction, VisitPhoto, Store, SKU, User, StoreSKUApproval,
)
from ..auth import get_current_user, require_admin

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _apply_filters(q, date_from, date_to, region, store_id, sku_id, merchandiser_id):
    if date_from:
        q = q.filter(StoreVisit.start_time >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(StoreVisit.start_time <= datetime.fromisoformat(date_to))
    if region:
        q = q.join(Store, StoreVisit.store_id == Store.id).filter(Store.region == region)
    if store_id:
        q = q.filter(StoreVisit.store_id == store_id)
    if merchandiser_id:
        q = q.filter(StoreVisit.user_id == merchandiser_id)
    return q


@router.get("/summary")
def dashboard_summary(
    date_from: str = None,
    date_to: str = None,
    region: str = None,
    store_id: int = None,
    sku_id: int = None,
    merchandiser_id: int = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    # Total visits
    visit_q = db.query(func.count(StoreVisit.id))
    visit_q = _apply_filters(visit_q, date_from, date_to, region, store_id, sku_id, merchandiser_id)
    total_visits = visit_q.scalar() or 0

    # Action breakdowns
    action_q = db.query(
        VisitSKUAction.action_type,
        func.count(VisitSKUAction.id),
    ).join(StoreVisit, VisitSKUAction.visit_id == StoreVisit.id)
    action_q = _apply_filters(action_q, date_from, date_to, region, store_id, sku_id, merchandiser_id)
    if sku_id:
        action_q = action_q.filter(VisitSKUAction.sku_id == sku_id)
    action_counts = dict(action_q.group_by(VisitSKUAction.action_type).all())

    # Photos processed
    photo_q = db.query(
        func.count(VisitPhoto.id),
        func.sum(case((VisitPhoto.cv_processed == True, 1), else_=0)),
    ).join(StoreVisit, VisitPhoto.visit_id == StoreVisit.id)
    photo_q = _apply_filters(photo_q, date_from, date_to, region, store_id, sku_id, merchandiser_id)
    photo_row = photo_q.first()
    total_photos = photo_row[0] or 0
    cv_processed_photos = int(photo_row[1] or 0)

    # Unique stores visited
    stores_q = db.query(func.count(func.distinct(StoreVisit.store_id)))
    stores_q = _apply_filters(stores_q, date_from, date_to, region, store_id, sku_id, merchandiser_id)
    stores_visited = stores_q.scalar() or 0

    total_stores = db.query(func.count(Store.id)).filter(Store.is_active == True).scalar() or 0

    return {
        "total_visits": total_visits,
        "stores_visited": stores_visited,
        "total_stores": total_stores,
        "coverage_rate": round(stores_visited / total_stores, 2) if total_stores > 0 else 0,
        "total_photos": total_photos,
        "cv_processed_photos": cv_processed_photos,
        "actions": {
            "gondola_llena": action_counts.get("gondola_llena", 0),
            "se_relleno": action_counts.get("se_relleno", 0),
            "orden": action_counts.get("orden", 0),
            "agotado": action_counts.get("agotado", 0),
        },
    }


@router.get("/by-store")
def dashboard_by_store(
    date_from: str = None,
    date_to: str = None,
    region: str = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(
        Store.id,
        Store.name,
        Store.region,
        func.count(func.distinct(StoreVisit.id)).label("visit_count"),
        func.sum(case((VisitSKUAction.action_type == "gondola_llena", 1), else_=0)).label("llena_count"),
        func.sum(case((VisitSKUAction.action_type == "se_relleno", 1), else_=0)).label("relleno_count"),
        func.sum(case((VisitSKUAction.action_type == "orden", 1), else_=0)).label("orden_count"),
        func.sum(case((VisitSKUAction.action_type == "agotado", 1), else_=0)).label("agotado_count"),
    ).outerjoin(StoreVisit, Store.id == StoreVisit.store_id
    ).outerjoin(VisitSKUAction, StoreVisit.id == VisitSKUAction.visit_id)

    if date_from:
        q = q.filter(StoreVisit.start_time >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(StoreVisit.start_time <= datetime.fromisoformat(date_to))
    if region:
        q = q.filter(Store.region == region)

    rows = q.filter(Store.is_active == True).group_by(Store.id).all()

    return [
        {
            "store_id": r[0],
            "store_name": r[1],
            "region": r[2],
            "visit_count": r[3],
            "gondola_llena": r[4] or 0,
            "se_relleno": r[5] or 0,
            "orden": r[6] or 0,
            "agotado": r[7] or 0,
        }
        for r in rows
    ]


@router.get("/incidents")
def dashboard_incidents(
    days_threshold: int = 7,
    region: str = None,
    store_id: int = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Unresolved shelf issues — SKUs that need order or are out of stock."""
    cutoff = datetime.utcnow() - timedelta(days=days_threshold)

    # Find SKU actions of type "orden" (needs order) or "agotado" (out of stock)
    # These are items that need attention
    q = db.query(
        VisitSKUAction.id,
        VisitSKUAction.action_type,
        VisitSKUAction.sku_id,
        SKU.name.label("sku_name"),
        StoreVisit.store_id,
        Store.name.label("store_name"),
        Store.region,
        StoreVisit.start_time,
        User.full_name.label("merchandiser_name"),
    ).join(StoreVisit, VisitSKUAction.visit_id == StoreVisit.id
    ).join(Store, StoreVisit.store_id == Store.id
    ).join(SKU, VisitSKUAction.sku_id == SKU.id
    ).join(User, StoreVisit.user_id == User.id
    ).filter(VisitSKUAction.action_type.in_(["orden", "agotado"]))

    if region:
        q = q.filter(Store.region == region)
    if store_id:
        q = q.filter(StoreVisit.store_id == store_id)

    rows = q.order_by(StoreVisit.start_time.asc()).all()

    incidents = []
    for r in rows:
        age_days = (datetime.utcnow() - r.start_time).days
        incidents.append({
            "action_id": r.id,
            "action_type": r.action_type,
            "sku_id": r.sku_id,
            "sku_name": r.sku_name,
            "store_id": r.store_id,
            "store_name": r.store_name,
            "region": r.region,
            "reported_at": r.start_time.isoformat(),
            "merchandiser": r.merchandiser_name,
            "age_days": age_days,
            "severity": "red" if age_days > days_threshold else "yellow" if age_days > 3 else "green",
        })

    return {
        "total_incidents": len(incidents),
        "red_incidents": sum(1 for i in incidents if i["severity"] == "red"),
        "incidents": incidents,
    }


@router.get("/regions")
def list_regions(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(Store.region).filter(Store.is_active == True).distinct().all()
    return [r[0] for r in rows if r[0]]
