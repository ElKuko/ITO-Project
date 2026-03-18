"""Route chat endpoints for real-time messaging between admin and merchandiser."""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from ..database import get_db
from ..models import ChatMessage, Route, User
from ..auth import get_current_user, decode_token
from ..schemas import (
    ChatMessageCreate,
    ChatMessageOut,
    ChatMessageMarkRead,
)
from ..websocket_manager import manager

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _chat_message_to_dict(msg: ChatMessage, sender: User = None) -> dict:
    """Convert ChatMessage model to dict for JSON serialization."""
    return {
        "id": msg.id,
        "route_id": msg.route_id,
        "sender_user_id": msg.sender_user_id,
        "sender_name": sender.full_name if sender else (msg.sender.full_name if msg.sender else None),
        "sender_role": sender.role if sender else (msg.sender.role if msg.sender else None),
        "message_type": msg.message_type,
        "text": msg.text,
        "ref_visit_id": msg.ref_visit_id,
        "ref_store_id": msg.ref_store_id,
        "ref_store_name": msg.ref_store_name,
        "ref_photo_id": msg.ref_photo_id,
        "ref_photo_type": msg.ref_photo_type,
        "ref_gondola_group_id": msg.ref_gondola_group_id,
        "ref_photo_url": msg.ref_photo_url,
        "ref_captured_at": msg.ref_captured_at.isoformat() if msg.ref_captured_at else None,
        "ref_annotation_id": msg.ref_annotation_id,
        "ref_annotation_preview_url": msg.ref_annotation_preview_url,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "is_read": msg.is_read,
    }


# ── REST Endpoints ───────────────────────────────────────────────────────


