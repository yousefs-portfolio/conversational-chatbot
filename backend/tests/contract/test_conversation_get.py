"""
Contract test for GET /conversations/{id} endpoint.

This test validates the API contract for retrieving a specific conversation.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
import uuid


class TestConversationGetContract:
    """Test contract compliance for conversation retrieval endpoint."""

    @pytest.fixture
    def sample_conversation_id(self):
        """Sample UUID for testing."""
        return str(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_conversation_success(self, client: AsyncClient, auth_headers: dict, sample_conversation_id: str):
        """Test successful conversation retrieval returns 200."""
        # Act
        response = await client.get(f"/conversations/{sample_conversation_id}", headers=auth_headers)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_conversation_id

    @pytest.mark.asyncio
    async def test_get_conversation_response_format(self, client: AsyncClient, auth_headers: dict, sample_conversation_id: str):
        """Test conversation retrieval response has correct format."""
        response = await client.get(f"/conversations/{sample_conversation_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        required_fields = [
            "id", "title", "system_prompt", "created_at",
            "updated_at", "message_count", "user_id", "messages"
        ]
        for field in required_fields:
            assert field in data

        # Validate data types
        assert isinstance(data["id"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["message_count"], int)
        assert isinstance(data["messages"], list)

    @pytest.mark.asyncio
    async def test_get_conversation_with_messages(self, client: AsyncClient, auth_headers: dict, sample_conversation_id: str):
        """Test conversation retrieval includes messages."""
        response = await client.get(f"/conversations/{sample_conversation_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data

        # If messages exist, validate message structure
        if data["messages"]:
            message = data["messages"][0]
            required_message_fields = [
                "id", "content", "role", "created_at", "metadata"
            ]
            for field in required_message_fields:
                assert field in message

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test conversation retrieval with non-existent ID returns 404."""
        non_existent_id = str(uuid.uuid4())
        response = await client.get(f"/conversations/{non_existent_id}", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_conversation_without_auth_unauthorized(self, client: AsyncClient, sample_conversation_id: str):
        """Test conversation retrieval without authentication returns 401."""
        response = await client.get(f"/conversations/{sample_conversation_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_conversation_invalid_token_unauthorized(self, client: AsyncClient, sample_conversation_id: str):
        """Test conversation retrieval with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.get(f"/conversations/{sample_conversation_id}", headers=invalid_headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_conversation_invalid_uuid(self, client: AsyncClient, auth_headers: dict):
        """Test conversation retrieval with invalid UUID format."""
        invalid_id = "not-a-uuid"
        response = await client.get(f"/conversations/{invalid_id}", headers=auth_headers)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_conversation_forbidden(self, client: AsyncClient, auth_headers: dict, sample_conversation_id: str):
        """Test conversation retrieval for conversation not owned by user returns 403."""
        # This test assumes the conversation exists but belongs to another user
        # The actual implementation will need to handle this scenario
        response = await client.get(f"/conversations/{sample_conversation_id}", headers=auth_headers)

        # Could be 404 (not found) or 403 (forbidden) - both are acceptable
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_get_conversation_with_pagination(self, client: AsyncClient, auth_headers: dict, sample_conversation_id: str):
        """Test conversation retrieval with message pagination."""
        params = {"message_limit": 10, "message_offset": 0}
        response = await client.get(f"/conversations/{sample_conversation_id}", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) <= 10

    @pytest.mark.asyncio
    async def test_get_conversation_metadata_included(self, client: AsyncClient, auth_headers: dict, sample_conversation_id: str):
        """Test conversation retrieval includes all metadata."""
        response = await client.get(f"/conversations/{sample_conversation_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check for optional metadata fields
        optional_fields = ["summary", "tags", "last_message_at", "token_count"]
        for field in optional_fields:
            # These fields should be present (even if null)
            assert field in data