import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func

from .models import (
    Agent as AgentModel, CreateAgentRequest, UpdateAgentRequest,
    Conversation as ConversationModel, CreateConversationRequest,
    Message as MessageModel, Tool as ToolModel, CreateToolRequest,
    Trigger as TriggerModel, CreateTriggerRequest, AgentStatus
)
from .config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    agent_type = Column(String, nullable=False, default="custom")
    config = Column(JSON, default=dict)
    tools = Column(JSON, default=list)
    triggers = Column(JSON, default=list)
    rag_enabled = Column(Boolean, default=False)
    rag_sources = Column(JSON, default=list)
    status = Column(String, default=AgentStatus.INACTIVE)
    user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_run = Column(DateTime)
    run_count = Column(Integer, default=0)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String)
    context = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    message_count = Column(Integer, default=0)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    message_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())


class Tool(Base):
    __tablename__ = "tools"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    tool_type = Column(String, nullable=False)
    config = Column(JSON, nullable=False)
    enabled = Column(Boolean, default=True)
    user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    usage_count = Column(Integer, default=0)


class Trigger(Base):
    __tablename__ = "triggers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    trigger_type = Column(String, nullable=False)
    config = Column(JSON, nullable=False)
    enabled = Column(Boolean, default=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_triggered = Column(DateTime)
    trigger_count = Column(Integer, default=0)


class DatabaseManager:
    """Manages database operations"""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None

    async def initialize(self):
        """Initialize database connection"""
        try:
            self.engine = create_engine(settings.database_url)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

            # Create tables
            Base.metadata.create_all(bind=self.engine)

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise

    async def cleanup(self):
        """Cleanup database connections"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")

    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()

    async def create_agent(self, agent_request: CreateAgentRequest, user_id: str) -> AgentModel:
        """Create a new agent"""
        with self.get_session() as session:
            try:
                agent = Agent(
                    id=str(uuid.uuid4()),
                    name=agent_request.name,
                    description=agent_request.description,
                    agent_type=agent_request.agent_type,
                    config=agent_request.config,
                    tools=agent_request.tools,
                    triggers=agent_request.triggers,
                    rag_enabled=agent_request.rag_enabled,
                    rag_sources=agent_request.rag_sources,
                    status=AgentStatus.INACTIVE,
                    user_id=user_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                session.add(agent)
                session.commit()
                session.refresh(agent)

                return self._agent_to_model(agent)

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to create agent: {str(e)}")
                raise

    async def get_agent(self, agent_id: str, user_id: str) -> Optional[AgentModel]:
        """Get an agent by ID"""
        with self.get_session() as session:
            try:
                agent = session.query(Agent).filter(
                    Agent.id == agent_id,
                    Agent.user_id == user_id
                ).first()

                return self._agent_to_model(agent) if agent else None

            except Exception as e:
                logger.error(f"Failed to get agent {agent_id}: {str(e)}")
                raise

    async def list_agents(self, user_id: str, skip: int = 0, limit: int = 100) -> List[AgentModel]:
        """List agents for a user"""
        with self.get_session() as session:
            try:
                agents = session.query(Agent).filter(
                    Agent.user_id == user_id
                ).offset(skip).limit(limit).all()

                return [self._agent_to_model(agent) for agent in agents]

            except Exception as e:
                logger.error(f"Failed to list agents for user {user_id}: {str(e)}")
                raise

    async def update_agent(self, agent_id: str, user_id: str, update: UpdateAgentRequest) -> Optional[AgentModel]:
        """Update an agent"""
        with self.get_session() as session:
            try:
                agent = session.query(Agent).filter(
                    Agent.id == agent_id,
                    Agent.user_id == user_id
                ).first()

                if not agent:
                    return None

                # Update fields
                update_data = update.dict(exclude_unset=True)
                for field, value in update_data.items():
                    if hasattr(agent, field):
                        setattr(agent, field, value)

                agent.updated_at = datetime.utcnow()

                session.commit()
                session.refresh(agent)

                return self._agent_to_model(agent)

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update agent {agent_id}: {str(e)}")
                raise

    async def delete_agent(self, agent_id: str, user_id: str) -> bool:
        """Delete an agent"""
        with self.get_session() as session:
            try:
                agent = session.query(Agent).filter(
                    Agent.id == agent_id,
                    Agent.user_id == user_id
                ).first()

                if not agent:
                    return False

                session.delete(agent)
                session.commit()

                return True

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to delete agent {agent_id}: {str(e)}")
                raise

    async def create_conversation(self, conversation_request: CreateConversationRequest, user_id: str) -> ConversationModel:
        """Create a new conversation"""
        with self.get_session() as session:
            try:
                conversation = Conversation(
                    id=str(uuid.uuid4()),
                    agent_id=conversation_request.agent_id,
                    user_id=user_id,
                    title=conversation_request.title,
                    context=conversation_request.context,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                session.add(conversation)
                session.commit()
                session.refresh(conversation)

                return self._conversation_to_model(conversation)

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to create conversation: {str(e)}")
                raise

    async def get_conversation(self, conversation_id: str, user_id: str) -> Optional[ConversationModel]:
        """Get a conversation by ID"""
        with self.get_session() as session:
            try:
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id
                ).first()

                return self._conversation_to_model(conversation) if conversation else None

            except Exception as e:
                logger.error(f"Failed to get conversation {conversation_id}: {str(e)}")
                raise

    async def list_conversations(self, user_id: str, agent_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[ConversationModel]:
        """List conversations for a user"""
        with self.get_session() as session:
            try:
                query = session.query(Conversation).filter(Conversation.user_id == user_id)

                if agent_id:
                    query = query.filter(Conversation.agent_id == agent_id)

                conversations = query.offset(skip).limit(limit).all()

                return [self._conversation_to_model(conv) for conv in conversations]

            except Exception as e:
                logger.error(f"Failed to list conversations for user {user_id}: {str(e)}")
                raise

    async def update_conversation_timestamp(self, conversation_id: str) -> bool:
        """Update conversation timestamp"""
        with self.get_session() as session:
            try:
                conversation = session.query(Conversation).filter(
                    Conversation.id == conversation_id
                ).first()

                if not conversation:
                    return False

                conversation.updated_at = datetime.utcnow()
                conversation.message_count += 1

                session.commit()
                return True

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update conversation {conversation_id}: {str(e)}")
                raise

    async def create_message(self, conversation_id: str, content: str, role: str, metadata: Dict[str, Any] = None) -> MessageModel:
        """Create a new message"""
        with self.get_session() as session:
            try:
                message = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    message_metadata=metadata or {},
                    created_at=datetime.utcnow()
                )

                session.add(message)
                session.commit()
                session.refresh(message)

                return self._message_to_model(message)

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to create message: {str(e)}")
                raise

    async def get_conversation_messages(self, conversation_id: str) -> List[MessageModel]:
        """Get all messages for a conversation"""
        with self.get_session() as session:
            try:
                messages = session.query(Message).filter(
                    Message.conversation_id == conversation_id
                ).order_by(Message.created_at.asc()).all()

                return [self._message_to_model(msg) for msg in messages]

            except Exception as e:
                logger.error(f"Failed to get messages for conversation {conversation_id}: {str(e)}")
                raise

    # Conversion methods
    def _agent_to_model(self, agent: Agent) -> AgentModel:
        """Convert database agent to Pydantic model"""
        # 确保 config 中的模型使用当前配置的默认模型
        agent_config = agent.config.copy() if isinstance(agent.config, dict) else {}
        # 强制更新模型配置为当前配置的默认模型
        agent_config["model"] = settings.provider_default_model
        logger.debug(f"Updated agent {agent.id} model to {settings.provider_default_model} in _agent_to_model")
        
        return AgentModel(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            agent_type=agent.agent_type,
            config=agent_config,  # 使用更新后的配置
            tools=agent.tools,
            triggers=agent.triggers,
            rag_enabled=agent.rag_enabled,
            rag_sources=agent.rag_sources,
            status=AgentStatus(agent.status),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            last_run=agent.last_run,
            run_count=agent.run_count
        )

    def _conversation_to_model(self, conversation: Conversation) -> ConversationModel:
        """Convert database conversation to Pydantic model"""
        return ConversationModel(
            id=conversation.id,
            agent_id=conversation.agent_id,
            user_id=conversation.user_id,
            title=conversation.title,
            context=conversation.context,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=conversation.message_count
        )

    def _message_to_model(self, message: Message) -> MessageModel:
        """Convert database message to Pydantic model"""
        return MessageModel(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            metadata=message.message_metadata,
            created_at=message.created_at
        )


# Import uuid for ID generation
import uuid
from datetime import datetime