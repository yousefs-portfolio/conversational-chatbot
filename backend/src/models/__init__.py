"""Database models for the conversational AI system."""

# Import base classes and existing models from parent module
from src.models import (
    Base,
    TimestampMixin,
    User,
    Conversation,
    Message,
    Memory,
    Tool,
    ToolExecution,
    APIKey
)

# Import new models for missing features
from .voice_session import VoiceSession, VoiceSessionStatus
from .uploaded_file import UploadedFile, FileType, ProcessingStatus
from .analytics_event import AnalyticsEvent, EventType
from .usage_quota import UsageQuota, EntityType, QuotaType, ResetPeriod, OveragePolicy
from .tenant_configuration import TenantConfiguration, DataIsolationLevel
from .proactive_suggestion import ProactiveSuggestion, SuggestionType, UserResponse
from .personalization_profile import PersonalizationProfile, CommunicationStyle
from .audit_log_entry import AuditLogEntry, ActionType

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    # Original models
    "User",
    "Conversation",
    "Message",
    "Memory",
    "Tool",
    "ToolExecution",
    "APIKey",
    # New models for missing features
    "VoiceSession",
    "VoiceSessionStatus",
    "UploadedFile",
    "FileType",
    "ProcessingStatus",
    "AnalyticsEvent",
    "EventType",
    "UsageQuota",
    "EntityType",
    "QuotaType",
    "ResetPeriod",
    "OveragePolicy",
    "TenantConfiguration",
    "DataIsolationLevel",
    "ProactiveSuggestion",
    "SuggestionType",
    "UserResponse",
    "PersonalizationProfile",
    "CommunicationStyle",
    "AuditLogEntry",
    "ActionType",
]