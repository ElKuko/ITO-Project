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


class ConnectionManager:
    """Manages WebSocket connections for real-time notifications."""

    def __init__(self):
        # Map of user_id -> ConnectedClient
        self.active_connections: Dict[int, ConnectedClient] = {}
        # Index by route for efficient broadcasting
        self._route_subscribers: Dict[int, Set[int]] = {}  # route_id -> set of user_ids
        # Admins who see all routes
        self._admin_connections: Set[int] = set()  # user_ids of admins

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


# Global connection manager instance
manager = ConnectionManager()
