import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for real-time communication
    """

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.connection_metadata: Dict[WebSocket, dict] = {}

    async def initialize(self):
        """Initialize WebSocket manager"""
        logger.info("WebSocket manager initialized")

    async def cleanup(self):
        """Cleanup WebSocket connections"""
        # Close all active connections
        for connections in self.active_connections.values():
            for websocket in connections:
                try:
                    await websocket.close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket: {str(e)}")

        self.active_connections.clear()
        self.connection_metadata.clear()
        logger.info("WebSocket manager cleaned up")

    async def connect(self, websocket: WebSocket, conversation_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()

        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []

        self.active_connections[conversation_id].append(websocket)
        self.connection_metadata[websocket] = {
            "conversation_id": conversation_id,
            "connected_at": datetime.utcnow().isoformat()
        }

        logger.info(f"WebSocket connected to conversation {conversation_id}")

        # Send connection confirmation
        await self.send_personal_message(
            websocket,
            {
                "type": "connection",
                "status": "connected",
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    def disconnect(self, conversation_id: str, websocket: Optional[WebSocket] = None):
        """Disconnect a WebSocket connection"""
        if conversation_id in self.active_connections:
            if websocket:
                # Remove specific connection
                if websocket in self.active_connections[conversation_id]:
                    self.active_connections[conversation_id].remove(websocket)
                    if websocket in self.connection_metadata:
                        del self.connection_metadata[websocket]

                # Clean up empty conversation groups
                if not self.active_connections[conversation_id]:
                    del self.active_connections[conversation_id]
            else:
                # Remove all connections for this conversation
                for ws in self.active_connections[conversation_id]:
                    if ws in self.connection_metadata:
                        del self.connection_metadata[ws]
                del self.active_connections[conversation_id]

        logger.info(f"WebSocket disconnected from conversation {conversation_id}")

    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {str(e)}")
            # Remove broken connection
            for conversation_id, connections in self.active_connections.items():
                if websocket in connections:
                    self.disconnect(conversation_id, websocket)
                    break

    async def send_conversation_message(self, conversation_id: str, message: dict, exclude: Optional[WebSocket] = None):
        """Send a message to all connections in a conversation"""
        if conversation_id in self.active_connections:
            disconnected_connections = []

            for websocket in self.active_connections[conversation_id]:
                if websocket != exclude:
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.error(f"Failed to send message to WebSocket: {str(e)}")
                        disconnected_connections.append(websocket)

            # Clean up disconnected connections
            for websocket in disconnected_connections:
                self.disconnect(conversation_id, websocket)

    async def broadcast_message(self, message: dict):
        """Broadcast a message to all connected WebSockets"""
        disconnected_connections = []

        for conversation_id, connections in self.active_connections.items():
            for websocket in connections:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast message: {str(e)}")
                    disconnected_connections.append((conversation_id, websocket))

        # Clean up disconnected connections
        for conversation_id, websocket in disconnected_connections:
            self.disconnect(conversation_id, websocket)

    def get_connection_count(self, conversation_id: Optional[str] = None) -> int:
        """Get the number of active connections"""
        if conversation_id:
            return len(self.active_connections.get(conversation_id, []))
        else:
            return sum(len(connections) for connections in self.active_connections.values())

    def get_active_conversations(self) -> List[str]:
        """Get list of conversation IDs with active connections"""
        return list(self.active_connections.keys())

    async def handle_agent_response(self, conversation_id: str, response_data: dict):
        """Handle and broadcast agent responses"""
        message = {
            "type": "agent_response",
            "data": response_data,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.send_conversation_message(conversation_id, message)

    async def handle_conversation_update(self, conversation_id: str, update_data: dict):
        """Handle and broadcast conversation updates"""
        message = {
            "type": "conversation_update",
            "data": update_data,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.send_conversation_message(conversation_id, message)

    async def handle_typing_indicator(self, conversation_id: str, user_id: str, is_typing: bool):
        """Handle typing indicators"""
        message = {
            "type": "typing_indicator",
            "user_id": user_id,
            "is_typing": is_typing,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.send_conversation_message(conversation_id, message)

    async def handle_error(self, websocket: WebSocket, error_message: str):
        """Handle and send error messages"""
        error_data = {
            "type": "error",
            "message": error_message,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            await websocket.send_json(error_data)
        except Exception as e:
            logger.error(f"Failed to send error message: {str(e)}")

    async def ping_connections(self):
        """Send ping messages to keep connections alive"""
        while True:
            try:
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.utcnow().isoformat()
                }

                await self.broadcast_message(ping_message)
                await asyncio.sleep(30)  # Ping every 30 seconds

            except Exception as e:
                logger.error(f"Error in ping task: {str(e)}")
                await asyncio.sleep(30)

    def start_ping_task(self):
        """Start the ping task"""
        asyncio.create_task(self.ping_connections())

    async def send_progress_update(self, conversation_id: str, progress_data: dict):
        """Send progress updates for long-running tasks"""
        message = {
            "type": "progress_update",
            "data": progress_data,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.send_conversation_message(conversation_id, message)

    async def send_tool_execution(self, conversation_id: str, tool_data: dict):
        """Send tool execution updates"""
        message = {
            "type": "tool_execution",
            "data": tool_data,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.send_conversation_message(conversation_id, message)

    async def send_agent_status(self, conversation_id: str, agent_id: str, status: str, details: dict = None):
        """Send agent status updates"""
        message = {
            "type": "agent_status",
            "agent_id": agent_id,
            "status": status,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.send_conversation_message(conversation_id, message)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()