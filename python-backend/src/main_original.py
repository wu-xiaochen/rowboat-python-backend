import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import (
    Agent, CreateAgentRequest, UpdateAgentRequest, AgentResponse,
    Conversation, CreateConversationRequest, ConversationResponse,
    Message, SendMessageRequest, Tool, CreateToolRequest,
    Trigger, CreateTriggerRequest
)
try:
    from .crew_manager import agent_manager
except ImportError:
    from .crew_manager_simple import agent_manager
from .database import DatabaseManager
try:
    from .rag_manager import RAGManager
except ImportError:
    # Create a mock RAG manager if dependencies are not available
    class RAGManager:
        async def initialize(self):
            pass
        async def cleanup(self):
            pass
        async def add_documents(self, collection_name: str, documents: list):
            pass
        async def search_with_scores(self, collection_name: str, query: str, k: int = 5):
            return []
from .websocket_manager import WebSocketManager
from .config import settings
try:
    from .monitoring import metrics_collector, health_checker, get_metrics, get_system_metrics, monitor_request
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    # 创建mock函数
    class MockMetricsCollector:
        def record_request(self, *args): pass
        def record_llm_request(self, *args): pass
        def record_database_query(self, *args): pass
        def record_websocket_message(self, *args): pass
        def record_error(self, *args): pass

    class MockHealthChecker:
        def add_check(self, *args): pass
        async def check_all(self):
            return {'status': 'healthy', 'checks': {}, 'timestamp': datetime.utcnow().isoformat()}

    metrics_collector = MockMetricsCollector()
    health_checker = MockHealthChecker()
    def get_metrics(): return ""
    def get_system_metrics(): return {}
    def monitor_request(func): return func

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=settings.log_format
)

logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

# Global managers
db_manager = DatabaseManager()
rag_manager = RAGManager()
websocket_manager = WebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Rowboat Python Backend...")
    await db_manager.initialize()
    await rag_manager.initialize()
    await websocket_manager.initialize()

    yield

    # Shutdown
    logger.info("Shutting down Rowboat Python Backend...")
    await db_manager.cleanup()
    await rag_manager.cleanup()
    await websocket_manager.cleanup()


