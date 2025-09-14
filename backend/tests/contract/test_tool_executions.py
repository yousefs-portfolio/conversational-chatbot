"""
Contract test for GET /tools/{id}/executions endpoint.

This test validates the API contract for retrieving tool execution history.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
import uuid


class TestToolExecutionsContract:
    """Test contract compliance for tool executions history endpoint."""

    @pytest.fixture
    def sample_tool_id(self):
        """Sample tool ID for testing."""
        return "web_search"

    @pytest.fixture
    def sample_execution_id(self):
        """Sample execution ID for testing."""
        return str(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_list_tool_executions_success(self, client: AsyncClient, auth_headers: dict,
                                               sample_tool_id: str):
        """Test successful tool executions listing returns 200."""
        # Act
        response = await client.get(f"/tools/{sample_tool_id}/executions", headers=auth_headers)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200
        assert "data" in response.json()
        assert isinstance(response.json()["data"], list)

    @pytest.mark.asyncio
    async def test_list_tool_executions_with_pagination(self, client: AsyncClient, auth_headers: dict,
                                                       sample_tool_id: str):
        """Test tool executions listing with pagination parameters."""
        params = {"page": 1, "limit": 10}
        response = await client.get(
            f"/tools/{sample_tool_id}/executions",
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
    async def test_list_tool_executions_response_format(self, client: AsyncClient, auth_headers: dict,
                                                       sample_tool_id: str):
        """Test tool executions listing response has correct format."""
        response = await client.get(f"/tools/{sample_tool_id}/executions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

        # If executions exist, validate execution structure
        if data["data"]:
            execution = data["data"][0]
            required_fields = [
                "id", "tool_id", "status", "parameters", "result",
                "started_at", "completed_at", "error", "user_id"
            ]
            for field in required_fields:
                assert field in execution

            # Validate status values
            assert execution["status"] in ["pending", "running", "completed", "failed"]

            # Validate execution ID format (UUID)
            uuid.UUID(execution["id"])  # Should not raise exception

    @pytest.mark.asyncio
    async def test_list_tool_executions_empty_result(self, client: AsyncClient, auth_headers: dict,
                                                    sample_tool_id: str):
        """Test tool executions listing returns empty array when no executions."""
        response = await client.get(f"/tools/{sample_tool_id}/executions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_list_tool_executions_tool_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test tool executions listing for non-existent tool returns 404."""
        non_existent_tool = "non_existent_tool"
        response = await client.get(f"/tools/{non_existent_tool}/executions", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_tool_executions_without_auth_unauthorized(self, client: AsyncClient,
                                                                 sample_tool_id: str):
        """Test tool executions listing without authentication returns 401."""
        response = await client.get(f"/tools/{sample_tool_id}/executions")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_tool_executions_invalid_token_unauthorized(self, client: AsyncClient,
                                                                  sample_tool_id: str):
        """Test tool executions listing with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.get(f"/tools/{sample_tool_id}/executions", headers=invalid_headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_tool_executions_with_status_filter(self, client: AsyncClient, auth_headers: dict,
                                                          sample_tool_id: str):
        """Test tool executions listing with status filter."""
        params = {"status": "completed"}
        response = await client.get(
            f"/tools/{sample_tool_id}/executions",
            headers=auth_headers,
            params=params
        )

        assert response.status_code == 200
        data = response.json()

        # All executions should have the filtered status
        for execution in data["data"]:
            assert execution["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_tool_executions_with_date_range(self, client: AsyncClient, auth_headers: dict,
                                                       sample_tool_id: str):
        """Test tool executions listing with date range filter."""
        params = {
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-12-31T23:59:59Z"
        }
        response = await client.get(
            f"/tools/{sample_tool_id}/executions",
            headers=auth_headers,
            params=params
        )

        assert response.status_code == 200
        data = response.json()

        # All executions should be within date range
        for execution in data["data"]:
            assert params["start_date"] <= execution["started_at"] <= params["end_date"]

    @pytest.mark.asyncio
    async def test_list_tool_executions_chronological_order(self, client: AsyncClient, auth_headers: dict,
                                                           sample_tool_id: str):
        """Test tool executions listing returns results in chronological order."""
        response = await client.get(f"/tools/{sample_tool_id}/executions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # If multiple executions exist, check they're in chronological order (newest first)
        if len(data["data"]) > 1:
            executions = data["data"]
            for i in range(1, len(executions)):
                # started_at should be in descending order (newest first)
                assert executions[i-1]["started_at"] >= executions[i]["started_at"]

    @pytest.mark.asyncio
    async def test_get_specific_tool_execution(self, client: AsyncClient, auth_headers: dict,
                                              sample_tool_id: str, sample_execution_id: str):
        """Test retrieving a specific tool execution."""
        response = await client.get(
            f"/tools/{sample_tool_id}/executions/{sample_execution_id}",
            headers=auth_headers
        )

        # Should return 200 if exists, 404 if not found
        if response.status_code == 200:
            data = response.json()
            assert data["id"] == sample_execution_id
            assert data["tool_id"] == sample_tool_id
        else:
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_tool_executions_invalid_pagination(self, client: AsyncClient, auth_headers: dict,
                                                          sample_tool_id: str):
        """Test tool executions listing with invalid pagination parameters."""
        # Test negative page
        response = await client.get(
            f"/tools/{sample_tool_id}/executions",
            headers=auth_headers,
            params={"page": -1}
        )
        assert response.status_code == 422

        # Test page 0
        response = await client.get(
            f"/tools/{sample_tool_id}/executions",
            headers=auth_headers,
            params={"page": 0}
        )
        assert response.status_code == 422

        # Test invalid limit
        response = await client.get(
            f"/tools/{sample_tool_id}/executions",
            headers=auth_headers,
            params={"limit": 0}
        )
        assert response.status_code == 422

        # Test limit too high
        response = await client.get(
            f"/tools/{sample_tool_id}/executions",
            headers=auth_headers,
            params={"limit": 1000}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_tool_executions_invalid_status_filter(self, client: AsyncClient, auth_headers: dict,
                                                             sample_tool_id: str):
        """Test tool executions listing with invalid status filter."""
        params = {"status": "invalid_status"}
        response = await client.get(
            f"/tools/{sample_tool_id}/executions",
            headers=auth_headers,
            params=params
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_tool_executions_invalid_date_format(self, client: AsyncClient, auth_headers: dict,
                                                           sample_tool_id: str):
        """Test tool executions listing with invalid date format."""
        params = {"start_date": "invalid-date"}
        response = await client.get(
            f"/tools/{sample_tool_id}/executions",
            headers=auth_headers,
            params=params
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_tool_executions_includes_error_info(self, client: AsyncClient, auth_headers: dict,
                                                           sample_tool_id: str):
        """Test that failed executions include error information."""
        params = {"status": "failed"}
        response = await client.get(
            f"/tools/{sample_tool_id}/executions",
            headers=auth_headers,
            params=params
        )

        assert response.status_code == 200
        data = response.json()

        # Failed executions should have error information
        for execution in data["data"]:
            if execution["status"] == "failed":
                assert "error" in execution
                assert execution["error"] is not None

    @pytest.mark.asyncio
    async def test_list_tool_executions_user_isolation(self, client: AsyncClient, auth_headers: dict,
                                                      sample_tool_id: str):
        """Test that users only see their own tool executions."""
        response = await client.get(f"/tools/{sample_tool_id}/executions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # All executions should belong to the authenticated user
        # Note: This test assumes the auth_headers fixture represents a specific user
        for execution in data["data"]:
            assert "user_id" in execution
            # The actual user_id check would depend on how auth is implemented