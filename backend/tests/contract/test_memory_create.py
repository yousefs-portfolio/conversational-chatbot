"""
Contract test for POST /memory endpoint.

This test validates the API contract for creating user memories.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient


class TestMemoryCreateContract:
    """Test contract compliance for memory creation endpoint."""

    @pytest.fixture
    def valid_memory_data(self):
        """Valid memory creation data."""
        return {
            "content": "User prefers Python over JavaScript for backend development",
            "type": "preference",
            "importance": 0.8,
            "metadata": {
                "source": "conversation",
                "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                "context": "programming language discussion"
            }
        }

    @pytest.fixture
    def minimal_memory_data(self):
        """Minimal valid memory data."""
        return {
            "content": "User likes coffee",
            "type": "fact"
        }

    @pytest.fixture
    def fact_memory_data(self):
        """Fact-type memory data."""
        return {
            "content": "User works as a software engineer at TechCorp",
            "type": "fact",
            "importance": 0.9
        }

    @pytest.mark.asyncio
    async def test_create_memory_success(self, client: AsyncClient, auth_headers: dict, valid_memory_data: dict):
        """Test successful memory creation returns 201."""
        # Act
        response = await client.post("/memory", headers=auth_headers, json=valid_memory_data)

        # Assert - This MUST FAIL initially
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == valid_memory_data["content"]
        assert data["type"] == valid_memory_data["type"]
        assert data["importance"] == valid_memory_data["importance"]

    @pytest.mark.asyncio
    async def test_create_memory_minimal_data(self, client: AsyncClient, auth_headers: dict, minimal_memory_data: dict):
        """Test memory creation with minimal data."""
        response = await client.post("/memory", headers=auth_headers, json=minimal_memory_data)

        assert response.status_code == 201
        data = response.json()
        assert data["content"] == minimal_memory_data["content"]
        assert data["type"] == minimal_memory_data["type"]
        # Importance should have a default value
        assert "importance" in data
        assert 0.0 <= data["importance"] <= 1.0

    @pytest.mark.asyncio
    async def test_create_memory_response_format(self, client: AsyncClient, auth_headers: dict, valid_memory_data: dict):
        """Test memory creation response has correct format."""
        response = await client.post("/memory", headers=auth_headers, json=valid_memory_data)

        assert response.status_code == 201
        data = response.json()

        # Validate response structure
        required_fields = [
            "id", "content", "type", "importance", "created_at",
            "updated_at", "last_accessed_at", "user_id", "embedding"
        ]
        for field in required_fields:
            assert field in data

        # Validate data types
        assert isinstance(data["id"], str)
        assert isinstance(data["content"], str)
        assert isinstance(data["importance"], (int, float))
        assert isinstance(data["embedding"], list)  # Vector embedding
        assert len(data["embedding"]) > 0  # Should have embedding dimensions

    @pytest.mark.asyncio
    async def test_create_memory_with_metadata(self, client: AsyncClient, auth_headers: dict, valid_memory_data: dict):
        """Test memory creation with metadata."""
        response = await client.post("/memory", headers=auth_headers, json=valid_memory_data)

        assert response.status_code == 201
        data = response.json()
        assert "metadata" in data
        assert data["metadata"] == valid_memory_data["metadata"]

    @pytest.mark.asyncio
    async def test_create_memory_different_types(self, client: AsyncClient, auth_headers: dict):
        """Test memory creation with different valid types."""
        memory_types = ["fact", "preference", "context", "relationship", "skill"]

        for memory_type in memory_types:
            memory_data = {
                "content": f"Test {memory_type} memory",
                "type": memory_type,
                "importance": 0.5
            }

            response = await client.post("/memory", headers=auth_headers, json=memory_data)
            assert response.status_code == 201
            data = response.json()
            assert data["type"] == memory_type

    @pytest.mark.asyncio
    async def test_create_memory_without_auth_unauthorized(self, client: AsyncClient, valid_memory_data: dict):
        """Test memory creation without authentication returns 401."""
        response = await client.post("/memory", json=valid_memory_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_memory_invalid_token_unauthorized(self, client: AsyncClient, valid_memory_data: dict):
        """Test memory creation with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.post("/memory", headers=invalid_headers, json=valid_memory_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_memory_invalid_data(self, client: AsyncClient, auth_headers: dict):
        """Test memory creation with various invalid data."""
        # Test missing content
        invalid_data = {"type": "fact"}
        response = await client.post("/memory", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test empty content
        invalid_data = {"content": "", "type": "fact"}
        response = await client.post("/memory", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test missing type
        invalid_data = {"content": "Some content"}
        response = await client.post("/memory", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test invalid type
        invalid_data = {"content": "Some content", "type": "invalid_type"}
        response = await client.post("/memory", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_memory_invalid_importance(self, client: AsyncClient, auth_headers: dict):
        """Test memory creation with invalid importance values."""
        # Test importance > 1.0
        invalid_data = {
            "content": "Test content",
            "type": "fact",
            "importance": 1.5
        }
        response = await client.post("/memory", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test negative importance
        invalid_data = {
            "content": "Test content",
            "type": "fact",
            "importance": -0.1
        }
        response = await client.post("/memory", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_memory_content_too_long(self, client: AsyncClient, auth_headers: dict):
        """Test memory creation with content too long."""
        # Assuming 10000 character limit
        long_content = "x" * 10001
        invalid_data = {
            "content": long_content,
            "type": "fact"
        }

        response = await client.post("/memory", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_memory_duplicate_detection(self, client: AsyncClient, auth_headers: dict, valid_memory_data: dict):
        """Test memory creation handles potential duplicates."""
        # Create first memory
        response1 = await client.post("/memory", headers=auth_headers, json=valid_memory_data)
        assert response1.status_code == 201

        # Try to create very similar memory
        similar_data = valid_memory_data.copy()
        similar_data["content"] = valid_memory_data["content"] + " with slight variation"

        response2 = await client.post("/memory", headers=auth_headers, json=similar_data)

        # Should either succeed (different enough) or return conflict/warning
        assert response2.status_code in [201, 409]  # 409 = Conflict for similar content

    @pytest.mark.asyncio
    async def test_create_memory_embedding_generated(self, client: AsyncClient, auth_headers: dict, valid_memory_data: dict):
        """Test that memory creation generates embeddings."""
        response = await client.post("/memory", headers=auth_headers, json=valid_memory_data)

        assert response.status_code == 201
        data = response.json()

        # Embedding should be generated automatically
        assert "embedding" in data
        assert isinstance(data["embedding"], list)
        assert len(data["embedding"]) > 0

        # Embedding should be valid float values
        for value in data["embedding"]:
            assert isinstance(value, (int, float))

    @pytest.mark.asyncio
    async def test_create_memory_timestamps(self, client: AsyncClient, auth_headers: dict, valid_memory_data: dict):
        """Test that memory creation sets appropriate timestamps."""
        response = await client.post("/memory", headers=auth_headers, json=valid_memory_data)

        assert response.status_code == 201
        data = response.json()

        # All timestamp fields should be present
        timestamp_fields = ["created_at", "updated_at", "last_accessed_at"]
        for field in timestamp_fields:
            assert field in data
            assert data[field] is not None

        # created_at and updated_at should be the same for new memory
        assert data["created_at"] == data["updated_at"]