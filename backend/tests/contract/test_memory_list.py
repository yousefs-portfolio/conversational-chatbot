"""
Contract test for GET /memory endpoint.

This test validates the API contract for listing user memories.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient


class TestMemoryListContract:
    """Test contract compliance for memory list endpoint."""

    @pytest.mark.asyncio
    async def test_list_memories_success(self, client: AsyncClient, auth_headers: dict):
        """Test successful memory listing returns 200."""
        # Act
        response = await client.get("/memory", headers=auth_headers)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200
        assert "data" in response.json()
        assert isinstance(response.json()["data"], list)

    @pytest.mark.asyncio
    async def test_list_memories_with_pagination(self, client: AsyncClient, auth_headers: dict):
        """Test memory listing with pagination parameters."""
        params = {"page": 1, "limit": 20}
        response = await client.get("/memory", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert "total" in data["pagination"]
        assert "page" in data["pagination"]
        assert "limit" in data["pagination"]

    @pytest.mark.asyncio
    async def test_list_memories_empty_result(self, client: AsyncClient, auth_headers: dict):
        """Test memory listing returns empty array when no memories."""
        response = await client.get("/memory", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_list_memories_response_format(self, client: AsyncClient, auth_headers: dict):
        """Test memory listing response has correct format."""
        response = await client.get("/memory", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

        # If memories exist, validate memory structure
        if data["data"]:
            memory = data["data"][0]
            required_fields = [
                "id", "content", "type", "importance", "created_at",
                "updated_at", "last_accessed_at", "embedding"
            ]
            for field in required_fields:
                assert field in memory

            # Validate memory type
            assert memory["type"] in ["fact", "preference", "context", "relationship", "skill"]

            # Validate importance range
            assert 0.0 <= memory["importance"] <= 1.0

    @pytest.mark.asyncio
    async def test_list_memories_without_auth_unauthorized(self, client: AsyncClient):
        """Test memory listing without authentication returns 401."""
        response = await client.get("/memory")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_memories_invalid_token_unauthorized(self, client: AsyncClient):
        """Test memory listing with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.get("/memory", headers=invalid_headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_memories_with_type_filter(self, client: AsyncClient, auth_headers: dict):
        """Test memory listing with type filter."""
        params = {"type": "fact"}
        response = await client.get("/memory", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All memories should have the filtered type
        for memory in data["data"]:
            assert memory["type"] == "fact"

    @pytest.mark.asyncio
    async def test_list_memories_with_importance_filter(self, client: AsyncClient, auth_headers: dict):
        """Test memory listing with importance threshold filter."""
        params = {"min_importance": 0.7}
        response = await client.get("/memory", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All memories should meet importance threshold
        for memory in data["data"]:
            assert memory["importance"] >= 0.7

    @pytest.mark.asyncio
    async def test_list_memories_search_query(self, client: AsyncClient, auth_headers: dict):
        """Test memory listing with search query."""
        params = {"query": "python programming"}
        response = await client.get("/memory", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # Response should include similarity scores when searching
        if data["data"]:
            memory = data["data"][0]
            assert "similarity_score" in memory
            assert 0.0 <= memory["similarity_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_list_memories_invalid_pagination(self, client: AsyncClient, auth_headers: dict):
        """Test memory listing with invalid pagination parameters."""
        # Test negative page
        response = await client.get("/memory", headers=auth_headers, params={"page": -1})
        assert response.status_code == 422

        # Test page 0
        response = await client.get("/memory", headers=auth_headers, params={"page": 0})
        assert response.status_code == 422

        # Test invalid limit
        response = await client.get("/memory", headers=auth_headers, params={"limit": 0})
        assert response.status_code == 422

        # Test limit too high
        response = await client.get("/memory", headers=auth_headers, params={"limit": 1000})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_memories_invalid_type_filter(self, client: AsyncClient, auth_headers: dict):
        """Test memory listing with invalid type filter."""
        params = {"type": "invalid_type"}
        response = await client.get("/memory", headers=auth_headers, params=params)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_memories_invalid_importance_filter(self, client: AsyncClient, auth_headers: dict):
        """Test memory listing with invalid importance filter."""
        # Test importance > 1.0
        response = await client.get("/memory", headers=auth_headers, params={"min_importance": 1.5})
        assert response.status_code == 422

        # Test negative importance
        response = await client.get("/memory", headers=auth_headers, params={"min_importance": -0.5})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_memories_ordering(self, client: AsyncClient, auth_headers: dict):
        """Test memory listing with different ordering options."""
        # Test order by importance
        params = {"order_by": "importance", "order": "desc"}
        response = await client.get("/memory", headers=auth_headers, params=params)
        assert response.status_code == 200

        # Test order by creation date
        params = {"order_by": "created_at", "order": "asc"}
        response = await client.get("/memory", headers=auth_headers, params=params)
        assert response.status_code == 200

        # Test order by last accessed
        params = {"order_by": "last_accessed_at", "order": "desc"}
        response = await client.get("/memory", headers=auth_headers, params=params)
        assert response.status_code == 200