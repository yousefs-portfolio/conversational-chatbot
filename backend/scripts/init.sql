-- Conversational AI Agent Database Initialization Script
-- This script sets up the initial database schema and extensions

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid-ossp extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm extension for text similarity search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable btree_gin extension for better indexing
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Create custom types
DO $$ BEGIN
    -- Enum for user roles (if needed in future)
    CREATE TYPE user_role AS ENUM ('user', 'admin', 'moderator');
    EXCEPTION
        WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    -- Enum for message roles
    CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');
    EXCEPTION
        WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    -- Enum for tool execution status
    CREATE TYPE execution_status AS ENUM ('pending', 'running', 'completed', 'failed');
    EXCEPTION
        WHEN duplicate_object THEN null;
END $$;

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create function for generating nanoid-style IDs (optional)
CREATE OR REPLACE FUNCTION generate_nanoid(size int DEFAULT 21)
RETURNS text AS $$
DECLARE
    alphabet text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
    idBuilder text := '';
    i int := 0;
    bytes bytea;
BEGIN
    bytes := gen_random_bytes(size);
    WHILE i < size LOOP
        idBuilder := idBuilder || substr(alphabet, (get_byte(bytes, i) % 62) + 1, 1);
        i := i + 1;
    END LOOP;
    RETURN idBuilder;
END;
$$ LANGUAGE plpgsql VOLATILE;

-- Create function for vector cosine similarity (helper for queries)
CREATE OR REPLACE FUNCTION cosine_similarity(a vector, b vector)
RETURNS float AS $$
BEGIN
    RETURN (a <=> b);
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;

-- Create materialized view for user statistics (will be created after tables)
-- This will be created by migrations after the tables exist

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE conversational TO postgres;

-- Create schema for storing application settings
CREATE SCHEMA IF NOT EXISTS app_config;

-- Create table for application configuration
CREATE TABLE IF NOT EXISTS app_config.settings (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create trigger for updating updated_at
CREATE TRIGGER update_app_settings_updated_at
    BEFORE UPDATE ON app_config.settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default application settings
INSERT INTO app_config.settings (key, value, description) VALUES
    ('version', '"1.0.0"', 'Application version'),
    ('max_conversation_length', '50', 'Maximum messages per conversation'),
    ('max_memory_items', '1000', 'Maximum memory items per user'),
    ('vector_similarity_threshold', '0.7', 'Default similarity threshold for vector search'),
    ('rate_limit_per_minute', '60', 'Default rate limit per minute per user'),
    ('session_timeout_minutes', '15', 'JWT session timeout in minutes')
ON CONFLICT (key) DO NOTHING;

-- Create indexes for better performance on common queries
-- Note: Table-specific indexes will be created by SQLAlchemy migrations

-- Create a function to clean up old sessions (will be used by background tasks)
CREATE OR REPLACE FUNCTION cleanup_expired_sessions(expire_before TIMESTAMP WITH TIME ZONE)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- This will be updated once the sessions table is created
    -- DELETE FROM sessions WHERE expires_at < expire_before;
    -- GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN 0; -- Placeholder until sessions table exists
END;
$$ LANGUAGE plpgsql;

-- Create a function for full-text search on conversations
CREATE OR REPLACE FUNCTION search_conversations(
    search_term TEXT,
    user_id_param UUID DEFAULT NULL
)
RETURNS TABLE (
    conversation_id UUID,
    title TEXT,
    summary TEXT,
    rank REAL
) AS $$
BEGIN
    -- This will be implemented once tables are created
    -- Placeholder implementation
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- Create notification function for real-time updates (optional)
CREATE OR REPLACE FUNCTION notify_conversation_update()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify(
        'conversation_update',
        json_build_object(
            'action', TG_OP,
            'conversation_id', COALESCE(NEW.id, OLD.id),
            'user_id', COALESCE(NEW.user_id, OLD.user_id)
        )::text
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Conversational AI database initialization completed successfully';
    RAISE NOTICE 'Extensions enabled: vector, uuid-ossp, pg_trgm, btree_gin';
    RAISE NOTICE 'Custom functions created for timestamps, IDs, and search';
END $$;