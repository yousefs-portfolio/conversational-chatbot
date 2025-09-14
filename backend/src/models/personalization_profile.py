"""Personalization profile model for user-specific preferences and patterns."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Index, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
import uuid

from ..models import Base, TimestampMixin


class CommunicationStyle(str, Enum):
    """Communication style preferences."""
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    CREATIVE = "creative"


class PersonalizationProfile(Base, TimestampMixin):
    """User-specific preferences, patterns, and adaptation settings."""
    __tablename__ = "personalization_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)

    # Communication preferences
    communication_style = Column(
        ENUM(CommunicationStyle, name="communication_style"),
        default=CommunicationStyle.CASUAL,
        nullable=False
    )

    # User preferences and patterns
    preferred_tools = Column(JSON, default=list)  # Array of frequently used tools
    interaction_patterns = Column(JSON, default=dict)  # Usage analytics and preferences
    learning_preferences = Column(JSON, default=dict)  # How user likes to receive information
    privacy_settings = Column(JSON, default=dict)  # What data can be used for personalization

    # Adaptation settings
    adaptation_enabled = Column(Boolean, default=True, nullable=False)  # Whether to personalize responses

    # Version tracking
    profile_version = Column(Integer, default=1, nullable=False)  # For tracking changes

    # Relationships
    user = relationship("User", backref="personalization_profile", uselist=False)

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint("user_id", name="unique_user_personalization_profile"),
        Index("idx_personalization_profile_user", "user_id"),
        Index("idx_personalization_profile_style", "communication_style"),
        Index("idx_personalization_profile_adaptation", "adaptation_enabled"),
        Index("idx_personalization_profile_version", "profile_version"),
    )

    def get_preferred_tool_priority(self, tool_name: str) -> int:
        """Get priority of a tool based on user preferences (higher = more preferred)."""
        if not isinstance(self.preferred_tools, list):
            return 0

        try:
            # If tool is in preferred list, return index as priority (lower index = higher priority)
            return len(self.preferred_tools) - self.preferred_tools.index(tool_name)
        except ValueError:
            # Tool not in preferred list
            return 0

    def is_feature_allowed(self, feature_name: str) -> bool:
        """Check if a personalization feature is allowed by privacy settings."""
        if not isinstance(self.privacy_settings, dict):
            return True  # Default to allowing if no privacy settings

        return self.privacy_settings.get(feature_name, True)

    def increment_version(self):
        """Increment profile version when making changes."""
        self.profile_version += 1
        self.updated_at = datetime.utcnow()

    def __repr__(self):
        return f"<PersonalizationProfile(id={self.id}, user_id={self.user_id}, style='{self.communication_style}')>"