"""Analytics event model for tracking user actions and system metrics."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, ENUM, TIMESTAMP
from sqlalchemy.orm import relationship
import uuid

from ..models import Base


class EventType(str, Enum):
    """Analytics event types."""
    CONVERSATION_START = "conversation_start"
    MESSAGE_SENT = "message_sent"
    TOOL_USED = "tool_used"
    FILE_UPLOADED = "file_uploaded"
    VOICE_INTERACTION = "voice_interaction"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    SEARCH_PERFORMED = "search_performed"
    MODEL_SWITCHED = "model_switched"
    SETTINGS_CHANGED = "settings_changed"
    ERROR_OCCURRED = "error_occurred"


class AnalyticsEvent(Base):
    """Individual user action or system metric with comprehensive tracking."""
    __tablename__ = "analytics_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Nullable for system events
    tenant_id = Column(UUID(as_uuid=True), nullable=True)  # For multi-tenancy

    # Event details
    event_type = Column(
        ENUM(EventType, name="event_type"),
        nullable=False
    )
    event_data = Column(JSON, default=dict)  # Flexible event-specific metadata
    timestamp = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False)
    session_id = Column(UUID(as_uuid=True))  # Groups related events

    # Usage tracking
    token_count = Column(Integer)  # For usage tracking
    processing_time_ms = Column(Integer)  # For performance monitoring
    cost_cents = Column(Integer)  # For billing tracking

    # Relationships
    user = relationship("User", backref="analytics_events")

    # Indexes for performance and analytics queries
    __table_args__ = (
        Index("idx_analytics_event_user", "user_id"),
        Index("idx_analytics_event_tenant", "tenant_id"),
        Index("idx_analytics_event_type", "event_type"),
        Index("idx_analytics_event_timestamp", "timestamp"),
        Index("idx_analytics_event_session", "session_id"),
        Index("idx_analytics_event_user_timestamp", "user_id", "timestamp"),
        Index("idx_analytics_event_type_timestamp", "event_type", "timestamp"),
    )

    def __repr__(self):
        return f"<AnalyticsEvent(id={self.id}, type='{self.event_type}', user_id={self.user_id})>"