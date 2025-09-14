"""Voice session model for audio input/output interactions."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
import uuid

from ..models import Base, TimestampMixin


class VoiceSessionStatus(str, Enum):
    """Voice session processing status."""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VoiceSession(Base, TimestampMixin):
    """Voice session model for audio input/output interactions with processing metadata."""
    __tablename__ = "voice_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)

    # Audio processing fields
    audio_input_file_path = Column(String(500), nullable=False)
    transcribed_text = Column(Text)
    recognition_accuracy = Column(Float)  # 0.0-1.0 confidence score
    processing_time_ms = Column(Integer)  # Total processing duration
    language_detected = Column(String(10))  # ISO language code

    # Status tracking
    status = Column(
        ENUM(VoiceSessionStatus, name="voice_session_status"),
        default=VoiceSessionStatus.PROCESSING,
        nullable=False
    )

    # Relationships
    user = relationship("User", backref="voice_sessions")
    conversation = relationship("Conversation", backref="voice_sessions")

    # Indexes for performance
    __table_args__ = (
        Index("idx_voice_session_user", "user_id"),
        Index("idx_voice_session_conversation", "conversation_id"),
        Index("idx_voice_session_status", "status"),
        Index("idx_voice_session_created", "created_at"),
        Index("idx_voice_session_language", "language_detected"),
    )

    def __repr__(self):
        return f"<VoiceSession(id={self.id}, status='{self.status}', language='{self.language_detected}')>"