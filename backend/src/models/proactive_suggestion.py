"""Proactive suggestion model for AI-generated recommendations."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
import uuid

from ..models import Base, TimestampMixin


class SuggestionType(str, Enum):
    """Types of proactive suggestions."""
    TOOL_RECOMMENDATION = "tool_recommendation"
    WORKFLOW_OPTIMIZATION = "workflow_optimization"
    CONTENT_IMPROVEMENT = "content_improvement"
    CONTEXT_SUGGESTION = "context_suggestion"
    EFFICIENCY_TIP = "efficiency_tip"


class UserResponse(str, Enum):
    """User response to suggestions."""
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    IGNORED = "ignored"


class ProactiveSuggestion(Base, TimestampMixin):
    """AI-generated recommendation with context, effectiveness tracking, and user response."""
    __tablename__ = "proactive_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)

    # Suggestion details
    suggestion_type = Column(
        ENUM(SuggestionType, name="suggestion_type"),
        nullable=False
    )
    suggestion_content = Column(Text, nullable=False)  # The actual suggestion
    context_data = Column(JSON, default=dict)  # What triggered the suggestion

    # AI confidence and effectiveness
    confidence_score = Column(Float, nullable=False)  # 0.0-1.0 AI confidence
    effectiveness_score = Column(Float)  # 0.0-1.0 post-action success rate

    # User interaction
    user_response = Column(
        ENUM(UserResponse, name="user_response"),
        nullable=True
    )
    responded_at = Column(DateTime)

    # Relationships
    user = relationship("User", backref="proactive_suggestions")
    conversation = relationship("Conversation", backref="proactive_suggestions")

    # Indexes for performance and analytics
    __table_args__ = (
        Index("idx_proactive_suggestion_user", "user_id"),
        Index("idx_proactive_suggestion_conversation", "conversation_id"),
        Index("idx_proactive_suggestion_type", "suggestion_type"),
        Index("idx_proactive_suggestion_response", "user_response"),
        Index("idx_proactive_suggestion_created", "created_at"),
        Index("idx_proactive_suggestion_confidence", "confidence_score"),
        Index("idx_proactive_suggestion_user_type", "user_id", "suggestion_type"),
    )

    @property
    def is_responded(self) -> bool:
        """Check if user has responded to the suggestion."""
        return self.user_response is not None

    @property
    def response_time_seconds(self) -> int:
        """Calculate response time in seconds if responded."""
        if not self.is_responded or not self.responded_at:
            return None
        return int((self.responded_at - self.created_at).total_seconds())

    def __repr__(self):
        return f"<ProactiveSuggestion(id={self.id}, type='{self.suggestion_type}', response='{self.user_response}')>"