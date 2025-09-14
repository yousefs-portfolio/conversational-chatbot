"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
import asyncpg
from typing import AsyncGenerator, Generator

from .config import settings


# Synchronous database engine
engine = create_engine(
    str(settings.DATABASE_URL),
    pool_pre_ping=True,
    pool_recycle=300,
)

# Asynchronous database engine
async_engine = create_async_engine(
    str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://"),
    pool_pre_ping=True,
    pool_recycle=300,
    poolclass=NullPool,  # Use NullPool for async
)

# Session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency for synchronous database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for asynchronous database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_db_and_tables():
    """Create database and tables if they don't exist."""
    from .models import Base

    # Create database if it doesn't exist
    try:
        # Parse database URL to get connection details
        db_url = str(settings.DATABASE_URL)
        if "postgresql" in db_url:
            # Extract connection details
            parts = db_url.replace("postgresql://", "").split("/")
            db_name = parts[-1]
            conn_str = "/".join(parts[:-1])

            # Connect to postgres database to create our database
            conn = await asyncpg.connect(f"postgresql://{conn_str}/postgres")
            try:
                # Check if database exists
                result = await conn.fetchval(
                    "SELECT 1 FROM pg_database WHERE datname = $1", db_name
                )
                if not result:
                    await conn.execute(f'CREATE DATABASE "{db_name}"')
                    print(f"Created database: {db_name}")
            finally:
                await conn.close()
    except Exception as e:
        print(f"Error creating database: {e}")

    # Create tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def init_db():
    """Initialize database with required extensions and tables."""
    await create_db_and_tables()

    # Create vector extension if not exists
    async with AsyncSessionLocal() as session:
        try:
            await session.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await session.commit()
            print("Created vector extension")
        except Exception as e:
            print(f"Error creating vector extension: {e}")
            await session.rollback()


class DatabaseManager:
    """Database manager for connection pooling and health checks."""

    def __init__(self):
        self.engine = engine
        self.async_engine = async_engine

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with AsyncSessionLocal() as session:
                await session.execute("SELECT 1")
                return True
        except Exception as e:
            print(f"Database health check failed: {e}")
            return False

    async def close_connections(self):
        """Close all database connections."""
        await self.async_engine.dispose()
        self.engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()