"""Route management and route-specific visit history endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..database import get_db
from ..models import Route, RouteStop, Store, StoreVisit, User, VisitSKUAction
from ..auth import get_current_user

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.get("/my-route")
def get_my_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the route assigned to the current merchandiser."""
    route = db.query(Route).options(
        joinedload(Route.stops).joinedload(RouteStop.store),
    ).filter(
        Route.merchandiser_id == current_user.id,
        Route.is_active == True
    ).first()

    if not route:
        return None

    return {
        "id": route.id,
        "name": route.name,
        "merchandiser_id": route.merchandiser_id,
        "store_count": len(route.stops),
    }


@router.get("/")
def list_routes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active routes with their merchandiser assignments."""
    if current_user.role not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Admin/supervisor access required")

    routes = db.query(Route).options(
        joinedload(Route.merchandiser),
        joinedload(Route.stops).joinedload(RouteStop.store),
    ).filter(Route.is_active == True).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "merchandiser": {
                "id": r.merchandiser.id,
                "full_name": r.merchandiser.full_name,
                "username": r.merchandiser.username,
            } if r.merchandiser else None,
            "store_count": len(r.stops),
            "stores": [
                {
                    "id": stop.store.id,
                    "name": stop.store.name,
                    "day": stop.day,
                    "visit_order": stop.visit_order,
                }
                for stop in sorted(r.stops, key=lambda s: (s.day, s.visit_order))
            ],
        }
        for r in routes
    ]


@router.put("/{route_id}/assign")
def assign_merchandiser_to_route(
    route_id: int,
    merchandiser_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign a merchandiser to a route. Pass merchandiser_id=null to unassign."""
    if current_user.role not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Admin/supervisor access required")

    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    if merchandiser_id is not None:
        # Verify merchandiser exists and is a merchandiser
        merchandiser = db.query(User).filter(User.id == merchandiser_id).first()
        if not merchandiser:
            raise HTTPException(status_code=404, detail="User not found")
        if merchandiser.role != "merchandiser":
            raise HTTPException(status_code=400, detail="User is not a merchandiser")

        # Remove from any previous route
        db.query(Route).filter(Route.merchandiser_id == merchandiser_id).update(
            {"merchandiser_id": None}
        )

    route.merchandiser_id = merchandiser_id
    db.commit()

    return {
        "id": route.id,
        "name": route.name,
        "merchandiser_id": route.merchandiser_id,
    }


@router.get("/{route_id}")
def get_route(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single route with all details."""
    if current_user.role not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Admin/supervisor access required")

    route = db.query(Route).options(
        joinedload(Route.merchandiser),
        joinedload(Route.stops).joinedload(RouteStop.store),
    ).filter(Route.id == route_id).first()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    return {
        "id": route.id,
        "name": route.name,
        "is_active": route.is_active,
        "merchandiser": {
            "id": route.merchandiser.id,
            "full_name": route.merchandiser.full_name,
            "username": route.merchandiser.username,
        } if route.merchandiser else None,
        "stops": [
            {
                "id": stop.id,
                "store_id": stop.store.id,
                "store_name": stop.store.name,
                "store_chain": stop.store.chain,
                "store_pueblo": stop.store.pueblo,
                "day": stop.day,
                "visit_order": stop.visit_order,
            }
            for stop in sorted(route.stops, key=lambda s: (s.day, s.visit_order))
        ],
    }


@router.get("/{route_id}/visits")
def get_route_visits(
    route_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get visit history for all stores in this route."""
    if current_user.role not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Admin/supervisor access required")

    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Get all store IDs in this route
    store_ids = db.query(RouteStop.store_id).filter(RouteStop.route_id == route_id).all()
    store_ids = [s[0] for s in store_ids]

    if not store_ids:
        return {"route_id": route_id, "route_name": route.name, "visits": []}

    # Get visits for these stores
    visits = db.query(StoreVisit).options(
        joinedload(StoreVisit.store),
        joinedload(StoreVisit.user),
        joinedload(StoreVisit.sku_actions).joinedload(VisitSKUAction.sku),
        joinedload(StoreVisit.photos),
    ).filter(
        StoreVisit.store_id.in_(store_ids)
    ).order_by(
        StoreVisit.start_time.desc()
    ).offset(offset).limit(limit).all()

    return {
        "route_id": route_id,
        "route_name": route.name,
        "visits": [
            {
                "id": v.id,
                "store_id": v.store_id,
                "store_name": v.store.name if v.store else None,
                "store_pueblo": v.store.pueblo if v.store else None,
                "user_id": v.user_id,
                "user_name": v.user.full_name if v.user else None,
                "start_time": v.start_time.isoformat() if v.start_time else None,
                "end_time": v.end_time.isoformat() if v.end_time else None,
                "status": v.status,
                "photo_count": len(v.photos) if v.photos else 0,
                "action_count": len(v.sku_actions) if v.sku_actions else 0,
                "actions_summary": _summarize_actions(v.sku_actions),
                "prices_on_gondola": v.prices_on_gondola,
                "pop_material_present": v.pop_material_present,
                "product_presentable": v.product_presentable,
                "gondola_space_gained": v.gondola_space_gained,
            }
            for v in visits
        ],
    }


def _summarize_actions(actions):
    """Summarize SKU actions by type."""
    if not actions:
        return {}
    summary = {}
    for a in actions:
        summary[a.action_type] = summary.get(a.action_type, 0) + 1
    return summary


@router.get("/{route_id}/summary")
def get_route_summary(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get summary stats for a route."""
    if current_user.role not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Admin/supervisor access required")

    route = db.query(Route).options(
        joinedload(Route.merchandiser)
    ).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Get store IDs and count
    store_ids = db.query(RouteStop.store_id).filter(RouteStop.route_id == route_id).all()
    store_ids = [s[0] for s in store_ids]
    store_count = len(store_ids)

    # Count visits and actions
    visit_count = 0
    action_counts = {"gondola_llena": 0, "se_relleno": 0, "orden": 0, "agotado": 0}

    if store_ids:
        visit_count = db.query(func.count(StoreVisit.id)).filter(
            StoreVisit.store_id.in_(store_ids)
        ).scalar() or 0

        # Get action counts
        actions = db.query(
            VisitSKUAction.action_type,
            func.count(VisitSKUAction.id)
        ).join(StoreVisit).filter(
            StoreVisit.store_id.in_(store_ids)
        ).group_by(VisitSKUAction.action_type).all()

        for action_type, count in actions:
            if action_type in action_counts:
                action_counts[action_type] = count

    return {
        "route_id": route.id,
        "route_name": route.name,
        "merchandiser": route.merchandiser.full_name if route.merchandiser else None,
        "store_count": store_count,
        "visit_count": visit_count,
        "actions": action_counts,
    }
