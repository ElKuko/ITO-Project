"""WebSocket connection manager for real-time notifications."""

import json
from typing import Dict, List, Optional, Set
from fastapi import WebSocket
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConnectedClient:
    """Represents a connected WebSocket client."""
    websocket: WebSocket
    user_id: int
    role: str
    subscribed_routes: Set[int] = field(default_factory=set)  # Empty = all routes (admin)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_event_id: Optional[int] = None  # For sync on reconnect


@dataclass
class ChatClient:
    """Represents a connected chat WebSocket client."""
    websocket: WebSocket
    user_id: int
    role: str
    route_id: int
    connected_at: datetime = field(default_factory=datetime.utcnow)


class ConnectionManager:
    """Manages WebSocket connections for real-time notifications and chat."""

    def __init__(self):
        # Map of user_id -> ConnectedClient (notifications)
        self.active_connections: Dict[int, ConnectedClient] = {}
        # Index by route for efficient broadcasting
        self._route_subscribers: Dict[int, Set[int]] = {}  # route_id -> set of user_ids
        # Admins who see all routes
        self._admin_connections: Set[int] = set()  # user_ids of admins

        # Chat connections: route_id -> {user_id -> ChatClient}
        self._chat_connections: Dict[int, Dict[int, ChatClient]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
        role: str,
        subscribed_routes: Optional[List[int]] = None,
        last_event_id: Optional[int] = None
    ) -> ConnectedClient:
        """Accept a new WebSocket connection."""
        await websocket.accept()

        # Disconnect existing connection for this user if any
        if user_id in self.active_connections:
            await self.disconnect(user_id)

        client = ConnectedClient(
            websocket=websocket,
            user_id=user_id,
            role=role,
            subscribed_routes=set(subscribed_routes) if subscribed_routes else set(),
            last_event_id=last_event_id
        )
        self.active_connections[user_id] = client

        # Track admin connections
        if role == "admin":
            self._admin_connections.add(user_id)

        # Track route subscriptions
        if subscribed_routes:
            for route_id in subscribed_routes:
                if route_id not in self._route_subscribers:
                    self._route_subscribers[route_id] = set()
                self._route_subscribers[route_id].add(user_id)

        return client

    async def disconnect(self, user_id: int):
        """Remove a WebSocket connection."""
        if user_id not in self.active_connections:
            return

        client = self.active_connections[user_id]

        # Clean up route subscriptions
        for route_id in client.subscribed_routes:
            if route_id in self._route_subscribers:
                self._route_subscribers[route_id].discard(user_id)
                if not self._route_subscribers[route_id]:
                    del self._route_subscribers[route_id]

        # Remove from admin set
        self._admin_connections.discard(user_id)

        # Close the websocket if still open
        try:
            await client.websocket.close()
        except Exception:
            pass  # Already closed

        del self.active_connections[user_id]

    async def send_notification(self, user_id: int, notification: dict):
        """Send a notification to a specific user."""
        if user_id not in self.active_connections:
            return False

        client = self.active_connections[user_id]
        try:
            message = {
                "type": "notification",
                "data": notification
            }
            await client.websocket.send_json(message)
            return True
        except Exception:
            # Connection broken, clean up
            await self.disconnect(user_id)
            return False

    async def broadcast_to_route(self, route_id: Optional[int], notification: dict):
        """
        Broadcast a notification to all subscribers of a route.
        Also sends to all admins (who see all routes).
        """
        recipients: Set[int] = set()

        # Add admins (they see all routes)
        recipients.update(self._admin_connections)

        # Add specific route subscribers
        if route_id and route_id in self._route_subscribers:
            recipients.update(self._route_subscribers[route_id])

        # Send to all recipients
        failed_users = []
        for user_id in recipients:
            success = await self.send_notification(user_id, notification)
            if not success:
                failed_users.append(user_id)

        return len(recipients) - len(failed_users)

    async def broadcast_to_all(self, notification: dict):
        """Broadcast a notification to all connected clients."""
        failed_users = []
        for user_id in list(self.active_connections.keys()):
            success = await self.send_notification(user_id, notification)
            if not success:
                failed_users.append(user_id)

        return len(self.active_connections) - len(failed_users)

    async def send_sync_message(self, user_id: int, notifications: list):
        """Send missed notifications on reconnect."""
        if user_id not in self.active_connections:
            return False

        client = self.active_connections[user_id]
        try:
            message = {
                "type": "sync",
                "data": {
                    "notifications": notifications,
                    "count": len(notifications)
                }
            }
            await client.websocket.send_json(message)
            return True
        except Exception:
            await self.disconnect(user_id)
            return False

    async def send_error(self, user_id: int, error_message: str):
        """Send an error message to a specific user."""
        if user_id not in self.active_connections:
            return False

        client = self.active_connections[user_id]
        try:
            message = {
                "type": "error",
                "data": {"message": error_message}
            }
            await client.websocket.send_json(message)
            return True
        except Exception:
            await self.disconnect(user_id)
            return False

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self.active_connections)

    def get_admin_connection_count(self) -> int:
        """Get number of connected admins."""
        return len(self._admin_connections)

    def is_connected(self, user_id: int) -> bool:
        """Check if a user is connected."""
        return user_id in self.active_connections

    # ── Chat Connection Methods ──────────────────────────────────────────────

    async def connect_chat(
        self,
        websocket: WebSocket,
        user_id: int,
        role: str,
        route_id: int,
    ) -> ChatClient:
        """Accept a new chat WebSocket connection for a specific route."""
        await websocket.accept()

        # Initialize route chat connections if needed
        if route_id not in self._chat_connections:
            self._chat_connections[route_id] = {}

        # Disconnect existing chat connection for this user on this route
        if user_id in self._chat_connections[route_id]:
            await self.disconnect_chat(user_id, route_id)

        client = ChatClient(
            websocket=websocket,
            user_id=user_id,
            role=role,
            route_id=route_id,
        )
        self._chat_connections[route_id][user_id] = client

        return client

    async def disconnect_chat(self, user_id: int, route_id: int):
        """Remove a chat WebSocket connection."""
        if route_id not in self._chat_connections:
            return

        if user_id not in self._chat_connections[route_id]:
            return

        client = self._chat_connections[route_id][user_id]

        # Close the websocket if still open
        try:
            await client.websocket.close()
        except Exception:
            pass  # Already closed

        del self._chat_connections[route_id][user_id]

        # Clean up empty route dict
        if not self._chat_connections[route_id]:
            del self._chat_connections[route_id]

    async def send_chat_message(self, user_id: int, route_id: int, message: dict):
        """Send a chat message to a specific user on a route."""
        if route_id not in self._chat_connections:
            return False

        if user_id not in self._chat_connections[route_id]:
            return False

        client = self._chat_connections[route_id][user_id]
        try:
            await client.websocket.send_json({
                "type": "chat_message",
                "data": message
            })
            return True
        except Exception:
            # Connection broken, clean up
            await self.disconnect_chat(user_id, route_id)
            return False

    async def broadcast_chat_to_route(self, route_id: int, message: dict):
        """Broadcast a chat message to all users connected to a route's chat."""
        if route_id not in self._chat_connections:
            return 0

        sent_count = 0
        failed_users = []

        for user_id in list(self._chat_connections[route_id].keys()):
            success = await self.send_chat_message(user_id, route_id, message)
            if success:
                sent_count += 1
            else:
                failed_users.append(user_id)

        return sent_count

    def get_chat_connection_count(self, route_id: int) -> int:
        """Get number of users connected to a route's chat."""
        if route_id not in self._chat_connections:
            return 0
        return len(self._chat_connections[route_id])

    def is_chat_connected(self, user_id: int, route_id: int) -> bool:
        """Check if a user is connected to a route's chat."""
        if route_id not in self._chat_connections:
            return False
        return user_id in self._chat_connections[route_id]


# Global connection manager instance
manager = ConnectionManager()
