"""
Database session management for async SQLAlchemy operations.
"""
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import structlog

logger = structlog.get_logger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/conversational"
)
DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "20"))
DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "30"))
DATABASE_ECHO = os.getenv("DATABASE_ECHO", "false").lower() == "true"

# Convert postgresql:// to postgresql+asyncpg:// if needed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=DATABASE_ECHO,
    pool_size=DATABASE_POOL_SIZE,
    max_overflow=DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,  # 1 hour
    # Use NullPool for testing to avoid connection issues
    poolclass=NullPool if os.getenv("ENVIRONMENT") == "test" else None,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session.

    Yields:
        AsyncSession: Database session

    Examples:
        >>> async def get_user(db: AsyncSession = Depends(get_db)):
        ...     return await db.execute(select(User))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", error=str(e))
            raise
        finally:
            await session.close()


async def create_db_session() -> AsyncSession:
    """
    Create a new database session for use outside of FastAPI dependency injection.

    Returns:
        AsyncSession: New database session

    Note:
        Remember to close the session when done:
        >>> session = await create_db_session()
        >>> try:
        ...     # Use session
        >>> finally:
        ...     await session.close()
    """
    return AsyncSessionLocal()


async def init_db() -> None:
    """
    Initialize database connection and test connectivity.

    Raises:
        Exception: If database connection fails
    """
    try:
        async with engine.begin() as conn:
            # Test connection
            await conn.execute("SELECT 1")
        logger.info("Database connection initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database connection", error=str(e))
        raise


async def close_db() -> None:
    """
    Close database engine and all connections.

    This should be called during application shutdown.
    """
    try:
        await engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error("Error closing database connections", error=str(e))
        raise


class DatabaseManager:
    """
    Database manager for handling connections in non-FastAPI contexts.

    Examples:
        >>> async with DatabaseManager() as db:
        ...     result = await db.execute(select(User))
    """

    def __init__(self):
        self._session: AsyncSession = None

    async def __aenter__(self) -> AsyncSession:
        """Async context manager entry."""
        self._session = await create_db_session()
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            try:
                if exc_type is None:
                    await self._session.commit()
                else:
                    await self._session.rollback()
            finally:
                await self._session.close()


# Health check function
async def health_check() -> bool:
    """
    Check if database is accessible.

    Returns:
        bool: True if database is accessible, False otherwise
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False


# Transaction utilities
class Transaction:
    """
    Context manager for explicit transaction handling.

    Examples:
        >>> async with Transaction() as tx:
        ...     user = User(email="test@example.com")
        ...     tx.session.add(user)
        ...     await tx.session.flush()
        ...     # Transaction is committed automatically
    """

    def __init__(self, session: AsyncSession = None):
        self._session = session
        self._should_close = False

    async def __aenter__(self):
        if self._session is None:
            self._session = await create_db_session()
            self._should_close = True

        self.session = self._session
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
        finally:
            if self._should_close and self._session:
                await self._session.close()


# Export commonly used items
__all__ = [
    "engine",
    "AsyncSessionLocal",
    "get_db",
    "create_db_session",
    "init_db",
    "close_db",
    "health_check",
    "DatabaseManager",
    "Transaction",
]