@router.get("/routes/{route_id}/messages", response_model=List[ChatMessageOut])
def list_chat_messages(
    route_id: int,
    since_id: Optional[int] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List chat messages for a route.
    Admin sees all, merchandiser sees only their assigned route.
    """
    # Verify route exists
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Authorization: admin can see all, merchandiser only their route
    if current_user.role != "admin":
        if route.merchandiser_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied to this route chat")

    query = db.query(ChatMessage).filter(ChatMessage.route_id == route_id)

    # For sync - get messages newer than last known
    if since_id is not None:
        query = query.filter(ChatMessage.id > since_id)

    # Order by newest first for display
    query = query.order_by(desc(ChatMessage.created_at))
    messages = query.offset(offset).limit(limit).all()

    # Enrich with sender info
    result = []
    for msg in messages:
        msg_dict = _chat_message_to_dict(msg)
        result.append(ChatMessageOut(**msg_dict))

    return result


@router.post("/routes/{route_id}/messages", response_model=ChatMessageOut)
async def send_chat_message(
    route_id: int,
    data: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a chat message to a route.
    Creates the message and broadcasts to connected clients.
    """
    # Verify route exists
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Authorization: admin can message any route, merchandiser only their route
    if current_user.role != "admin":
        if route.merchandiser_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied to this route chat")

    # Create message
    msg = ChatMessage(
        route_id=route_id,
        sender_user_id=current_user.id,
        message_type=data.message_type,
        text=data.text,
    )

    # Add reference if provided
    if data.reference and data.message_type == "TAGGED_REFERENCE":
        msg.ref_visit_id = data.reference.visit_id
        msg.ref_store_id = data.reference.store_id
        msg.ref_store_name = data.reference.store_name
        msg.ref_photo_id = data.reference.photo_id
        msg.ref_photo_type = data.reference.photo_type
        msg.ref_gondola_group_id = data.reference.gondola_group_id
        msg.ref_photo_url = data.reference.photo_url
        msg.ref_captured_at = data.reference.captured_at

    # Add annotated reference if provided
    if data.annotated_reference and data.message_type == "ANNOTATED_REFERENCE":
        msg.ref_annotation_id = data.annotated_reference.annotation_id
        msg.ref_visit_id = data.annotated_reference.visit_id
        msg.ref_store_id = data.annotated_reference.store_id
        msg.ref_store_name = data.annotated_reference.store_name
        msg.ref_photo_id = data.annotated_reference.photo_id
        msg.ref_photo_type = data.annotated_reference.photo_type
        msg.ref_gondola_group_id = data.annotated_reference.gondola_group_id
        msg.ref_photo_url = data.annotated_reference.original_photo_url
        msg.ref_annotation_preview_url = data.annotated_reference.annotation_preview_url
        msg.ref_captured_at = data.annotated_reference.captured_at

    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Prepare response
    msg_dict = _chat_message_to_dict(msg, current_user)

    # Broadcast to route subscribers
    await manager.broadcast_chat_to_route(route_id, msg_dict)

    return ChatMessageOut(**msg_dict)


@router.post("/routes/{route_id}/messages/mark-read")
def mark_messages_read(
    route_id: int,
    data: ChatMessageMarkRead,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark chat messages as read."""
    now = datetime.utcnow()

    # Only mark messages not sent by current user
    updated = db.query(ChatMessage).filter(
        and_(
            ChatMessage.route_id == route_id,
            ChatMessage.id.in_(data.message_ids),
            ChatMessage.sender_user_id != current_user.id,
        )
    ).update(
        {"is_read": True, "read_at": now},
        synchronize_session=False
    )
    db.commit()

    return {"updated": updated}


@router.get("/routes/{route_id}/unread-count")
def get_unread_count(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get count of unread messages for current user in a route."""
    count = db.query(ChatMessage).filter(
        and_(
            ChatMessage.route_id == route_id,
            ChatMessage.sender_user_id != current_user.id,
            ChatMessage.is_read == False,
        )
    ).count()

    return {"route_id": route_id, "unread_count": count}


# ── WebSocket Endpoint ───────────────────────────────────────────────────


@router.websocket("/ws/{route_id}")
async def websocket_chat(
    websocket: WebSocket,
    route_id: int,
    token: Optional[str] = Query(default=None),
    last_message_id: Optional[int] = Query(default=None),
):
    """
    WebSocket endpoint for real-time chat on a specific route.

    Connect with: ws://host/api/chat/ws/{route_id}?token=<jwt>&last_message_id=<id>

    Messages from server:
    - {type: "chat_message", data: {...}}  - New chat message
    - {type: "chat_sync", data: {messages: [...], count: N}}  - Missed messages on reconnect
    - {type: "connected", data: {user_id, role, route_id}}  - Connection confirmed
    - {type: "error", data: {message: "..."}}  - Error message

    Messages from client:
    - {type: "send_message", data: {text: "...", message_type: "TEXT", reference: {...}}}
    - {type: "mark_read", data: {message_ids: [...]}}
    - {type: "ping"}  - Keepalive
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

    # Connect and register for chat
    db = next(get_db())
    try:
        # Verify route exists and user has access
        route = db.query(Route).filter(Route.id == route_id).first()
        if not route:
            await websocket.close(code=4004, reason="Route not found")
            return

        # Authorization
        if role != "admin" and route.merchandiser_id != user_id:
            await websocket.close(code=4003, reason="Access denied")
            return

        # Connect to chat
        await manager.connect_chat(
            websocket=websocket,
            user_id=user_id,
            role=role,
            route_id=route_id,
        )

        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "data": {"user_id": user_id, "role": role, "route_id": route_id}
        })

        # Sync missed messages if reconnecting
        if last_message_id is not None:
            missed = db.query(ChatMessage).filter(
                and_(
                    ChatMessage.route_id == route_id,
                    ChatMessage.id > last_message_id,
                )
            ).order_by(ChatMessage.id).limit(100).all()

            if missed:
                await websocket.send_json({
                    "type": "chat_sync",
                    "data": {
                        "messages": [_chat_message_to_dict(m) for m in missed],
                        "count": len(missed),
                    }
                })
    finally:
        db.close()

    # Listen for client messages
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "send_message":
                # Handle sending message via WebSocket
                msg_data = data.get("data", {})
                db = next(get_db())
                try:
                    user = db.query(User).filter(User.id == user_id).first()

                    msg = ChatMessage(
                        route_id=route_id,
                        sender_user_id=user_id,
                        message_type=msg_data.get("message_type", "TEXT"),
                        text=msg_data.get("text", ""),
                    )

                    # Add reference if provided
                    ref = msg_data.get("reference")
                    if ref and msg.message_type == "TAGGED_REFERENCE":
                        msg.ref_visit_id = ref.get("visit_id")
                        msg.ref_store_id = ref.get("store_id")
                        msg.ref_store_name = ref.get("store_name")
                        msg.ref_photo_id = ref.get("photo_id")
                        msg.ref_photo_type = ref.get("photo_type")
                        msg.ref_gondola_group_id = ref.get("gondola_group_id")
                        msg.ref_photo_url = ref.get("photo_url")
                        if ref.get("captured_at"):
                            msg.ref_captured_at = datetime.fromisoformat(ref["captured_at"].replace("Z", "+00:00"))

                    # Add annotated reference if provided
                    ann_ref = msg_data.get("annotated_reference")
                    if ann_ref and msg.message_type == "ANNOTATED_REFERENCE":
                        msg.ref_annotation_id = ann_ref.get("annotation_id")
                        msg.ref_visit_id = ann_ref.get("visit_id")
                        msg.ref_store_id = ann_ref.get("store_id")
                        msg.ref_store_name = ann_ref.get("store_name")
                        msg.ref_photo_id = ann_ref.get("photo_id")
                        msg.ref_photo_type = ann_ref.get("photo_type")
                        msg.ref_gondola_group_id = ann_ref.get("gondola_group_id")
                        msg.ref_photo_url = ann_ref.get("original_photo_url")
                        msg.ref_annotation_preview_url = ann_ref.get("annotation_preview_url")
                        if ann_ref.get("captured_at"):
                            msg.ref_captured_at = datetime.fromisoformat(ann_ref["captured_at"].replace("Z", "+00:00"))

                    db.add(msg)
                    db.commit()
                    db.refresh(msg)

                    msg_dict = _chat_message_to_dict(msg, user)

                    # Broadcast to all route subscribers
                    await manager.broadcast_chat_to_route(route_id, msg_dict)

                finally:
                    db.close()

            elif msg_type == "mark_read":
                msg_ids = data.get("data", {}).get("message_ids", [])
                if msg_ids:
                    db = next(get_db())
                    try:
                        now = datetime.utcnow()
                        db.query(ChatMessage).filter(
                            and_(
                                ChatMessage.route_id == route_id,
                                ChatMessage.id.in_(msg_ids),
                                ChatMessage.sender_user_id != user_id,
                            )
                        ).update(
                            {"is_read": True, "read_at": now},
                            synchronize_session=False
                        )
                        db.commit()
                    finally:
                        db.close()

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect_chat(user_id, route_id)