# Create FastAPI app
app = FastAPI(
    title="Rowboat API",
    description="Python backend for Rowboat - AI Agent Management Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    # Implement JWT validation here
    # For now, return a mock user
    return {"id": "user_123", "email": "user@example.com"}


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if MONITORING_AVAILABLE:
        # 执行详细的健康检查
        health_status = await health_checker.check_all()
        return health_status
    else:
        return {
            "status": "healthy",
            "service": "rowboat-python-backend",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat()
        }

# 系统指标端点
@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus指标端点"""
    if MONITORING_AVAILABLE:
        from fastapi.responses import PlainTextResponse
        metrics_data = get_metrics()
        return PlainTextResponse(content=metrics_data, media_type="text/plain")
    else:
        return {"error": "Monitoring not available"}

# 系统状态端点
@app.get("/system")
async def system_status():
    """系统状态端点"""
    if MONITORING_AVAILABLE:
        system_metrics = get_system_metrics()
        return system_metrics
    else:
        return {"error": "System monitoring not available"}


# Agent endpoints
@app.post("/api/agents", response_model=AgentResponse)
async def create_agent(
    agent_request: CreateAgentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new agent"""
    try:
        # Create agent in database
        agent = await db_manager.create_agent(agent_request, current_user["id"])

        # Create CrewAI agent
        await agent_manager.create_agent(agent)

        logger.info(f"Agent created: {agent.name} by user {current_user['id']}")
        return AgentResponse(agent=agent)

    except Exception as e:
        logger.error(f"Failed to create agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


@app.get("/api/agents", response_model=List[Agent])
async def list_agents(
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """List all agents for the current user"""
    try:
        agents = await db_manager.list_agents(current_user["id"], skip, limit)
        return agents

    except Exception as e:
        logger.error(f"Failed to list agents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")


@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific agent"""
    try:
        agent = await db_manager.get_agent(agent_id, current_user["id"])
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        return AgentResponse(agent=agent)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")


@app.put("/api/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_update: UpdateAgentRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update an agent"""
    try:
        agent = await db_manager.update_agent(agent_id, current_user["id"], agent_update)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Update CrewAI agent configuration
        await agent_manager.update_agent_config(agent_id, agent_update.dict(exclude_unset=True))

        logger.info(f"Agent updated: {agent_id} by user {current_user['id']}")
        return AgentResponse(agent=agent)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")


@app.delete("/api/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete an agent"""
    try:
        success = await db_manager.delete_agent(agent_id, current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Remove CrewAI agent
        await agent_manager.remove_agent(agent_id)

        logger.info(f"Agent deleted: {agent_id} by user {current_user['id']}")
        return {"success": True, "message": "Agent deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")


# Conversation endpoints
@app.post("/api/conversations", response_model=ConversationResponse)
async def create_conversation(
    conversation_request: CreateConversationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new conversation"""
    try:
        conversation = await db_manager.create_conversation(conversation_request, current_user["id"])

        logger.info(f"Conversation created: {conversation.id} by user {current_user['id']}")
        return ConversationResponse(conversation=conversation)

    except Exception as e:
        logger.error(f"Failed to create conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")


@app.get("/api/conversations", response_model=List[Conversation])
async def list_conversations(
    agent_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """List conversations for the current user"""
    try:
        conversations = await db_manager.list_conversations(
            current_user["id"], agent_id, skip, limit
        )
        return conversations

    except Exception as e:
        logger.error(f"Failed to list conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@app.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific conversation with messages"""
    try:
        conversation = await db_manager.get_conversation(conversation_id, current_user["id"])
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = await db_manager.get_conversation_messages(conversation_id)

        return ConversationResponse(conversation=conversation, messages=messages)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation: {str(e)}")


@app.post("/api/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    message_request: SendMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Send a message in a conversation"""
    try:
        # Get conversation
        conversation = await db_manager.get_conversation(conversation_id, current_user["id"])
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Save user message
        user_message = await db_manager.create_message(
            conversation_id, message_request.content, "user", message_request.metadata
        )

        # Process with agent
        response_content = await agent_manager.process_conversation_message(
            conversation, user_message
        )

        # Save agent response
        agent_message = await db_manager.create_message(
            conversation_id, response_content, "assistant"
        )

        # Update conversation
        await db_manager.update_conversation_timestamp(conversation_id)

        logger.info(f"Message processed in conversation {conversation_id}")

        return {
            "success": True,
            "message": "Message processed successfully",
            "response": response_content
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process message in conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")


# Copilot endpoint
@app.post("/api/copilot")
async def copilot_assist(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """Get assistance from the Rowboat copilot"""
    try:
        user_input = request.get("input", "")
        context = request.get("context", {})

        if not user_input:
            raise HTTPException(status_code=400, detail="Input is required")

        response = await agent_manager.copilot_assist(user_input, context)

        logger.info(f"Copilot assistance provided to user {current_user['id']}")

        return {
            "success": True,
            "response": response,
            "message": "Copilot assistance completed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Copilot assistance failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Copilot assistance failed: {str(e)}")


# WebSocket endpoint for real-time communication
@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str
):
    """WebSocket endpoint for real-time conversation"""
    await websocket_manager.connect(websocket, conversation_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            # Process message (similar to HTTP endpoint but via WebSocket)
            # This is a simplified implementation
            message_content = data.get("content", "")

            if message_content:
                # Get conversation and process message
                conversation = await db_manager.get_conversation(conversation_id)
                if conversation:
                    # Create message
                    message = await db_manager.create_message(
                        conversation_id, message_content, "user"
                    )

                    # Process with agent
                    response = await agent_manager.process_conversation_message(
                        conversation, message
                    )

                    # Send response back via WebSocket
                    await websocket.send_json({
                        "type": "response",
                        "content": response,
                        "timestamp": datetime.utcnow().isoformat()
                    })

    except WebSocketDisconnect:
        websocket_manager.disconnect(conversation_id)
    except Exception as e:
        logger.error(f"WebSocket error in conversation {conversation_id}: {str(e)}")
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    from datetime import datetime

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )