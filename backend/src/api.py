"""FastAPI application and main API routes."""

import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from fastapi.security import HTTPBearer
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db, get_async_db, init_db, db_manager
from .middleware import setup_middleware
from .models import User, Conversation, Message
from .auth import (
    authenticate_user, create_access_token, get_current_user,
    get_current_active_user, create_user, auth_manager
)
from .conversation_service import conversation_service
from .memory_service import memory_service
from .tool_service import tool_service
from .tasks import process_file_upload, generate_embeddings_batch, analyze_user_patterns
from .websocket import websocket_endpoint, init_websocket

# Import new routers for missing features
from .api.routes import voice, files, analytics, tenants, proactive

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    logger.info("Starting up Conversational AI API")

    # Initialize database
    await init_db()

    # Initialize WebSocket manager
    await init_websocket()

    # Initialize built-in tools
    await tool_service.initialize_builtin_tools()

    logger.info("Application startup completed")

    yield

    # Shutdown
    logger.info("Shutting down Conversational AI API")
    await db_manager.close_connections()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A production-ready conversational AI system with multi-provider LLM support, tool execution, and vector memory.",
    lifespan=lifespan
)

# Setup middleware
setup_middleware(app)

# Include routers for new features
app.include_router(voice.router, prefix="/api/v1", tags=["voice"])
app.include_router(files.router, prefix="/api/v1", tags=["files"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(tenants.router, prefix="/api/v1", tags=["tenants"])
app.include_router(proactive.router, prefix="/api/v1", tags=["proactive"])


# Pydantic models for request/response
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None


class ConversationCreateRequest(BaseModel):
    title: str
    system_prompt: Optional[str] = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 1000
    metadata: Optional[Dict[str, Any]] = None


class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class MessageRequest(BaseModel):
    message: str
    use_tools: bool = True
    use_memory: bool = True
    stream: bool = False


class ToolCreateRequest(BaseModel):
    name: str
    description: str
    schema: Dict[str, Any]
    implementation: str
    category: str = "custom"


class MemoryCreateRequest(BaseModel):
    content: str
    memory_type: str = "episodic"
    importance: int = 1
    conversation_id: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db_healthy = await db_manager.health_check()

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "version": settings.APP_VERSION,
        "timestamp": "2024-01-01T00:00:00Z"  # Would use datetime.utcnow().isoformat()
    }


# Authentication endpoints
@app.post("/api/v1/auth/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """User login endpoint."""
    user = authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    return auth_manager.create_user_token(user)


@app.post("/api/v1/auth/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """User registration endpoint."""
    # Validate password strength
    if not auth_manager.validate_password_strength(request.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters with uppercase, lowercase, and digit"
        )

    try:
        user = create_user(
            db=db,
            email=request.email,
            username=request.username,
            password=request.password,
            full_name=request.full_name
        )
        return auth_manager.create_user_token(user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.get("/api/v1/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "is_superuser": current_user.is_superuser,
        "preferences": current_user.preferences,
        "created_at": current_user.created_at.isoformat()
    }


# Conversation endpoints
@app.post("/api/v1/conversations")
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Create a new conversation."""
    conversation_id = await conversation_service.create_conversation(
        user_id=str(current_user.id),
        title=request.title,
        system_prompt=request.system_prompt,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        metadata=request.metadata
    )

    return {"conversation_id": conversation_id}


@app.get("/api/v1/conversations")
async def list_conversations(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_active_user)
):
    """List user's conversations."""
    conversations = await conversation_service.list_conversations(
        user_id=str(current_user.id),
        limit=limit,
        offset=offset,
        active_only=active_only
    )

    return {"conversations": conversations}


@app.get("/api/v1/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific conversation with its messages."""
    conversation = await conversation_service.get_conversation(
        conversation_id=conversation_id,
        user_id=str(current_user.id)
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    return conversation


@app.put("/api/v1/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: ConversationUpdateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Update a conversation."""
    success = await conversation_service.update_conversation(
        conversation_id=conversation_id,
        user_id=str(current_user.id),
        title=request.title,
        system_prompt=request.system_prompt,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        metadata=request.metadata,
        is_active=request.is_active
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    return {"success": True}


@app.delete("/api/v1/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Delete a conversation."""
    success = await conversation_service.delete_conversation(
        conversation_id=conversation_id,
        user_id=str(current_user.id)
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    return {"success": True}


@app.post("/api/v1/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: MessageRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Send a message to a conversation."""
    if request.stream:
        # Return streaming response
        async def generate():
            async for chunk in await conversation_service.generate_response(
                conversation_id=conversation_id,
                user_id=str(current_user.id),
                user_message=request.message,
                use_tools=request.use_tools,
                use_memory=request.use_memory,
                stream=True
            ):
                yield f"data: {chunk}\n\n"

        return StreamingResponse(generate(), media_type="text/plain")
    else:
        # Return single response
        response = await conversation_service.generate_response(
            conversation_id=conversation_id,
            user_id=str(current_user.id),
            user_message=request.message,
            use_tools=request.use_tools,
            use_memory=request.use_memory,
            stream=False
        )

        return response


# Tool endpoints
@app.get("/api/v1/tools")
async def list_tools(
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user)
):
    """List available tools."""
    tools = await tool_service.list_tools(
        user_id=str(current_user.id),
        category=category
    )

    return {"tools": tools}


@app.post("/api/v1/tools")
async def create_tool(
    request: ToolCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Create a custom tool."""
    try:
        tool_id = await tool_service.create_tool(
            user_id=str(current_user.id),
            name=request.name,
            description=request.description,
            schema=request.schema,
            implementation=request.implementation,
            category=request.category
        )

        return {"tool_id": tool_id}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.post("/api/v1/tools/{tool_name}/execute")
async def execute_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    """Execute a tool."""
    result = await tool_service.execute_tool(
        tool_name=tool_name,
        parameters=parameters,
        user_id=str(current_user.id)
    )

    return result


@app.get("/api/v1/tools/executions")
async def get_tool_executions(
    tool_id: Optional[str] = Query(None),
    limit: int = Query(10, le=50),
    current_user: User = Depends(get_current_active_user)
):
    """Get tool execution history."""
    executions = await tool_service.get_tool_execution_history(
        user_id=str(current_user.id),
        tool_id=tool_id,
        limit=limit
    )

    return {"executions": executions}


# Memory endpoints
@app.post("/api/v1/memory")
async def create_memory(
    request: MemoryCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Store a memory."""
    memory_id = await memory_service.store_memory(
        content=request.content,
        user_id=str(current_user.id),
        memory_type=request.memory_type,
        importance=request.importance,
        conversation_id=request.conversation_id,
        tags=request.tags,
        metadata=request.metadata
    )

    return {"memory_id": memory_id}


@app.get("/api/v1/memory/search")
async def search_memories(
    query: str = Query(...),
    limit: int = Query(10, le=50),
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    memory_type: Optional[str] = Query(None),
    conversation_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user)
):
    """Search memories by similarity."""
    memories = await memory_service.retrieve_relevant_memories(
        query=query,
        user_id=str(current_user.id),
        limit=limit,
        threshold=threshold,
        memory_type=memory_type,
        conversation_id=conversation_id
    )

    return {"memories": memories}


@app.get("/api/v1/memory/stats")
async def get_memory_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get memory statistics for the user."""
    stats = await memory_service.get_memory_stats(str(current_user.id))
    return stats


@app.delete("/api/v1/memory/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Delete a memory."""
    success = await memory_service.delete_memory(
        memory_id=memory_id,
        user_id=str(current_user.id)
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )

    return {"success": True}


# File upload endpoints
@app.post("/api/v1/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Upload and process a file."""
    # Validate file size
    if hasattr(file, 'size') and file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE} bytes"
        )

    # Determine file type
    file_type = "text"
    if file.filename:
        if file.filename.endswith('.pdf'):
            file_type = "pdf"
        elif file.filename.endswith('.docx'):
            file_type = "docx"

    # Save file temporarily
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name

    # Process file in background
    background_tasks.add_task(
        process_file_upload.delay,
        temp_file_path,
        str(current_user.id),
        file_type
    )

    return {
        "message": "File uploaded and processing started",
        "filename": file.filename,
        "size": len(content),
        "type": file_type
    }


# LLM model endpoints
@app.get("/api/v1/models")
async def get_available_models():
    """Get available LLM models."""
    from .llm_service import llm_service
    models = llm_service.get_available_models()
    return {"models": models}


# WebSocket endpoint
app.websocket("/ws/{token}")(websocket_endpoint)


# Admin endpoints (for superusers)
@app.get("/api/v1/admin/stats")
async def get_admin_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get system statistics (admin only)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    # Get system stats
    from .websocket import manager

    stats = {
        "active_websocket_connections": manager.get_connection_count(),
        "connected_users": len(manager.get_connected_users()),
        "database_status": "connected" if await db_manager.health_check() else "disconnected",
        "version": settings.APP_VERSION
    }

    return stats


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )