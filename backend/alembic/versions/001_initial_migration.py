"""Initial migration

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create vector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_superuser', sa.Boolean(), default=False),
        sa.Column('preferences', sa.JSON(), default={}),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # Create conversations table
    op.create_table('conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('system_prompt', sa.Text()),
        sa.Column('model', sa.String(100), default='gpt-3.5-turbo'),
        sa.Column('temperature', sa.String(10), default='0.7'),
        sa.Column('max_tokens', sa.Integer(), default=1000),
        sa.Column('metadata', sa.JSON(), default={}),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # Create messages table
    op.create_table('messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tool_calls', sa.JSON()),
        sa.Column('tool_call_id', sa.String(100)),
        sa.Column('metadata', sa.JSON(), default={}),
        sa.Column('token_count', sa.Integer()),
        sa.Column('model', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # Create indexes for messages
    op.create_index('idx_message_conversation_created', 'messages', ['conversation_id', 'created_at'])
    op.create_index('idx_message_role', 'messages', ['role'])

    # Create memories table with vector column
    op.create_table('memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id')),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.String()), # Will be converted to vector type after table creation
        sa.Column('memory_type', sa.String(50), default='episodic'),
        sa.Column('importance', sa.Integer(), default=1),
        sa.Column('access_count', sa.Integer(), default=0),
        sa.Column('last_accessed', sa.DateTime()),
        sa.Column('tags', postgresql.ARRAY(sa.String())),
        sa.Column('metadata', sa.JSON(), default={}),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # Alter embedding column to vector type
    op.execute('ALTER TABLE memories ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)')

    # Create indexes for memories
    op.create_index('idx_memory_user', 'memories', ['user_id'])
    op.create_index('idx_memory_conversation', 'memories', ['conversation_id'])
    op.create_index('idx_memory_type', 'memories', ['memory_type'])

    # Create vector similarity index
    op.execute('''
        CREATE INDEX idx_memory_embedding_cosine
        ON memories
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')

    # Create tools table
    op.create_table('tools',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('schema', sa.JSON(), nullable=False),
        sa.Column('implementation', sa.Text(), nullable=False),
        sa.Column('category', sa.String(50), default='general'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_builtin', sa.Boolean(), default=False),
        sa.Column('version', sa.String(20), default='1.0.0'),
        sa.Column('usage_count', sa.Integer(), default=0),
        sa.Column('last_used', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # Create tool_executions table
    op.create_table('tool_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('tool_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tools.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id')),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('messages.id')),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON()),
        sa.Column('error', sa.Text()),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('execution_time', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # Create indexes for tool_executions
    op.create_index('idx_tool_execution_user', 'tool_executions', ['user_id'])
    op.create_index('idx_tool_execution_conversation', 'tool_executions', ['conversation_id'])
    op.create_index('idx_tool_execution_status', 'tool_executions', ['status'])

    # Create api_keys table
    op.create_table('api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('key', sa.String(500), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('usage_count', sa.Integer(), default=0),
        sa.Column('last_used', sa.DateTime()),
        sa.Column('expires_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    # Create constraints and indexes for api_keys
    op.create_index('idx_api_key_user', 'api_keys', ['user_id'])
    op.create_index('idx_api_key_provider', 'api_keys', ['provider'])
    op.execute('ALTER TABLE api_keys ADD CONSTRAINT unique_user_key_name UNIQUE (user_id, name)')


def downgrade() -> None:
    op.drop_table('api_keys')
    op.drop_table('tool_executions')
    op.drop_table('tools')
    op.drop_table('memories')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('users')
    op.execute('DROP EXTENSION IF EXISTS vector')