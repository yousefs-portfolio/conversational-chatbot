"""Audit log entry model for security and compliance tracking."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID, ENUM, INET, TIMESTAMP
from sqlalchemy.orm import relationship
import uuid

from ..models import Base


class ActionType(str, Enum):
    """Types of auditable actions."""
    LOGIN = "login"
    LOGOUT = "logout"
    DATA_ACCESS = "data_access"
    DATA_MODIFY = "data_modify"
    DATA_DELETE = "data_delete"
    CONFIGURATION_CHANGE = "configuration_change"
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    PERMISSION_CHANGE = "permission_change"
    API_ACCESS = "api_access"
    SYSTEM_ACTION = "system_action"
    SECURITY_EVENT = "security_event"


class AuditLogEntry(Base):
    """Security and compliance record with action details, user identification, and system context."""
    __tablename__ = "audit_log_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Nullable for system actions
    tenant_id = Column(UUID(as_uuid=True), nullable=True)  # For multi-tenancy

    # Action details
    action_type = Column(
        ENUM(ActionType, name="action_type"),
        nullable=False
    )
    resource_type = Column(String(100))  # What was acted upon
    resource_id = Column(UUID(as_uuid=True))  # Identifier of affected resource
    action_details = Column(JSON, default=dict)  # Specific action parameters

    # Request context
    ip_address = Column(INET)  # Source IP address
    user_agent = Column(Text)  # Browser/client information
    timestamp = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False)

    # Outcome
    success = Column(Boolean, nullable=False)  # Whether action completed successfully
    failure_reason = Column(Text)  # Error details if failed

    # Relationships
    user = relationship("User", backref="audit_log_entries")

    # Indexes for performance and compliance queries
    __table_args__ = (
        Index("idx_audit_log_user", "user_id"),
        Index("idx_audit_log_tenant", "tenant_id"),
        Index("idx_audit_log_action_type", "action_type"),
        Index("idx_audit_log_resource", "resource_type", "resource_id"),
        Index("idx_audit_log_timestamp", "timestamp"),
        Index("idx_audit_log_success", "success"),
        Index("idx_audit_log_ip", "ip_address"),
        Index("idx_audit_log_user_timestamp", "user_id", "timestamp"),
        Index("idx_audit_log_action_timestamp", "action_type", "timestamp"),
    )

    @property
    def is_security_relevant(self) -> bool:
        """Check if this audit entry is security-relevant."""
        security_actions = {
            ActionType.LOGIN,
            ActionType.LOGOUT,
            ActionType.PERMISSION_CHANGE,
            ActionType.SECURITY_EVENT,
            ActionType.CONFIGURATION_CHANGE
        }
        return self.action_type in security_actions

    @property
    def is_data_access(self) -> bool:
        """Check if this audit entry involves data access."""
        data_actions = {
            ActionType.DATA_ACCESS,
            ActionType.DATA_MODIFY,
            ActionType.DATA_DELETE,
            ActionType.FILE_DOWNLOAD
        }
        return self.action_type in data_actions

    def __repr__(self):
        return f"<AuditLogEntry(id={self.id}, action='{self.action_type}', user_id={self.user_id}, success={self.success})>"