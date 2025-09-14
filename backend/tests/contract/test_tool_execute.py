"""
Contract test for POST /tools/{id}/execute endpoint.

This test validates the API contract for executing tools.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
import uuid


class TestToolExecuteContract:
    """Test contract compliance for tool execution endpoint."""

    @pytest.fixture
    def sample_tool_id(self):
        """Sample tool ID for testing."""
        return "web_search"

    @pytest.fixture
    def valid_execution_data(self):
        """Valid tool execution data."""
        return {
            "parameters": {
                "query": "Python programming best practices",
                "max_results": 5
            },
            "context": {
                "conversation_id": str(uuid.uuid4()),
                "message_id": str(uuid.uuid4())
            }
        }

    @pytest.fixture
    def minimal_execution_data(self):
        """Minimal valid execution data."""
        return {
            "parameters": {
                "query": "test query"
            }
        }

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, client: AsyncClient, auth_headers: dict,
                                       sample_tool_id: str, valid_execution_data: dict):
        """Test successful tool execution returns 200."""
        # Act
        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=auth_headers,
            json=valid_execution_data
        )

        # Assert - This MUST FAIL initially
        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert "status" in data
        assert "result" in data

    @pytest.mark.asyncio
    async def test_execute_tool_async_response(self, client: AsyncClient, auth_headers: dict,
                                              sample_tool_id: str, valid_execution_data: dict):
        """Test tool execution returns proper async response format."""
        # Add async flag
        execution_data = valid_execution_data.copy()
        execution_data["async"] = True

        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=auth_headers,
            json=execution_data
        )

        assert response.status_code == 202  # Accepted for async execution
        data = response.json()
        assert "execution_id" in data
        assert "status" in data
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_execute_tool_response_format(self, client: AsyncClient, auth_headers: dict,
                                               sample_tool_id: str, valid_execution_data: dict):
        """Test tool execution response has correct format."""
        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=auth_headers,
            json=valid_execution_data
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        required_fields = [
            "execution_id", "status", "result", "started_at",
            "completed_at", "tool_id", "parameters_used"
        ]
        for field in required_fields:
            assert field in data

        # Validate status values
        assert data["status"] in ["completed", "running", "failed", "pending"]

        # Validate execution_id format (UUID)
        assert isinstance(data["execution_id"], str)
        uuid.UUID(data["execution_id"])  # Should not raise exception

    @pytest.mark.asyncio
    async def test_execute_tool_with_minimal_data(self, client: AsyncClient, auth_headers: dict,
                                                 sample_tool_id: str, minimal_execution_data: dict):
        """Test tool execution with minimal required data."""
        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=auth_headers,
            json=minimal_execution_data
        )

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert "result" in data

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, client: AsyncClient, auth_headers: dict,
                                         valid_execution_data: dict):
        """Test tool execution with non-existent tool returns 404."""
        non_existent_tool = "non_existent_tool"
        response = await client.post(
            f"/tools/{non_existent_tool}/execute",
            headers=auth_headers,
            json=valid_execution_data
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_tool_without_auth_unauthorized(self, client: AsyncClient,
                                                         sample_tool_id: str, valid_execution_data: dict):
        """Test tool execution without authentication returns 401."""
        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            json=valid_execution_data
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_execute_tool_invalid_token_unauthorized(self, client: AsyncClient,
                                                          sample_tool_id: str, valid_execution_data: dict):
        """Test tool execution with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=invalid_headers,
            json=valid_execution_data
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_execute_tool_invalid_parameters(self, client: AsyncClient, auth_headers: dict,
                                                  sample_tool_id: str):
        """Test tool execution with invalid parameters."""
        # Test missing required parameters
        invalid_data = {"parameters": {}}
        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=auth_headers,
            json=invalid_data
        )
        assert response.status_code == 422

        # Test invalid parameter types
        invalid_data = {
            "parameters": {
                "query": 123,  # Should be string
                "max_results": "invalid"  # Should be integer
            }
        }
        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=auth_headers,
            json=invalid_data
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_execute_tool_missing_parameters(self, client: AsyncClient, auth_headers: dict,
                                                  sample_tool_id: str):
        """Test tool execution with missing parameters object."""
        invalid_data = {}  # Missing parameters
        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=auth_headers,
            json=invalid_data
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_execute_tool_disabled(self, client: AsyncClient, auth_headers: dict,
                                        valid_execution_data: dict):
        """Test execution of disabled tool returns 403."""
        disabled_tool = "disabled_tool"
        response = await client.post(
            f"/tools/{disabled_tool}/execute",
            headers=auth_headers,
            json=valid_execution_data
        )
        # Could be 403 (forbidden) or 404 (not found) if disabled tools are hidden
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_execute_tool_with_context(self, client: AsyncClient, auth_headers: dict,
                                            sample_tool_id: str, valid_execution_data: dict):
        """Test tool execution with context information."""
        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=auth_headers,
            json=valid_execution_data
        )

        assert response.status_code == 200
        data = response.json()

        # Context should be preserved in response
        if "context" in valid_execution_data:
            assert "context" in data
            assert data["context"] == valid_execution_data["context"]

    @pytest.mark.asyncio
    async def test_execute_tool_error_handling(self, client: AsyncClient, auth_headers: dict,
                                              sample_tool_id: str):
        """Test tool execution error handling."""
        # Use parameters that should cause an error
        error_data = {
            "parameters": {
                "query": "",  # Empty query should cause error
                "max_results": -1  # Negative results should cause error
            }
        }

        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=auth_headers,
            json=error_data
        )

        # Should either return 422 for validation error or 200 with error status
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "failed"
            assert "error" in data
        else:
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_execute_tool_timeout_handling(self, client: AsyncClient, auth_headers: dict,
                                                 sample_tool_id: str, valid_execution_data: dict):
        """Test tool execution with timeout parameter."""
        execution_data = valid_execution_data.copy()
        execution_data["timeout"] = 30  # 30 second timeout

        response = await client.post(
            f"/tools/{sample_tool_id}/execute",
            headers=auth_headers,
            json=execution_data
        )

        assert response.status_code in [200, 202]  # Success or accepted

    @pytest.mark.asyncio
    async def test_execute_tool_multiple_tools(self, client: AsyncClient, auth_headers: dict):
        """Test execution of different tool types."""
        tools_to_test = [
            ("web_search", {"query": "test"}),
            ("file_read", {"path": "/tmp/test.txt"}),
            ("code_execute", {"code": "print('hello')", "language": "python"})
        ]

        for tool_id, params in tools_to_test:
            execution_data = {"parameters": params}
            response = await client.post(
                f"/tools/{tool_id}/execute",
                headers=auth_headers,
                json=execution_data
            )

            # Tools might not exist yet (TDD), but structure should be consistent
            if response.status_code not in [404, 422]:  # Skip if tool doesn't exist
                assert response.status_code in [200, 202]