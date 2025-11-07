from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUILDING = "building"
    ERROR = "error"


class AgentType(str, Enum):
    CUSTOM = "custom"
    TEMPLATE = "template"
    COPILOT = "copilot"


class ToolType(str, Enum):
    API = "api"
    DATABASE = "database"
    FILE = "file"
    WEBHOOK = "webhook"
    MCP = "mcp"


class TriggerType(str, Enum):
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"
    MANUAL = "manual"


# Base Models
class AgentBase(BaseModel):
    name: str = Field(..., description="Name of the agent")
    description: Optional[str] = Field(None, description="Description of the agent")
    agent_type: AgentType = Field(AgentType.CUSTOM, description="Type of agent")
    config: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration")
    tools: List[str] = Field(default_factory=list, description="List of tool IDs")
    triggers: List[str] = Field(default_factory=list, description="List of trigger IDs")
    rag_enabled: bool = Field(False, description="Whether RAG is enabled")
    rag_sources: List[str] = Field(default_factory=list, description="RAG source IDs")


class Agent(AgentBase):
    id: str = Field(..., description="Unique identifier")
    status: AgentStatus = Field(AgentStatus.INACTIVE, description="Agent status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_run: Optional[datetime] = Field(None, description="Last execution timestamp")
    run_count: int = Field(0, description="Number of times executed")


class ToolBase(BaseModel):
    name: str = Field(..., description="Name of the tool")
    description: Optional[str] = Field(None, description="Description of the tool")
    tool_type: ToolType = Field(..., description="Type of tool")
    config: Dict[str, Any] = Field(..., description="Tool configuration")
    enabled: bool = Field(True, description="Whether the tool is enabled")


class Tool(ToolBase):
    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    usage_count: int = Field(0, description="Number of times used")


class TriggerBase(BaseModel):
    name: str = Field(..., description="Name of the trigger")
    description: Optional[str] = Field(None, description="Description of the trigger")
    trigger_type: TriggerType = Field(..., description="Type of trigger")
    config: Dict[str, Any] = Field(..., description="Trigger configuration")
    enabled: bool = Field(True, description="Whether the trigger is enabled")
    agent_id: str = Field(..., description="ID of the agent to trigger")


class Trigger(TriggerBase):
    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_triggered: Optional[datetime] = Field(None, description="Last trigger timestamp")
    trigger_count: int = Field(0, description="Number of times triggered")


class ConversationBase(BaseModel):
    agent_id: str = Field(..., description="ID of the agent")
    user_id: str = Field(..., description="ID of the user")
    title: Optional[str] = Field(None, description="Conversation title")
    context: Dict[str, Any] = Field(default_factory=dict, description="Conversation context")


class Conversation(ConversationBase):
    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(0, description="Number of messages")


class MessageBase(BaseModel):
    conversation_id: str = Field(..., description="ID of the conversation")
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Message metadata")


class Message(MessageBase):
    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")


# Request/Response Models
class CreateAgentRequest(AgentBase):
    pass


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    tools: Optional[List[str]] = None
    triggers: Optional[List[str]] = None
    rag_enabled: Optional[bool] = None
    rag_sources: Optional[List[str]] = None


class CreateToolRequest(ToolBase):
    pass


class CreateTriggerRequest(TriggerBase):
    pass


class CreateConversationRequest(ConversationBase):
    pass


class SendMessageRequest(BaseModel):
    content: str = Field(..., description="Message content")
    role: str = Field("user", description="Message role")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Message metadata")


class AgentResponse(BaseModel):
    agent: Agent
    success: bool = True
    message: str = "Success"


class ConversationResponse(BaseModel):
    conversation: Conversation
    messages: List[Message] = []
    success: bool = True
    message: str = "Success"