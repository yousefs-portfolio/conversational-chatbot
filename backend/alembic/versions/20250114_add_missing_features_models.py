"""Add missing features models

Revision ID: 20250114001
Revises:
Create Date: 2025-01-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic
revision = '20250114001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tables for missing features"""

    # Create VoiceSession table
    op.create_table('voice_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('audio_input_file_path', sa.String(), nullable=True),
        sa.Column('transcribed_text', sa.Text(), nullable=True),
        sa.Column('recognition_accuracy', sa.Float(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('language_detected', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Enum('processing', 'completed', 'failed', name='voicesessionstatus'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_voice_sessions_user_id', 'voice_sessions', ['user_id'])
    op.create_index('ix_voice_sessions_conversation_id', 'voice_sessions', ['conversation_id'])
    op.create_index('ix_voice_sessions_status', 'voice_sessions', ['status'])

    # Create UploadedFile table
    op.create_table('uploaded_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_type', sa.Enum('pdf', 'docx', 'txt', 'jpg', 'png', 'gif', name='filetype'), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('extracted_content', sa.Text(), nullable=True),
        sa.Column('processing_status', sa.Enum('pending', 'processing', 'completed', 'failed', name='processingstatus'), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('upload_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_uploaded_files_user_id', 'uploaded_files', ['user_id'])
    op.create_index('ix_uploaded_files_conversation_id', 'uploaded_files', ['conversation_id'])
    op.create_index('ix_uploaded_files_processing_status', 'uploaded_files', ['processing_status'])
    op.create_index('ix_uploaded_files_content_hash', 'uploaded_files', ['content_hash'])

    # Create AnalyticsEvent table
    op.create_table('analytics_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data', postgresql.JSONB(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('cost_cents', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant_configurations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_events_user_id', 'analytics_events', ['user_id'])
    op.create_index('ix_analytics_events_tenant_id', 'analytics_events', ['tenant_id'])
    op.create_index('ix_analytics_events_event_type', 'analytics_events', ['event_type'])
    op.create_index('ix_analytics_events_timestamp', 'analytics_events', ['timestamp'])
    op.create_index('ix_analytics_events_session_id', 'analytics_events', ['session_id'])

    # Create UsageQuota table
    op.create_table('usage_quotas',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('entity_type', sa.Enum('user', 'tenant', name='entitytype'), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quota_type', sa.Enum('messages_per_day', 'tokens_per_month', 'file_uploads_per_day', 'voice_minutes_per_month', name='quotatype'), nullable=False),
        sa.Column('limit_value', sa.Integer(), nullable=False),
        sa.Column('current_usage', sa.Integer(), nullable=False, default=0),
        sa.Column('reset_period', sa.Enum('daily', 'weekly', 'monthly', name='resetperiod'), nullable=False),
        sa.Column('last_reset', sa.DateTime(timezone=True), nullable=False),
        sa.Column('overage_policy', sa.Enum('block', 'throttle', 'billing', name='overagepolicy'), nullable=False),
        sa.Column('overage_count', sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'entity_id', 'quota_type', name='uq_entity_quota')
    )
    op.create_index('ix_usage_quotas_entity', 'usage_quotas', ['entity_type', 'entity_id'])
    op.create_index('ix_usage_quotas_quota_type', 'usage_quotas', ['quota_type'])

    # Create TenantConfiguration table
    op.create_table('tenant_configurations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('tenant_name', sa.String(255), nullable=False),
        sa.Column('tenant_slug', sa.String(100), nullable=False, unique=True),
        sa.Column('admin_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enabled_features', postgresql.JSONB(), nullable=True),
        sa.Column('custom_limits', postgresql.JSONB(), nullable=True),
        sa.Column('data_isolation_level', sa.Enum('strict', 'standard', name='dataisolationlevel'), nullable=False, default='standard'),
        sa.Column('billing_settings', postgresql.JSONB(), nullable=True),
        sa.Column('security_settings', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tenant_configurations_tenant_slug', 'tenant_configurations', ['tenant_slug'], unique=True)
    op.create_index('ix_tenant_configurations_admin_user_id', 'tenant_configurations', ['admin_user_id'])

    # Create ProactiveSuggestion table
    op.create_table('proactive_suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('suggestion_type', sa.Enum('tool_recommendation', 'workflow_optimization', 'content_improvement', name='suggestiontype'), nullable=False),
        sa.Column('suggestion_content', sa.Text(), nullable=False),
        sa.Column('context_data', postgresql.JSONB(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('user_response', sa.Enum('accepted', 'dismissed', 'ignored', name='userresponse'), nullable=True),
        sa.Column('effectiveness_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_proactive_suggestions_user_id', 'proactive_suggestions', ['user_id'])
    op.create_index('ix_proactive_suggestions_conversation_id', 'proactive_suggestions', ['conversation_id'])
    op.create_index('ix_proactive_suggestions_user_response', 'proactive_suggestions', ['user_response'])

    # Create PersonalizationProfile table
    op.create_table('personalization_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('communication_style', sa.Enum('formal', 'casual', 'technical', 'creative', name='communicationstyle'), nullable=True),
        sa.Column('preferred_tools', postgresql.JSONB(), nullable=True),
        sa.Column('interaction_patterns', postgresql.JSONB(), nullable=True),
        sa.Column('learning_preferences', postgresql.JSONB(), nullable=True),
        sa.Column('privacy_settings', postgresql.JSONB(), nullable=True),
        sa.Column('adaptation_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('profile_version', sa.Integer(), nullable=False, default=1),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_personalization_profiles_user_id', 'personalization_profiles', ['user_id'], unique=True)

    # Create AuditLogEntry table
    op.create_table('audit_log_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action_details', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False, default=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant_configurations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_log_entries_user_id', 'audit_log_entries', ['user_id'])
    op.create_index('ix_audit_log_entries_tenant_id', 'audit_log_entries', ['tenant_id'])
    op.create_index('ix_audit_log_entries_action_type', 'audit_log_entries', ['action_type'])
    op.create_index('ix_audit_log_entries_timestamp', 'audit_log_entries', ['timestamp'])
    op.create_index('ix_audit_log_entries_resource', 'audit_log_entries', ['resource_type', 'resource_id'])


def downgrade() -> None:
    """Drop tables for missing features"""

    op.drop_table('audit_log_entries')
    op.drop_table('personalization_profiles')
    op.drop_table('proactive_suggestions')
    op.drop_table('tenant_configurations')
    op.drop_table('usage_quotas')
    op.drop_table('analytics_events')
    op.drop_table('uploaded_files')
    op.drop_table('voice_sessions')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS voicesessionstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS filetype CASCADE")
    op.execute("DROP TYPE IF EXISTS processingstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS entitytype CASCADE")
    op.execute("DROP TYPE IF EXISTS quotatype CASCADE")
    op.execute("DROP TYPE IF EXISTS resetperiod CASCADE")
    op.execute("DROP TYPE IF EXISTS overagepolicy CASCADE")
    op.execute("DROP TYPE IF EXISTS dataisolationlevel CASCADE")
    op.execute("DROP TYPE IF EXISTS suggestiontype CASCADE")
    op.execute("DROP TYPE IF EXISTS userresponse CASCADE")
    op.execute("DROP TYPE IF EXISTS communicationstyle CASCADE")