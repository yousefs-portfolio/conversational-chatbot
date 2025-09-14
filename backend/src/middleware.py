"""Custom middleware for the FastAPI application."""

import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .config import settings

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable):
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Log request
        start_time = time.time()
        logger.info(
            f"Request {request_id}: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request {request_id} failed: {str(e)}")
            raise

        # Calculate processing time
        process_time = time.time() - start_time

        # Log response
        logger.info(
            f"Request {request_id} completed: {response.status_code} "
            f"in {process_time:.4f}s"
        )

        # Add custom headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers."""

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' ws: wss:;"
        )

        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware."""

    def __init__(self, app, calls_per_minute: int = 100):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.clients = {}  # client_ip -> [timestamps]

    async def dispatch(self, request: Request, call_next: Callable):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Clean old timestamps
        current_time = time.time()
        if client_ip in self.clients:
            self.clients[client_ip] = [
                timestamp for timestamp in self.clients[client_ip]
                if current_time - timestamp < 60  # Last minute
            ]

        # Check rate limit
        if client_ip not in self.clients:
            self.clients[client_ip] = []

        if len(self.clients[client_ip]) >= self.calls_per_minute:
            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={"Retry-After": "60"}
            )

        # Add current request
        self.clients[client_ip].append(current_time)

        return await call_next(request)


class DatabaseMiddleware(BaseHTTPMiddleware):
    """Middleware for database connection management."""

    async def dispatch(self, request: Request, call_next: Callable):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Log database errors
            if "database" in str(e).lower() or "connection" in str(e).lower():
                logger.error(f"Database error in request {getattr(request.state, 'request_id', 'unknown')}: {str(e)}")

            # Re-raise the exception
            raise


class ResponseCompressionMiddleware(BaseHTTPMiddleware):
    """Middleware for response compression."""

    def __init__(self, app, minimum_size: int = 1000):
        super().__init__(app)
        self.minimum_size = minimum_size

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)

        # Only compress if response is large enough and appropriate content type
        if (
            hasattr(response, 'body') and
            len(getattr(response, 'body', b'')) > self.minimum_size and
            response.headers.get('content-type', '').startswith(('application/json', 'text/'))
        ):
            response.headers["Content-Encoding"] = "gzip"

        return response


def setup_middleware(app):
    """Set up all middleware for the FastAPI application."""

    # CORS middleware (must be first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Custom middleware (order matters - first added is last to process)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, calls_per_minute=100)
    app.add_middleware(DatabaseMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    logger.info("Middleware setup completed")