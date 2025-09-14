"""WebSocket handler for real-time communication."""

import json
import asyncio
from typing import Dict, Set, Optional, Any, List
from datetime import datetime
import logging
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from jose import JWTError, jwt
import redis.asyncio as redis

from .config import settings
from .auth import verify_token, get_user_by_email
from .database import get_async_db
from .models import User
from .conversation_service import conversation_service

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        # Active connections: user_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Connection metadata: websocket -> user info
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}
        # Redis client for pub/sub
        self.redis_client: Optional[redis.Redis] = None

    async def initialize_redis(self):
        """Initialize Redis connection for pub/sub."""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis connection established for WebSocket")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    async def connect(self, websocket: WebSocket, user: User):
        """Accept a WebSocket connection."""
        await websocket.accept()

        user_id = str(user.id)
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)
        self.connection_info[websocket] = {
            "user_id": user_id,
            "user_email": user.email,
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow()
        }

        # Send connection confirmation
        await self.send_personal_message({
            "type": "connection",
            "status": "connected",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)

        logger.info(f"User {user.email} connected via WebSocket")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.connection_info:
            user_id = self.connection_info[websocket]["user_id"]
            user_email = self.connection_info[websocket]["user_email"]

            # Remove from active connections
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]

            # Remove connection info
            del self.connection_info[websocket]

            logger.info(f"User {user_email} disconnected from WebSocket")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")
            # Remove disconnected websocket
            self.disconnect(websocket)

    async def send_user_message(self, message: Dict[str, Any], user_id: str):
        """Send a message to all connections for a specific user."""
        if user_id in self.active_connections:
            disconnected_sockets = []

            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")
                    disconnected_sockets.append(websocket)

            # Clean up disconnected sockets
            for socket in disconnected_sockets:
                self.disconnect(socket)

    async def broadcast_message(self, message: Dict[str, Any], exclude_user: Optional[str] = None):
        """Broadcast a message to all connected users."""
        for user_id, connections in self.active_connections.items():
            if exclude_user and user_id == exclude_user:
                continue

            disconnected_sockets = []
            for websocket in connections:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error broadcasting to user {user_id}: {e}")
                    disconnected_sockets.append(websocket)

            # Clean up disconnected sockets
            for socket in disconnected_sockets:
                self.disconnect(socket)

    async def send_typing_indicator(self, user_id: str, conversation_id: str, is_typing: bool):
        """Send typing indicator to user."""
        message = {
            "type": "typing",
            "conversation_id": conversation_id,
            "is_typing": is_typing,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_user_message(message, user_id)

    async def send_conversation_update(self, user_id: str, conversation_id: str, update_type: str, data: Dict[str, Any]):
        """Send conversation update to user."""
        message = {
            "type": "conversation_update",
            "conversation_id": conversation_id,
            "update_type": update_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_user_message(message, user_id)

    def get_connected_users(self) -> List[str]:
        """Get list of currently connected user IDs."""
        return list(self.active_connections.keys())

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(connections) for connections in self.active_connections.values())

    async def ping_all_connections(self):
        """Send ping to all connections to keep them alive."""
        ping_message = {
            "type": "ping",
            "timestamp": datetime.utcnow().isoformat()
        }

        all_connections = []
        for connections in self.active_connections.values():
            all_connections.extend(connections)

        disconnected_sockets = []
        for websocket in all_connections:
            try:
                await websocket.send_text(json.dumps(ping_message))
                # Update last ping time
                if websocket in self.connection_info:
                    self.connection_info[websocket]["last_ping"] = datetime.utcnow()
            except Exception as e:
                logger.error(f"Error pinging connection: {e}")
                disconnected_sockets.append(websocket)

        # Clean up disconnected sockets
        for socket in disconnected_sockets:
            self.disconnect(socket)


# Global connection manager
manager = ConnectionManager()


async def authenticate_websocket(websocket: WebSocket, token: str, db) -> Optional[User]:
    """Authenticate WebSocket connection using JWT token."""
    try:
        # Verify token
        token_data = verify_token(token)
        if not token_data:
            return None

        # Get user
        user = get_user_by_email(db, email=token_data["username"])
        if not user or not user.is_active:
            return None

        return user

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        return None


async def websocket_endpoint(websocket: WebSocket, token: str, db = Depends(get_async_db)):
    """Main WebSocket endpoint."""
    # Authenticate user
    user = await authenticate_websocket(websocket, token, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Connect user
    await manager.connect(websocket, user)

    try:
        # Message handling loop
        while True:
            # Receive message
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                await handle_websocket_message(websocket, message, user, db)
            except json.JSONDecodeError:
                await manager.send_personal_message({
                    "type": "error",
                    "error": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                }, websocket)
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await manager.send_personal_message({
                    "type": "error",
                    "error": "Internal server error",
                    "timestamp": datetime.utcnow().isoformat()
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def handle_websocket_message(websocket: WebSocket, message: Dict[str, Any], user: User, db):
    """Handle incoming WebSocket messages."""
    message_type = message.get("type")
    user_id = str(user.id)

    if message_type == "ping":
        # Respond to ping
        await manager.send_personal_message({
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)

    elif message_type == "conversation_message":
        # Handle conversation message
        conversation_id = message.get("conversation_id")
        user_message = message.get("message")
        stream = message.get("stream", False)

        if not conversation_id or not user_message:
            await manager.send_personal_message({
                "type": "error",
                "error": "Missing conversation_id or message",
                "timestamp": datetime.utcnow().isoformat()
            }, websocket)
            return

        try:
            # Send typing indicator
            await manager.send_typing_indicator(user_id, conversation_id, True)

            if stream:
                # Handle streaming response
                response_generator = await conversation_service.generate_response(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    user_message=user_message,
                    stream=True
                )

                async for chunk in response_generator:
                    await manager.send_personal_message({
                        "type": "conversation_stream",
                        "conversation_id": conversation_id,
                        **chunk,
                        "timestamp": datetime.utcnow().isoformat()
                    }, websocket)

            else:
                # Handle single response
                response = await conversation_service.generate_response(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    user_message=user_message,
                    stream=False
                )

                await manager.send_personal_message({
                    "type": "conversation_response",
                    "conversation_id": conversation_id,
                    **response,
                    "timestamp": datetime.utcnow().isoformat()
                }, websocket)

            # Stop typing indicator
            await manager.send_typing_indicator(user_id, conversation_id, False)

        except Exception as e:
            logger.error(f"Error processing conversation message: {e}")
            await manager.send_personal_message({
                "type": "error",
                "error": f"Failed to process message: {str(e)}",
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat()
            }, websocket)

            # Stop typing indicator
            await manager.send_typing_indicator(user_id, conversation_id, False)

    elif message_type == "typing":
        # Handle typing indicator
        conversation_id = message.get("conversation_id")
        is_typing = message.get("is_typing", False)

        if conversation_id:
            await manager.send_typing_indicator(user_id, conversation_id, is_typing)

    elif message_type == "join_conversation":
        # Join a conversation (for future multi-user support)
        conversation_id = message.get("conversation_id")
        if conversation_id:
            await manager.send_personal_message({
                "type": "joined_conversation",
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat()
            }, websocket)

    elif message_type == "leave_conversation":
        # Leave a conversation
        conversation_id = message.get("conversation_id")
        if conversation_id:
            await manager.send_personal_message({
                "type": "left_conversation",
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat()
            }, websocket)

    else:
        await manager.send_personal_message({
            "type": "error",
            "error": f"Unknown message type: {message_type}",
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)


# Background task for connection maintenance
async def websocket_maintenance_task():
    """Background task to maintain WebSocket connections."""
    while True:
        try:
            # Send ping to all connections every 30 seconds
            await manager.ping_all_connections()
            await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)
        except Exception as e:
            logger.error(f"WebSocket maintenance error: {e}")
            await asyncio.sleep(10)


# Startup function
async def init_websocket():
    """Initialize WebSocket manager."""
    await manager.initialize_redis()

    # Start maintenance task
    asyncio.create_task(websocket_maintenance_task())