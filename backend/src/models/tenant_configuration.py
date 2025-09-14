"""Tenant configuration model for organizational settings and policies."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
import uuid

from ..models import Base, TimestampMixin


class DataIsolationLevel(str, Enum):
    """Data isolation levels for tenant security."""
    STRICT = "strict"
    STANDARD = "standard"


class TenantConfiguration(Base, TimestampMixin):
    """Organizational settings including features, limits, and administrative policies."""
    __tablename__ = "tenant_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Tenant identification
    tenant_name = Column(String(255), nullable=False)
    tenant_slug = Column(String(100), nullable=False, unique=True)  # URL-safe identifier
    admin_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Configuration settings
    enabled_features = Column(JSON, default=list)  # Array of feature flags
    custom_limits = Column(JSON, default=dict)  # Overrides for default quotas
    data_isolation_level = Column(
        ENUM(DataIsolationLevel, name="data_isolation_level"),
        default=DataIsolationLevel.STANDARD,
        nullable=False
    )

    # Billing and security settings
    billing_settings = Column(JSON, default=dict)  # Payment and invoicing config
    security_settings = Column(JSON, default=dict)  # Authentication and access policies

    # Relationships
    admin_user = relationship("User", backref="administered_tenants")
    users = relationship("User", backref="tenant", foreign_keys="User.tenant_id")

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint("tenant_slug", name="unique_tenant_slug"),
        Index("idx_tenant_config_slug", "tenant_slug"),
        Index("idx_tenant_config_admin", "admin_user_id"),
        Index("idx_tenant_config_isolation", "data_isolation_level"),
    )

    @property
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a specific feature is enabled for this tenant."""
        if not isinstance(self.enabled_features, list):
            return False
        return feature_name in self.enabled_features

    def get_custom_limit(self, limit_type: str, default_value: int = None) -> int:
        """Get custom limit value or return default."""
        if not isinstance(self.custom_limits, dict):
            return default_value
        return self.custom_limits.get(limit_type, default_value)

    def __repr__(self):
        return f"<TenantConfiguration(id={self.id}, name='{self.tenant_name}', slug='{self.tenant_slug}')>"