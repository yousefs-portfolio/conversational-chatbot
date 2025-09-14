"""
Contract test for POST /conversations/{id}/messages endpoint.

This test validates the API contract for sending messages in a conversation.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
import uuid


class TestMessageSendContract:
    """Test contract compliance for message sending endpoint."""

    @pytest.fixture
    def sample_conversation_id(self):
        """Sample UUID for testing."""
        return str(uuid.uuid4())

    @pytest.fixture
    def valid_message_data(self):
        """Valid message data."""
        return {
            "content": "Hello, how can you help me today?",
            "role": "user"
        }

    @pytest.fixture
    def message_with_metadata(self):
        """Message data with metadata."""
        return {
            "content": "Analyze this code snippet",
            "role": "user",
            "metadata": {
                "source": "code_editor",
                "language": "python",
                "file_name": "example.py"
            }
        }

    @pytest.mark.asyncio
    async def test_send_message_success(self, client: AsyncClient, auth_headers: dict,
                                       sample_conversation_id: str, valid_message_data: dict):
        """Test successful message sending returns 201."""
        # Act
        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            json=valid_message_data
        )

        # Assert - This MUST FAIL initially
        assert response.status_code == 201
        data = response.json()
        assert "user_message" in data
        assert "assistant_message" in data

    @pytest.mark.asyncio
    async def test_send_message_response_format(self, client: AsyncClient, auth_headers: dict,
                                               sample_conversation_id: str, valid_message_data: dict):
        """Test message sending response has correct format."""
        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            json=valid_message_data
        )

        assert response.status_code == 201
        data = response.json()

        # Validate user message structure
        user_msg = data["user_message"]
        required_fields = ["id", "content", "role", "created_at", "metadata"]
        for field in required_fields:
            assert field in user_msg

        # Validate assistant response structure
        assistant_msg = data["assistant_message"]
        for field in required_fields:
            assert field in assistant_msg

        # Validate roles
        assert user_msg["role"] == "user"
        assert assistant_msg["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_send_message_with_metadata(self, client: AsyncClient, auth_headers: dict,
                                             sample_conversation_id: str, message_with_metadata: dict):
        """Test message sending with metadata."""
        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            json=message_with_metadata
        )

        assert response.status_code == 201
        data = response.json()
        user_msg = data["user_message"]
        assert user_msg["metadata"] == message_with_metadata["metadata"]

    @pytest.mark.asyncio
    async def test_send_message_conversation_not_found(self, client: AsyncClient, auth_headers: dict,
                                                      valid_message_data: dict):
        """Test message sending to non-existent conversation returns 404."""
        non_existent_id = str(uuid.uuid4())
        response = await client.post(
            f"/conversations/{non_existent_id}/messages",
            headers=auth_headers,
            json=valid_message_data
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_send_message_without_auth_unauthorized(self, client: AsyncClient,
                                                         sample_conversation_id: str, valid_message_data: dict):
        """Test message sending without authentication returns 401."""
        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            json=valid_message_data
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_send_message_invalid_token_unauthorized(self, client: AsyncClient,
                                                          sample_conversation_id: str, valid_message_data: dict):
        """Test message sending with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            headers=invalid_headers,
            json=valid_message_data
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_send_message_invalid_conversation_uuid(self, client: AsyncClient, auth_headers: dict,
                                                         valid_message_data: dict):
        """Test message sending with invalid conversation UUID."""
        invalid_id = "not-a-uuid"
        response = await client.post(
            f"/conversations/{invalid_id}/messages",
            headers=auth_headers,
            json=valid_message_data
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_send_message_forbidden(self, client: AsyncClient, auth_headers: dict,
                                         sample_conversation_id: str, valid_message_data: dict):
        """Test message sending to conversation not owned by user returns 403."""
        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            json=valid_message_data
        )

        # Could be 404 (not found) or 403 (forbidden) - both are acceptable
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_send_message_invalid_data(self, client: AsyncClient, auth_headers: dict,
                                           sample_conversation_id: str):
        """Test message sending with invalid data."""
        # Test missing content
        invalid_data = {"role": "user"}
        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            json=invalid_data
        )
        assert response.status_code == 422

        # Test empty content
        invalid_data = {"content": "", "role": "user"}
        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            json=invalid_data
        )
        assert response.status_code == 422

        # Test invalid role
        invalid_data = {"content": "Hello", "role": "invalid"}
        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            json=invalid_data
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_send_message_too_long(self, client: AsyncClient, auth_headers: dict,
                                        sample_conversation_id: str):
        """Test message sending with content too long."""
        # Assuming 10000 character limit
        long_content = "x" * 10001
        invalid_data = {"content": long_content, "role": "user"}

        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            json=invalid_data
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_send_message_streaming_response(self, client: AsyncClient, auth_headers: dict,
                                                  sample_conversation_id: str, valid_message_data: dict):
        """Test message sending with streaming response option."""
        # Add stream parameter
        params = {"stream": "true"}
        response = await client.post(
            f"/conversations/{sample_conversation_id}/messages",
            headers=auth_headers,
            json=valid_message_data,
            params=params
        )

        # Streaming responses should return different status or content-type
        assert response.status_code in [200, 201]
        assert "text/event-stream" in response.headers.get("content-type", "") or response.status_code == 201