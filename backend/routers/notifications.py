"""Real-time notification endpoints and WebSocket handler."""

import json
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from ..database import get_db
from ..models import Notification, Route, StoreVisit, User
from ..auth import get_current_user, decode_token
from ..schemas import (
    NotificationOut,
    NotificationMarkRead,
    NotificationMarkAcknowledged,
    NotificationCountOut,
)
from ..websocket_manager import manager

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ── REST Endpoints ───────────────────────────────────────────────────────


@router.get("/", response_model=List[NotificationOut])
def list_notifications(
    route_id: Optional[int] = None,
    event_type: Optional[str] = None,
    is_read: Optional[bool] = None,
    is_acknowledged: Optional[bool] = None,
    since_id: Optional[int] = None,
    since_time: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List notifications with optional filters.
    Admins see all, merchandisers see only their own visits.
    """
    query = db.query(Notification)

    # Role-based filtering
    if current_user.role != "admin":
        query = query.filter(Notification.merchandiser_id == current_user.id)

    # Apply filters
    if route_id is not None:
        query = query.filter(Notification.route_id == route_id)

    if event_type:
        query = query.filter(Notification.event_type == event_type)

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    if is_acknowledged is not None:
        query = query.filter(Notification.is_acknowledged == is_acknowledged)

    # For reconnection sync - get events newer than last known
    if since_id is not None:
        query = query.filter(Notification.id > since_id)

    if since_time:
        try:
            since_dt = datetime.fromisoformat(since_time.replace("Z", "+00:00"))
            query = query.filter(Notification.created_at > since_dt)
        except ValueError:
            pass  # Ignore invalid date format

    # Order by newest first
    query = query.order_by(desc(Notification.created_at))

    notifications = query.offset(offset).limit(limit).all()
    return notifications


@router.get("/counts")
def get_notification_counts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get unread notification counts grouped by route.
    Returns a count per route plus a total.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Get all routes
    routes = db.query(Route).filter(Route.is_active == True).all()

    counts = []
    total_unread = 0

    for route in routes:
        unread = db.query(Notification).filter(
            and_(
                Notification.route_id == route.id,
                Notification.is_read == False
            )
        ).count()

        total = db.query(Notification).filter(
            Notification.route_id == route.id
        ).count()

        counts.append({
            "route_id": route.id,
            "route_name": route.name,
            "unread_count": unread,
            "total_count": total,
        })
        total_unread += unread

    # Also count notifications without a route
    unrouted_unread = db.query(Notification).filter(
        and_(
            Notification.route_id == None,
            Notification.is_read == False
        )
    ).count()

    unrouted_total = db.query(Notification).filter(
        Notification.route_id == None
    ).count()

    if unrouted_total > 0:
        counts.append({
            "route_id": None,
            "route_name": "Sin Ruta",
            "unread_count": unrouted_unread,
            "total_count": unrouted_total,
        })
        total_unread += unrouted_unread

    return {
        "total_unread": total_unread,
        "by_route": counts,
    }


@router.get("/{notification_id}", response_model=NotificationOut)
def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single notification by ID."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Check access
    if current_user.role != "admin" and notification.merchandiser_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return notification


@router.post("/mark-read")
def mark_notifications_read(
    data: NotificationMarkRead,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark notifications as read."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    now = datetime.utcnow()
    updated = db.query(Notification).filter(
        Notification.id.in_(data.notification_ids)
    ).update(
        {"is_read": True, "read_at": now},
        synchronize_session=False
    )
    db.commit()

    return {"updated": updated}


@router.post("/mark-all-read")
def mark_all_notifications_read(
    route_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read, optionally filtered by route."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    now = datetime.utcnow()
    query = db.query(Notification).filter(Notification.is_read == False)

    if route_id is not None:
        query = query.filter(Notification.route_id == route_id)

    updated = query.update(
        {"is_read": True, "read_at": now},
        synchronize_session=False
    )
    db.commit()

    return {"updated": updated}


@router.post("/acknowledge")
def acknowledge_notifications(
    data: NotificationMarkAcknowledged,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark notifications as acknowledged (reviewed)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    now = datetime.utcnow()
    updated = db.query(Notification).filter(
        Notification.id.in_(data.notification_ids)
    ).update(
        {
            "is_acknowledged": True,
            "acknowledged_at": now,
            "acknowledged_by": current_user.id,
        },
        synchronize_session=False
    )
    db.commit()

    return {"updated": updated}


# ── WebSocket Endpoint ───────────────────────────────────────────────────


@router.websocket("/ws")
async def websocket_notifications(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    last_event_id: Optional[int] = Query(default=None),
):
    """
    WebSocket endpoint for real-time notifications.

    Connect with: ws://host/api/notifications/ws?token=<jwt>&last_event_id=<id>

    Messages from server:
    - {type: "notification", data: {...}}  - New notification
    - {type: "sync", data: {notifications: [...], count: N}}  - Missed notifications on reconnect
    - {type: "connected", data: {user_id, role}}  - Connection confirmed
    - {type: "error", data: {message: "..."}}  - Error message

    Messages from client:
    - {type: "ping"}  - Keepalive
    - {type: "subscribe", data: {routes: [1, 2, 3]}}  - Subscribe to specific routes
    """
    # Validate token
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = payload.get("user_id")
    role = payload.get("role")

    if not user_id:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    # Connect and register
    client = await manager.connect(
        websocket=websocket,
        user_id=user_id,
        role=role,
        last_event_id=last_event_id,
    )

    # Send connection confirmation
    await websocket.send_json({
        "type": "connected",
        "data": {"user_id": user_id, "role": role}
    })

    # Sync missed notifications if reconnecting
    if last_event_id is not None:
        db = next(get_db())
        try:
            missed = db.query(Notification).filter(
                Notification.id > last_event_id
            ).order_by(Notification.id).limit(100).all()

            if missed:
                await manager.send_sync_message(
                    user_id,
                    [_notification_to_dict(n) for n in missed]
                )
        finally:
            db.close()

    # Listen for client messages
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "subscribe":
                # Update route subscriptions
                routes = data.get("data", {}).get("routes", [])
                client.subscribed_routes = set(routes)
                await websocket.send_json({
                    "type": "subscribed",
                    "data": {"routes": routes}
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(user_id)


def _notification_to_dict(n: Notification) -> dict:
    """Convert notification model to dict for JSON serialization."""
    return {
        "id": n.id,
        "event_type": n.event_type,
        "route_id": n.route_id,
        "route_name": n.route_name,
        "visit_id": n.visit_id,
        "store_id": n.store_id,
        "store_name": n.store_name,
        "merchandiser_id": n.merchandiser_id,
        "merchandiser_name": n.merchandiser_name,
        "summary_data": n.summary_data,
        "event_time": n.event_time.isoformat() if n.event_time else None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "is_read": n.is_read,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "is_acknowledged": n.is_acknowledged,
        "acknowledged_at": n.acknowledged_at.isoformat() if n.acknowledged_at else None,
    }


# ── Notification Creation Helper ─────────────────────────────────────────


async def create_and_broadcast_notification(
    db: Session,
    event_type: str,
    visit: StoreVisit,
    summary_data: Optional[dict] = None,
):
    """
    Create a notification in the database and broadcast to connected clients.
    Called from visit completion endpoint.
    """
    # Determine route for this store
    from ..models import RouteStop
    route_stop = db.query(RouteStop).filter(
        RouteStop.store_id == visit.store_id
    ).first()

    route_id = None
    route_name = None
    if route_stop:
        route = db.query(Route).filter(Route.id == route_stop.route_id).first()
        if route:
            route_id = route.id
            route_name = route.name

    # Create notification record
    notification = Notification(
        event_type=event_type,
        route_id=route_id,
        route_name=route_name,
        visit_id=visit.id,
        store_id=visit.store_id,
        store_name=visit.store.name if visit.store else "Unknown",
        merchandiser_id=visit.user_id,
        merchandiser_name=visit.user.full_name if visit.user else "Unknown",
        summary_data=json.dumps(summary_data) if summary_data else None,
        event_time=visit.end_time or datetime.utcnow(),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    # Broadcast to connected clients
    notification_dict = _notification_to_dict(notification)
    await manager.broadcast_to_route(route_id, notification_dict)

    return notification
