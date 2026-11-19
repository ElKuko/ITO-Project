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


# ── Box-count (cajas) analytics ──────────────────────────────────────────
#
# Built on one record per SKU per submitted visit (VisitSKUAction with a segment).
# Placement Opportunity = puestas + faltaron. Rates are null when it is zero.

CAJAS_GROUPS = ("store", "sku", "section", "merchandiser", "date", "visit")


def _cajas_query(db, store_id, sku_id, section, merchandiser_id, date_from, date_to, region=None):
    from datetime import timedelta
    from ..models import StoreVisit, VisitSKUAction

    q = db.query(VisitSKUAction, StoreVisit).join(StoreVisit, VisitSKUAction.visit_id == StoreVisit.id).filter(
        VisitSKUAction.segment != None,
        VisitSKUAction.work_item_id == None,
        VisitSKUAction.cajas_puestas != None,
        VisitSKUAction.cajas_faltaron != None,
        StoreVisit.status.in_(("submitted", "reviewed")),
    )
    if store_id:
        q = q.filter(StoreVisit.store_id == store_id)
    if region:
        q = q.filter(StoreVisit.store.has(Store.region == region))
    if sku_id:
        q = q.filter(VisitSKUAction.sku_id == sku_id)
    if section:
        q = q.filter(VisitSKUAction.segment == section)
    if merchandiser_id:
        q = q.filter(StoreVisit.user_id == merchandiser_id)
    from ..timeutil import pr_midnight_utc
    try:
        if date_from:
            q = q.filter(StoreVisit.start_time >= pr_midnight_utc(date_from))
        if date_to:
            q = q.filter(StoreVisit.start_time < pr_midnight_utc(date_to) + timedelta(days=1))
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas deben ser YYYY-MM-DD")
    return q


def _rates(puestas: int, faltaron: int) -> dict:
    total = puestas + faltaron
    return {
        "cajas_puestas": puestas,
        "cajas_faltaron": faltaron,
        "placement_opportunity": total,
        "placement_completion_rate": round(puestas / total, 4) if total else None,
        "unfulfilled_placement_rate": round(faltaron / total, 4) if total else None,
    }


def _require_reports_access(user: User):
    if user.role not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/cajas")
def get_cajas_report(
    group_by: str = "store",
    store_id: int = None,
    sku_id: int = None,
    section: str = None,
    merchandiser_id: int = None,
    date_from: str = None,
    date_to: str = None,
    region: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Totals and placement rates of submitted visits, grouped by store, SKU,
    section, merchandiser, date (Puerto Rico) or visit. Dates are YYYY-MM-DD, inclusive."""
    from ..timeutil import pr_date

    _require_reports_access(current_user)
    if group_by not in CAJAS_GROUPS:
        raise HTTPException(status_code=400, detail=f"group_by must be one of {CAJAS_GROUPS}")
    rows = _cajas_query(db, store_id, sku_id, section, merchandiser_id, date_from, date_to, region).all()

    groups = {}
    for a, v in rows:
        key, label = {
            "store": (v.store_id, v.store.name if v.store else None),
            "sku": (a.sku_id, a.sku_name or (a.sku.name if a.sku else None)),
            "section": (a.segment, a.segment),
            "merchandiser": (v.user_id, v.user.full_name if v.user else None),
            "date": (pr_date(v.start_time), pr_date(v.start_time)),
            "visit": (v.id, f"{v.store.name if v.store else v.store_id} · {pr_date(v.start_time)}"),
        }[group_by]
        g = groups.setdefault(key, {"key": key, "label": label, "p": 0, "f": 0, "skus": 0, "visits": set(),
                                    "last": None, "region": v.store.region if v.store else None})
        g["last"] = max(g["last"], v.start_time) if g["last"] else v.start_time
        g["p"] += a.cajas_puestas
        g["f"] += a.cajas_faltaron
        g["skus"] += 1
        g["visits"].add(v.id)

    result = [
        {"key": g["key"], "label": g["label"], "visits": len(g["visits"]), "sku_records": g["skus"],
         "last_visit_at": g["last"].isoformat() + "Z" if g["last"] else None,
         **({"region": g["region"]} if group_by == "store" else {}),
         **_rates(g["p"], g["f"])}
        for g in groups.values()
    ]
    result.sort(key=lambda r: (str(r["key"]) if group_by == "date" else -r["placement_opportunity"]))
    total_p = sum(r["cajas_puestas"] for r in result)
    total_f = sum(r["cajas_faltaron"] for r in result)
    return {
        "group_by": group_by,
        "totals": {"visits": len({v.id for _, v in rows}), "sku_records": len(rows), **_rates(total_p, total_f)},
        "rows": result,
    }


@router.get("/cajas/records")
def get_cajas_records(
    format: str = "json",
    store_id: int = None,
    sku_id: int = None,
    section: str = None,
    merchandiser_id: int = None,
    date_from: str = None,
    date_to: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The flat dataset: one row per SKU per submitted visit, with IDs and UTC timestamps.
    format=csv downloads it as a spreadsheet-friendly file."""
    import csv
    import io
    from fastapi.responses import StreamingResponse

    _require_reports_access(current_user)
    from ..models import StoreVisit, VisitSKUAction
    rows = _cajas_query(db, store_id, sku_id, section, merchandiser_id, date_from, date_to).order_by(
        StoreVisit.start_time, VisitSKUAction.segment, VisitSKUAction.sku_name
    ).all()

    def iso(dt):
        return dt.isoformat() + "Z" if dt else None

    records = [
        {
            "visit_sku_id": a.id,
            "visit_id": v.id,
            "store_id": v.store_id,
            "store_name": v.store.name if v.store else None,
            "merchandiser_id": v.user_id,
            "merchandiser_name": v.user.full_name if v.user else None,
            "section_id": a.segment,
            "sku_id": a.sku_id,
            "sku_code": a.sku_code,
            "sku_name": a.sku_name or (a.sku.name if a.sku else None),
            "cajas_puestas": a.cajas_puestas,
            "cajas_faltaron": a.cajas_faltaron,
            "cajas_puestas_at": iso(a.cajas_puestas_at),
            "cajas_faltaron_at": iso(a.cajas_faltaron_at),
            "updated_at": iso(a.updated_at),
            "visit_started_at": iso(v.start_time),
            "visit_submitted_at": iso(v.end_time),
        }
        for a, v in rows
    ]
    if format != "csv":
        return records

    buf = io.StringIO()
    fields = list(records[0].keys()) if records else ["visit_sku_id"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cajas_records.csv"},
    )
