"""Usage quota model for resource limits and consumption tracking."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, ENUM
import uuid

from ..models import Base


class EntityType(str, Enum):
    """Entity type for polymorphic association."""
    USER = "user"
    TENANT = "tenant"


class QuotaType(str, Enum):
    """Quota types for different resource limits."""
    MESSAGES_PER_DAY = "messages_per_day"
    TOKENS_PER_MONTH = "tokens_per_month"
    FILE_UPLOADS_PER_DAY = "file_uploads_per_day"
    VOICE_MINUTES_PER_MONTH = "voice_minutes_per_month"
    STORAGE_MB = "storage_mb"
    API_CALLS_PER_HOUR = "api_calls_per_hour"


class ResetPeriod(str, Enum):
    """Reset period for quota limits."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class OveragePolicy(str, Enum):
    """Policy for handling quota overages."""
    BLOCK = "block"
    THROTTLE = "throttle"
    BILLING = "billing"
    NOTIFY = "notify"


class UsageQuota(Base):
    """Resource limits and current consumption tracking per user or tenant."""
    __tablename__ = "usage_quotas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Polymorphic association - can reference User or Tenant
    entity_type = Column(
        ENUM(EntityType, name="entity_type"),
        nullable=False
    )
    entity_id = Column(UUID(as_uuid=True), nullable=False)

    # Quota configuration
    quota_type = Column(
        ENUM(QuotaType, name="quota_type"),
        nullable=False
    )
    limit_value = Column(Integer, nullable=False)  # Maximum allowed
    current_usage = Column(Integer, default=0, nullable=False)  # Current consumption

    # Reset configuration
    reset_period = Column(
        ENUM(ResetPeriod, name="reset_period"),
        nullable=False
    )
    last_reset = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Overage handling
    overage_policy = Column(
        ENUM(OveragePolicy, name="overage_policy"),
        default=OveragePolicy.BLOCK,
        nullable=False
    )
    overage_count = Column(Integer, default=0, nullable=False)  # Times limit exceeded

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Indexes for performance
    __table_args__ = (
        Index("idx_usage_quota_entity", "entity_type", "entity_id"),
        Index("idx_usage_quota_type", "quota_type"),
        Index("idx_usage_quota_reset", "reset_period", "last_reset"),
        Index("idx_usage_quota_overage", "overage_count"),
        Index("idx_usage_quota_entity_type", "entity_type", "entity_id", "quota_type"),
    )

    @property
    def is_over_limit(self):
        """Check if current usage exceeds the limit."""
        return self.current_usage > self.limit_value

    @property
    def usage_percentage(self):
        """Calculate usage as a percentage of the limit."""
        if self.limit_value == 0:
            return 0
        return min((self.current_usage / self.limit_value) * 100, 100)

    def __repr__(self):
        return f"<UsageQuota(id={self.id}, type='{self.quota_type}', usage={self.current_usage}/{self.limit_value})>"