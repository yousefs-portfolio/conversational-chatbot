"""
Contract test for GET /conversations/{id}/messages endpoint.

This test validates the API contract for retrieving messages from a conversation.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
import uuid


class TestMessagesListContract:
    """Test contract compliance for messages list endpoint."""

    @pytest.fixture
    def sample_conversation_id(self):
        """Sample UUID for testing."""
        return str(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_list_messages_success(self, client: AsyncClient, auth_headers: dict,
                                        sample_conversation_id: str):
        """Test successful message listing returns 200."""
        # Act
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers
        )

        # Assert - This MUST FAIL initially
        assert response.status_code == 200
        assert "data" in response.json()
        assert isinstance(response.json()["data"], list)

    @pytest.mark.asyncio
    async def test_list_messages_with_pagination(self, client: AsyncClient, auth_headers: dict,
                                                sample_conversation_id: str):
        """Test message listing with pagination parameters."""
        params = {"page": 1, "limit": 20}
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            params=params
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert "total" in data["pagination"]
        assert "page" in data["pagination"]
        assert "limit" in data["pagination"]

    @pytest.mark.asyncio
    async def test_list_messages_empty_result(self, client: AsyncClient, auth_headers: dict,
                                             sample_conversation_id: str):
        """Test message listing returns empty array when no messages."""
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_list_messages_response_format(self, client: AsyncClient, auth_headers: dict,
                                                sample_conversation_id: str):
        """Test message listing response has correct format."""
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

        # If messages exist, validate message structure
        if data["data"]:
            message = data["data"][0]
            required_fields = ["id", "content", "role", "created_at", "metadata"]
            for field in required_fields:
                assert field in message

            # Validate role is valid
            assert message["role"] in ["user", "assistant", "system"]

    @pytest.mark.asyncio
    async def test_list_messages_conversation_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test message listing for non-existent conversation returns 404."""
        non_existent_id = str(uuid.uuid4())
        response = await client.get(
            f"/conversations/{non_existent_id}/messages",
            headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_messages_without_auth_unauthorized(self, client: AsyncClient,
                                                          sample_conversation_id: str):
        """Test message listing without authentication returns 401."""
        response = await client.get(f"/conversations/{sample_conversation_id}/messages")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_messages_invalid_token_unauthorized(self, client: AsyncClient,
                                                           sample_conversation_id: str):
        """Test message listing with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=invalid_headers
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_messages_invalid_conversation_uuid(self, client: AsyncClient, auth_headers: dict):
        """Test message listing with invalid conversation UUID."""
        invalid_id = "not-a-uuid"
        response = await client.get(f"/conversations/{invalid_id}/messages", headers=auth_headers)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_messages_forbidden(self, client: AsyncClient, auth_headers: dict,
                                          sample_conversation_id: str):
        """Test message listing for conversation not owned by user returns 403."""
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers
        )

        # Could be 404 (not found) or 403 (forbidden) - both are acceptable
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_list_messages_invalid_pagination(self, client: AsyncClient, auth_headers: dict,
                                                   sample_conversation_id: str):
        """Test message listing with invalid pagination parameters."""
        # Test negative page
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            params={"page": -1}
        )
        assert response.status_code == 422

        # Test page 0
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            params={"page": 0}
        )
        assert response.status_code == 422

        # Test invalid limit
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            params={"limit": 0}
        )
        assert response.status_code == 422

        # Test limit too high
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            params={"limit": 1000}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_messages_chronological_order(self, client: AsyncClient, auth_headers: dict,
                                                    sample_conversation_id: str):
        """Test message listing returns messages in chronological order."""
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # If multiple messages exist, check they're in chronological order
        if len(data["data"]) > 1:
            messages = data["data"]
            for i in range(1, len(messages)):
                # created_at should be in ascending order (oldest first)
                assert messages[i-1]["created_at"] <= messages[i]["created_at"]

    @pytest.mark.asyncio
    async def test_list_messages_with_role_filter(self, client: AsyncClient, auth_headers: dict,
                                                 sample_conversation_id: str):
        """Test message listing with role filter."""
        params = {"role": "user"}
        response = await client.get(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            params=params
        )

        assert response.status_code == 200
        data = response.json()

        # All messages should have the filtered role
        for message in data["data"]:
            assert message["role"] == "user"