"""Database models for the conversational AI system."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey,
    Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector
import uuid

Base = declarative_base()


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class User(Base, TimestampMixin):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)

    # User preferences
    preferences = Column(JSON, default=dict)

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    tools = relationship("Tool", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"


class Conversation(Base, TimestampMixin):
    """Conversation model to group related messages."""
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    system_prompt = Column(Text)
    model = Column(String(100), default="gpt-3.5-turbo")
    temperature = Column(String(10), default="0.7")
    max_tokens = Column(Integer, default=1000)

    # Conversation metadata
    metadata = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

    def __repr__(self):
        return f"<Conversation(id={self.id}, title='{self.title}')>"


class Message(Base, TimestampMixin):
    """Message model for conversation history."""
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)

    # Tool execution results
    tool_calls = Column(JSON)
    tool_call_id = Column(String(100))

    # Message metadata
    metadata = Column(JSON, default=dict)
    token_count = Column(Integer)
    model = Column(String(100))

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    # Indexes for performance
    __table_args__ = (
        Index("idx_message_conversation_created", "conversation_id", "created_at"),
        Index("idx_message_role", "role"),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, role='{self.role}')>"


class Memory(Base, TimestampMixin):
    """Vector memory for semantic search and context retrieval."""
    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)

    # Content and embedding
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # Assuming OpenAI embeddings

    # Memory type and metadata
    memory_type = Column(String(50), default="episodic")  # episodic, semantic, procedural
    importance = Column(Integer, default=1)  # 1-10 scale
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime)

    # Metadata for filtering and organization
    tags = Column(ARRAY(String))
    metadata = Column(JSON, default=dict)

    # Indexes for vector similarity search
    __table_args__ = (
        Index("idx_memory_user", "user_id"),
        Index("idx_memory_conversation", "conversation_id"),
        Index("idx_memory_type", "memory_type"),
        Index("idx_memory_embedding_cosine", "embedding", postgresql_using="ivfflat", postgresql_with={"lists": 100}, postgresql_ops={"embedding": "vector_cosine_ops"}),
    )

    def __repr__(self):
        return f"<Memory(id={self.id}, type='{self.memory_type}')>"


class Tool(Base, TimestampMixin):
    """Tool definitions for LLM function calling."""
    __tablename__ = "tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Tool definition
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=False)
    schema = Column(JSON, nullable=False)  # JSON Schema for parameters
    implementation = Column(Text, nullable=False)  # Python code or API endpoint

    # Tool metadata
    category = Column(String(50), default="general")
    is_active = Column(Boolean, default=True)
    is_builtin = Column(Boolean, default=False)
    version = Column(String(20), default="1.0.0")

    # Usage statistics
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="tools")
    executions = relationship("ToolExecution", back_populates="tool", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tool(id={self.id}, name='{self.name}')>"


class ToolExecution(Base, TimestampMixin):
    """Tool execution history and results."""
    __tablename__ = "tool_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_id = Column(UUID(as_uuid=True), ForeignKey("tools.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)

    # Execution details
    parameters = Column(JSON, nullable=False)
    result = Column(JSON)
    error = Column(Text)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    execution_time = Column(Integer)  # milliseconds

    # Relationships
    tool = relationship("Tool", back_populates="executions")

    # Indexes
    __table_args__ = (
        Index("idx_tool_execution_user", "user_id"),
        Index("idx_tool_execution_conversation", "conversation_id"),
        Index("idx_tool_execution_status", "status"),
    )

    def __repr__(self):
        return f"<ToolExecution(id={self.id}, status='{self.status}')>"


class APIKey(Base, TimestampMixin):
    """API keys for external service integration."""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Key details
    name = Column(String(100), nullable=False)
    key = Column(String(500), nullable=False)  # Encrypted
    provider = Column(String(50), nullable=False)  # openai, anthropic, google, etc.

    # Key metadata
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime)
    expires_at = Column(DateTime)

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="unique_user_key_name"),
        Index("idx_api_key_user", "user_id"),
        Index("idx_api_key_provider", "provider"),
    )

    def __repr__(self):
        return f"<APIKey(id={self.id}, provider='{self.provider}')>"