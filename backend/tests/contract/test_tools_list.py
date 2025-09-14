"""
Contract test for GET /tools endpoint.

This test validates the API contract for listing available tools.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient


class TestToolsListContract:
    """Test contract compliance for tools list endpoint."""

    @pytest.mark.asyncio
    async def test_list_tools_success(self, client: AsyncClient, auth_headers: dict):
        """Test successful tools listing returns 200."""
        # Act
        response = await client.get("/tools", headers=auth_headers)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200
        assert "data" in response.json()
        assert isinstance(response.json()["data"], list)

    @pytest.mark.asyncio
    async def test_list_tools_response_format(self, client: AsyncClient, auth_headers: dict):
        """Test tools listing response has correct format."""
        response = await client.get("/tools", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "data" in data
        assert isinstance(data["data"], list)

        # If tools exist, validate tool structure
        if data["data"]:
            tool = data["data"][0]
            required_fields = [
                "id", "name", "description", "category", "version",
                "enabled", "schema", "created_at", "updated_at"
            ]
            for field in required_fields:
                assert field in tool

            # Validate tool schema structure
            schema = tool["schema"]
            assert "type" in schema
            assert "properties" in schema
            assert isinstance(schema["properties"], dict)

    @pytest.mark.asyncio
    async def test_list_tools_with_category_filter(self, client: AsyncClient, auth_headers: dict):
        """Test tools listing with category filter."""
        params = {"category": "web"}
        response = await client.get("/tools", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All tools should have the filtered category
        for tool in data["data"]:
            assert tool["category"] == "web"

    @pytest.mark.asyncio
    async def test_list_tools_with_enabled_filter(self, client: AsyncClient, auth_headers: dict):
        """Test tools listing with enabled filter."""
        params = {"enabled": "true"}
        response = await client.get("/tools", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # All tools should be enabled
        for tool in data["data"]:
            assert tool["enabled"] is True

    @pytest.mark.asyncio
    async def test_list_tools_categories(self, client: AsyncClient, auth_headers: dict):
        """Test that tools have valid categories."""
        response = await client.get("/tools", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        valid_categories = [
            "web", "file", "code", "data", "ai", "communication",
            "utility", "search", "analysis", "automation"
        ]

        # All tools should have valid categories
        for tool in data["data"]:
            assert tool["category"] in valid_categories

    @pytest.mark.asyncio
    async def test_list_tools_without_auth_unauthorized(self, client: AsyncClient):
        """Test tools listing without authentication returns 401."""
        response = await client.get("/tools")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_tools_invalid_token_unauthorized(self, client: AsyncClient):
        """Test tools listing with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.get("/tools", headers=invalid_headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_tools_schema_validation(self, client: AsyncClient, auth_headers: dict):
        """Test that tool schemas are valid JSON Schema."""
        response = await client.get("/tools", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        for tool in data["data"]:
            schema = tool["schema"]

            # Basic JSON Schema validation
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert isinstance(schema["properties"], dict)

            # Each property should have a type
            for prop_name, prop_schema in schema["properties"].items():
                assert "type" in prop_schema
                assert isinstance(prop_schema["type"], str)

    @pytest.mark.asyncio
    async def test_list_tools_builtin_tools_present(self, client: AsyncClient, auth_headers: dict):
        """Test that common built-in tools are present."""
        response = await client.get("/tools", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Get tool names
        tool_names = [tool["name"] for tool in data["data"]]

        # Common tools that should be available
        expected_tools = ["web_search", "file_read", "code_execute", "memory_search"]

        # At least some basic tools should be present
        assert len([tool for tool in expected_tools if tool in tool_names]) > 0

    @pytest.mark.asyncio
    async def test_list_tools_invalid_category_filter(self, client: AsyncClient, auth_headers: dict):
        """Test tools listing with invalid category filter."""
        params = {"category": "invalid_category"}
        response = await client.get("/tools", headers=auth_headers, params=params)

        # Should return 422 for invalid category or 200 with empty results
        assert response.status_code in [200, 422]

        if response.status_code == 200:
            data = response.json()
            assert data["data"] == []

    @pytest.mark.asyncio
    async def test_list_tools_invalid_enabled_filter(self, client: AsyncClient, auth_headers: dict):
        """Test tools listing with invalid enabled filter."""
        params = {"enabled": "invalid"}
        response = await client.get("/tools", headers=auth_headers, params=params)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_tools_with_search_query(self, client: AsyncClient, auth_headers: dict):
        """Test tools listing with search query."""
        params = {"q": "web"}
        response = await client.get("/tools", headers=auth_headers, params=params)

        assert response.status_code == 200
        data = response.json()

        # Results should be relevant to search query
        for tool in data["data"]:
            # Search should match name, description, or category
            search_text = f"{tool['name']} {tool['description']} {tool['category']}".lower()
            assert "web" in search_text

    @pytest.mark.asyncio
    async def test_list_tools_version_info(self, client: AsyncClient, auth_headers: dict):
        """Test that tools have proper version information."""
        response = await client.get("/tools", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        for tool in data["data"]:
            # Version should be present and follow semantic versioning pattern
            assert "version" in tool
            assert isinstance(tool["version"], str)
            # Basic version format check (e.g., "1.0.0")
            version_parts = tool["version"].split(".")
            assert len(version_parts) >= 2  # At least major.minor