# Claude Code Context: Conversational AI Agent System

**Project**: Conversational AI Agent with Tool Use & Memory
**Tech Stack**: Python 3.11, FastAPI, PostgreSQL, Redis, Next.js, TypeScript
**Architecture**: Web application (backend + frontend + CLI)

## Project Overview

A comprehensive conversational AI system that enables intelligent conversations with tool integration and persistent memory. Users can chat with AI agents that remember context, execute external tools (calculator, web search, weather), and provide personalized responses.

## Key Features

- **Real-time Chat**: WebSocket-based instant messaging with AI agents
- **Tool Integration**: Calculator, web search, weather tools with extensible framework
- **Persistent Memory**: Semantic memory with vector embeddings using pgvector
- **Multi-user Support**: Complete user isolation with JWT authentication
- **Personalization**: User preferences and adaptive AI behavior
- **Multiple Interfaces**: Web UI, CLI tool, and REST API

## Architecture

### Backend (Python/FastAPI)
```
backend/
├── src/
│   ├── models/           # SQLAlchemy models with relationships
│   ├── services/         # Business logic (auth, conversation, memory, llm, tools)
│   ├── api/              # REST API endpoints
│   ├── websocket/        # Real-time WebSocket handlers
│   ├── tools/            # AI tool implementations
│   ├── middleware/       # Auth, CORS, rate limiting
│   └── tasks/            # Background Celery tasks
├── tests/                # TDD test suite
├── alembic/              # Database migrations
└── docker-compose.yml    # Development environment
```

### Frontend (Next.js/TypeScript)
```
frontend/
├── src/
│   ├── components/       # React components (chat, auth, dashboard)
│   ├── pages/            # Next.js pages
│   ├── services/         # API clients and WebSocket
│   ├── hooks/            # Custom React hooks
│   └── types/            # TypeScript interfaces
└── package.json
```

### CLI (Python/Click)
```
cli/
├── cli.py               # Main CLI entry point
├── auth.py              # Authentication commands
├── conversation.py      # Chat management
├── admin.py            # Admin operations
└── config.py           # Configuration management
```

## Database Schema

**Core Entities**:
- `users` - Authentication and user profiles
- `conversations` - Message threads
- `messages` - Individual chat messages with vector embeddings
- `memories` - Extracted facts with semantic search
- `tools` - Available AI capabilities
- `tool_executions` - Tool usage records
- `preferences` - User customization settings
- `sessions` - JWT session management

**Key Relationships**:
- User → Many Conversations → Many Messages
- User → Many Memories (semantic search)
- Messages → Many Tool Executions
- One-to-one User ↔ Preferences

## Technology Stack

### Core Technologies
- **Backend**: Python 3.11+ with FastAPI for async API server
- **Database**: PostgreSQL 15+ with pgvector extension for vector embeddings
- **Cache**: Redis for sessions, caching, and WebSocket pub/sub
- **Frontend**: Next.js 13+ with TypeScript and Tailwind CSS
- **Real-time**: WebSocket connections with Redis scaling
- **Background Tasks**: Celery with Redis broker
- **Authentication**: JWT tokens with refresh token rotation

### AI Integration
- **Multi-Provider LLM**: OpenAI GPT-4, Anthropic Claude with automatic failover
- **Vector Embeddings**: OpenAI text-embedding-ada-002 for semantic memory
- **Tool Framework**: Plugin-based architecture for AI capabilities

### Development Tools
- **Testing**: TDD with pytest (backend), Jest (frontend), contract tests
- **API Documentation**: OpenAPI/Swagger with automatic generation
- **Code Quality**: Black, isort, mypy, ESLint, Prettier
- **Containerization**: Docker and Docker Compose
- **Orchestration**: Kubernetes for production deployment

## Development Workflow

### TDD Approach
1. **Red Phase**: Write failing tests first
2. **Green Phase**: Implement minimal code to pass
3. **Refactor Phase**: Improve code while maintaining tests
4. **Order**: Contract tests → Integration tests → Unit tests

### Project Structure Rules
- **Library-First**: Every feature as reusable module
- **Direct Framework Usage**: No unnecessary abstractions
- **Real Dependencies**: Tests use actual PostgreSQL/Redis
- **CLI Access**: All features available via command line

## Key Implementation Details

### Vector Memory System
- Uses pgvector for semantic similarity search
- HNSW indexing for efficient nearest neighbor queries
- Automatic fact extraction from conversations
- Importance scoring and memory cleanup

### Tool Integration
- Plugin registry pattern for extensible tools
- Standardized input/output interfaces
- Async execution with progress tracking
- Error handling and fallback mechanisms

### Real-time Communication
- WebSocket connections with automatic reconnection
- Redis pub/sub for horizontal scaling
- Message streaming for AI responses
- Connection state management

### Security & Scalability
- JWT authentication with 15-minute expiry
- Refresh token rotation for security
- Per-user rate limiting with Redis
- Horizontal scaling via load balancer
- Database connection pooling

## Recent Changes

### Infrastructure & Core Features Complete ✅ (72.5% Implementation)
- Complete FastAPI backend with multi-provider LLM support (OpenAI, Anthropic, Google)
- PostgreSQL database with pgvector for semantic memory
- Redis caching, session management, and WebSocket support
- Celery background task processing
- Docker containerization with service orchestration
- JWT authentication and user isolation
- 21 REST API endpoints + WebSocket real-time communication
- Vector-based semantic memory system
- Tool execution framework with built-in tools
- Complete test foundation (67 contract tests + integration tests)

### Missing Features Specification Complete ✅
- **Spec 002-implement-the-missing**: Comprehensive specification for 8 remaining features
- **40 functional requirements** covering voice integration, multi-modal support, analytics
- **Research findings**: Performance targets, file size limits, quota policies resolved
- **Data model expansion**: 8 new entities (VoiceSession, UploadedFile, AnalyticsEvent, etc.)
- **API contracts**: 5 OpenAPI specs for voice, multimodal, analytics, tenancy, proactive APIs
- **Quickstart validation**: 6 user journey scenarios for end-to-end testing

### Current Phase: Implementation Planning ✅
- **Phase 0 Research**: All NEEDS CLARIFICATION items resolved with specific targets
- **Phase 1 Design**: Complete data model, API contracts, quickstart scenarios
- **Ready for Phase 2**: Task generation approach planned for /tasks command

## Development Commands

```bash
# Start development environment
docker-compose up -d

# Backend development
cd backend && uvicorn src.main:app --reload

# Frontend development
cd frontend && npm run dev

# Run tests
pytest backend/tests/
npm test --prefix frontend/

# CLI tool
pip install -e cli/
conversational --help
```

## Configuration

### Environment Variables
```env
# Core
DATABASE_URL=postgresql://postgres:password@localhost:5432/conversational
REDIS_URL=redis://localhost:6379

# AI Providers
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=your-key

# Tools
WEATHER_API_KEY=your-weather-key

# Security
JWT_SECRET_KEY=your-secret
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
```

### Performance Targets
- API Response: <200ms p95
- WebSocket Latency: <50ms
- Concurrent Users: 1000+
- Memory Usage: <500MB per instance
- Vector Search: <100ms for similarity queries

This system provides a complete conversational AI platform with enterprise-grade features while maintaining simplicity and extensibility.