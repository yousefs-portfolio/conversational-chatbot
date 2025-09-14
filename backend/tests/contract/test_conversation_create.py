"""
Contract test for POST /conversations endpoint.

This test validates the API contract for creating new conversations.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient


class TestConversationCreateContract:
    """Test contract compliance for conversation creation endpoint."""

    @pytest.fixture
    def valid_conversation_data(self):
        """Valid conversation creation data."""
        return {
            "title": "Test Conversation",
            "system_prompt": "You are a helpful AI assistant."
        }

    @pytest.fixture
    def minimal_conversation_data(self):
        """Minimal valid conversation data."""
        return {}  # Title should be optional and auto-generated

    @pytest.mark.asyncio
    async def test_create_conversation_success(self, client: AsyncClient, auth_headers: dict, valid_conversation_data: dict):
        """Test successful conversation creation returns 201."""
        # Act
        response = await client.post("/conversations", headers=auth_headers, json=valid_conversation_data)

        # Assert - This MUST FAIL initially
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["title"] == valid_conversation_data["title"]
        assert data["system_prompt"] == valid_conversation_data["system_prompt"]

    @pytest.mark.asyncio
    async def test_create_conversation_minimal_data(self, client: AsyncClient, auth_headers: dict, minimal_conversation_data: dict):
        """Test conversation creation with minimal data."""
        response = await client.post("/conversations", headers=auth_headers, json=minimal_conversation_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "title" in data
        assert data["title"] is not None  # Should be auto-generated

    @pytest.mark.asyncio
    async def test_create_conversation_response_format(self, client: AsyncClient, auth_headers: dict, valid_conversation_data: dict):
        """Test conversation creation response has correct format."""
        response = await client.post("/conversations", headers=auth_headers, json=valid_conversation_data)

        assert response.status_code == 201
        data = response.json()

        # Validate response structure
        required_fields = [
            "id", "title", "system_prompt", "created_at",
            "updated_at", "message_count", "user_id"
        ]
        for field in required_fields:
            assert field in data

        # Validate data types
        assert isinstance(data["id"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["message_count"], int)
        assert data["message_count"] == 0  # New conversation should have 0 messages

    @pytest.mark.asyncio
    async def test_create_conversation_without_auth_unauthorized(self, client: AsyncClient, valid_conversation_data: dict):
        """Test conversation creation without authentication returns 401."""
        response = await client.post("/conversations", json=valid_conversation_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_conversation_invalid_token_unauthorized(self, client: AsyncClient, valid_conversation_data: dict):
        """Test conversation creation with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.post("/conversations", headers=invalid_headers, json=valid_conversation_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_conversation_invalid_data(self, client: AsyncClient, auth_headers: dict):
        """Test conversation creation with various invalid data."""
        # Test with invalid title type
        invalid_data = {"title": 123}
        response = await client.post("/conversations", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test with empty title string
        invalid_data = {"title": ""}
        response = await client.post("/conversations", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test with title too long
        invalid_data = {"title": "x" * 501}  # Assuming 500 char limit
        response = await client.post("/conversations", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_conversation_with_custom_system_prompt(self, client: AsyncClient, auth_headers: dict):
        """Test conversation creation with custom system prompt."""
        conversation_data = {
            "title": "Custom Assistant",
            "system_prompt": "You are a specialized coding assistant."
        }

        response = await client.post("/conversations", headers=auth_headers, json=conversation_data)

        assert response.status_code == 201
        data = response.json()
        assert data["system_prompt"] == conversation_data["system_prompt"]

    @pytest.mark.asyncio
    async def test_create_conversation_empty_request_body(self, client: AsyncClient, auth_headers: dict):
        """Test conversation creation with empty request body."""
        response = await client.post("/conversations", headers=auth_headers, json={})

        # Should succeed with auto-generated title
        assert response.status_code == 201
        data = response.json()
        assert "title" in data
        assert len(data["title"]) > 0