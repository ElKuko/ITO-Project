"""Report endpoints for admin users.

These endpoints provide aggregated data for business intelligence,
crowdsourced from merchandiser activities.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..database import get_db
from ..models import StoreSKUApproval, Store, SKU, User
from ..auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/approved-skus")
def get_approved_skus_report(
    quarter: str = None,
    chain: str = None,
    region: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a report of all stores with their approved SKUs.

    This data is valuable because supermarkets don't share it publicly -
    it's crowdsourced via merchandisers during their store visits.

    Returns list of stores with their approved SKU details.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Build query for approvals with related data
    q = db.query(StoreSKUApproval).options(
        joinedload(StoreSKUApproval.store),
        joinedload(StoreSKUApproval.sku),
    )

    if quarter:
        q = q.filter(StoreSKUApproval.quarter == quarter)

    # Apply store filters via subquery
    if chain or region:
        store_q = db.query(Store.id)
        if chain:
            store_q = store_q.filter(Store.chain == chain)
        if region:
            store_q = store_q.filter(Store.region == region)
        store_ids = [s[0] for s in store_q.all()]
        q = q.filter(StoreSKUApproval.store_id.in_(store_ids))

    approvals = q.all()

    # Group by store for the report
    stores_data = {}
    for approval in approvals:
        store = approval.store
        sku = approval.sku

        if store.id not in stores_data:
            stores_data[store.id] = {
                "store_id": store.id,
                "store_name": store.name,
                "chain": store.chain or "",
                "pueblo": store.pueblo or "",
                "region": store.region,
                "skus": []
            }

        stores_data[store.id]["skus"].append({
            "sku_id": sku.id,
            "sku_name": sku.name,
            "brand": sku.brand,
            "category": sku.category or "",
            "section": sku.section or "",
            "quarter": approval.quarter,
            "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
        })

    return {
        "report_name": "SKUs Aprobados en Tiendas",
        "filters": {
            "quarter": quarter,
            "chain": chain,
            "region": region,
        },
        "total_stores": len(stores_data),
        "total_approvals": len(approvals),
        "stores": list(stores_data.values()),
    }


@router.get("/approved-skus/flat")
def get_approved_skus_flat(
    quarter: str = None,
    chain: str = None,
    region: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get approved SKUs in a flat format suitable for Excel export.
    Each row represents one store-SKU approval.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    q = db.query(StoreSKUApproval).options(
        joinedload(StoreSKUApproval.store),
        joinedload(StoreSKUApproval.sku),
    )

    if quarter:
        q = q.filter(StoreSKUApproval.quarter == quarter)

    if chain or region:
        store_q = db.query(Store.id)
        if chain:
            store_q = store_q.filter(Store.chain == chain)
        if region:
            store_q = store_q.filter(Store.region == region)
        store_ids = [s[0] for s in store_q.all()]
        q = q.filter(StoreSKUApproval.store_id.in_(store_ids))

    approvals = q.order_by(StoreSKUApproval.store_id, StoreSKUApproval.sku_id).all()

    rows = []
    for a in approvals:
        rows.append({
            "tienda": a.store.name,
            "cadena": a.store.chain or "",
            "pueblo": a.store.pueblo or "",
            "region": a.store.region,
            "sku": a.sku.name,
            "marca": a.sku.brand,
            "categoria": a.sku.category or "",
            "seccion": a.sku.section or "",
            "trimestre": a.quarter,
            "fecha_aprobacion": a.approved_at.strftime("%Y-%m-%d") if a.approved_at else "",
        })

    return {
        "columns": [
            {"key": "tienda", "label": "Tienda"},
            {"key": "cadena", "label": "Cadena"},
            {"key": "pueblo", "label": "Pueblo"},
            {"key": "region", "label": "Región"},
            {"key": "sku", "label": "SKU"},
            {"key": "marca", "label": "Marca"},
            {"key": "categoria", "label": "Categoría"},
            {"key": "seccion", "label": "Sección"},
            {"key": "trimestre", "label": "Trimestre"},
            {"key": "fecha_aprobacion", "label": "Fecha Aprobación"},
        ],
        "rows": rows,
    }


@router.get("/filter-options")
def get_report_filter_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get available filter options for reports (quarters, chains, regions)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    quarters = db.query(StoreSKUApproval.quarter).distinct().order_by(
        StoreSKUApproval.quarter.desc()
    ).all()

    chains = db.query(Store.chain).filter(Store.chain.isnot(None)).distinct().order_by(
        Store.chain
    ).all()

    regions = db.query(Store.region).distinct().order_by(Store.region).all()

    return {
        "quarters": [q[0] for q in quarters],
        "chains": [c[0] for c in chains if c[0]],
        "regions": [r[0] for r in regions],
    }
