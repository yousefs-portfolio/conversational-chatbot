"""
Test configuration and fixtures for the conversational AI backend.
"""
import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment
os.environ["ENVIRONMENT"] = "test"

# Import after setting environment
from src.database.session import get_db
from src.main import app
from src.models.user import Base


# Test database configuration
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/conversational_test"

# Create test engine with StaticPool for SQLite compatibility or connection reuse
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {},
    echo=False,
)

TestAsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with TestAsyncSessionLocal() as session:
        yield session

    # Clean up - drop all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database session override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sync_client(db_session: AsyncSession) -> Generator[TestClient, None, None]:
    """Create a synchronous test client for simpler tests."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_user_data():
    """Sample user registration data."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User"
    }


@pytest_asyncio.fixture
async def sample_conversation_data():
    """Sample conversation data."""
    return {
        "title": "Test Conversation",
        "metadata": {"source": "test"}
    }


@pytest_asyncio.fixture
async def sample_message_data():
    """Sample message data."""
    return {
        "content": "Hello, this is a test message",
        "metadata": {"test": True}
    }


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, sample_user_data: dict):
    """Create authenticated user and return auth headers."""
    # Register user
    register_response = await client.post("/auth/register", json=sample_user_data)
    assert register_response.status_code == 201

    # Login user
    login_response = await client.post("/auth/login", json={
        "email": sample_user_data["email"],
        "password": sample_user_data["password"]
    })
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# Test data factories
class UserFactory:
    """Factory for creating test users."""

    @staticmethod
    def build(**kwargs):
        """Build user data without saving to database."""
        default_data = {
            "email": f"user{os.urandom(4).hex()}@example.com",
            "password": "testpassword123",
            "full_name": "Test User"
        }
        default_data.update(kwargs)
        return default_data


class ConversationFactory:
    """Factory for creating test conversations."""

    @staticmethod
    def build(**kwargs):
        """Build conversation data."""
        default_data = {
            "title": f"Test Conversation {os.urandom(4).hex()}",
            "metadata": {}
        }
        default_data.update(kwargs)
        return default_data


class MessageFactory:
    """Factory for creating test messages."""

    @staticmethod
    def build(**kwargs):
        """Build message data."""
        default_data = {
            "content": f"Test message {os.urandom(4).hex()}",
            "metadata": {}
        }
        default_data.update(kwargs)
        return default_data


# Test utilities
def assert_valid_uuid(uuid_string: str):
    """Assert that a string is a valid UUID."""
    import uuid
    try:
        uuid.UUID(uuid_string)
    except ValueError:
        pytest.fail(f"'{uuid_string}' is not a valid UUID")


def assert_datetime_format(datetime_string: str):
    """Assert that a string is in valid ISO datetime format."""
    from datetime import datetime
    try:
        datetime.fromisoformat(datetime_string.replace('Z', '+00:00'))
    except ValueError:
        pytest.fail(f"'{datetime_string}' is not a valid ISO datetime")


# Mark all tests as asyncio
pytest_plugins = ("pytest_asyncio",)