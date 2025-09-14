"""
Contract test for GET /analytics/dashboard endpoint.

This test validates the API contract for retrieving analytics dashboard data.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta


class TestAnalyticsDashboardGetContract:
    """Test contract compliance for analytics dashboard endpoint."""

    @pytest.mark.asyncio
    async def test_dashboard_success_response_format(self, client: AsyncClient, auth_headers: dict):
        """Test successful dashboard retrieval returns correct response format."""
        # Act
        response = await client.get("/analytics/dashboard", headers=auth_headers)

        # Assert - This MUST FAIL initially (endpoint doesn't exist yet)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Validate response structure according to OpenAPI spec
        response_data = response.json()
        required_fields = [
            "total_conversations", "total_messages", "total_tokens",
            "active_users", "conversation_metrics", "usage_metrics",
            "time_range", "last_updated"
        ]
        for field in required_fields:
            assert field in response_data, f"Missing required field: {field}"

        # Validate data types
        assert isinstance(response_data["total_conversations"], int)
        assert isinstance(response_data["total_messages"], int)
        assert isinstance(response_data["total_tokens"], int)
        assert isinstance(response_data["active_users"], int)
        assert isinstance(response_data["conversation_metrics"], dict)
        assert isinstance(response_data["usage_metrics"], dict)
        assert isinstance(response_data["time_range"], dict)
        assert isinstance(response_data["last_updated"], str)

        # Validate conversation_metrics structure
        conv_metrics = response_data["conversation_metrics"]
        conv_required_fields = ["daily", "weekly", "monthly", "average_length", "completion_rate"]
        for field in conv_required_fields:
            assert field in conv_metrics, f"Missing conversation_metrics field: {field}"

        # Validate usage_metrics structure
        usage_metrics = response_data["usage_metrics"]
        usage_required_fields = ["tokens_by_day", "requests_by_hour", "popular_endpoints", "error_rate"]
        for field in usage_required_fields:
            assert field in usage_metrics, f"Missing usage_metrics field: {field}"

    @pytest.mark.asyncio
    async def test_dashboard_time_range_filtering_hour(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard with hourly time range filtering."""
        # Act
        params = {"time_range": "hour"}
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Validate time_range reflects the filter
        assert response_data["time_range"]["type"] == "hour"
        assert "start_time" in response_data["time_range"]
        assert "end_time" in response_data["time_range"]

    @pytest.mark.asyncio
    async def test_dashboard_time_range_filtering_day(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard with daily time range filtering."""
        # Act
        params = {"time_range": "day"}
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["time_range"]["type"] == "day"

    @pytest.mark.asyncio
    async def test_dashboard_time_range_filtering_week(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard with weekly time range filtering."""
        # Act
        params = {"time_range": "week"}
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["time_range"]["type"] == "week"

    @pytest.mark.asyncio
    async def test_dashboard_time_range_filtering_month(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard with monthly time range filtering."""
        # Act
        params = {"time_range": "month"}
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["time_range"]["type"] == "month"

    @pytest.mark.asyncio
    async def test_dashboard_time_range_filtering_quarter(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard with quarterly time range filtering."""
        # Act
        params = {"time_range": "quarter"}
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["time_range"]["type"] == "quarter"

    @pytest.mark.asyncio
    async def test_dashboard_time_range_filtering_year(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard with yearly time range filtering."""
        # Act
        params = {"time_range": "year"}
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["time_range"]["type"] == "year"

    @pytest.mark.asyncio
    async def test_dashboard_invalid_time_range(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard with invalid time range returns validation error."""
        # Act
        params = {"time_range": "invalid"}
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 400
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response

    @pytest.mark.asyncio
    async def test_dashboard_tenant_filtering_admin_only(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard with tenant filtering (admin users only)."""
        # Act - Try with regular user (should work for own tenant)
        response = await client.get("/analytics/dashboard", headers=auth_headers)
        assert response.status_code == 200

        # Act - Try with tenant_id parameter (should require admin role)
        params = {"tenant_id": "other-tenant-id"}
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert - Should fail for non-admin users
        assert response.status_code in [403, 401]  # Forbidden or unauthorized

    @pytest.mark.asyncio
    async def test_dashboard_without_auth_unauthorized(self, client: AsyncClient):
        """Test dashboard retrieval without authentication returns 401."""
        # Act
        response = await client.get("/analytics/dashboard")

        # Assert
        assert response.status_code == 401
        error_response = response.json()
        assert "error" in error_response
        assert error_response["error"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_dashboard_invalid_token_unauthorized(self, client: AsyncClient):
        """Test dashboard retrieval with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.get("/analytics/dashboard", headers=invalid_headers)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_dashboard_response_schema_validation(self, client: AsyncClient, auth_headers: dict):
        """Test that dashboard response follows expected schema."""
        # Act
        response = await client.get("/analytics/dashboard", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Validate numeric fields are non-negative
        assert response_data["total_conversations"] >= 0
        assert response_data["total_messages"] >= 0
        assert response_data["total_tokens"] >= 0
        assert response_data["active_users"] >= 0

        # Validate timestamp format
        from datetime import datetime
        assert datetime.fromisoformat(response_data["last_updated"].replace('Z', '+00:00'))

        # Validate conversation metrics structure
        conv_metrics = response_data["conversation_metrics"]
        assert isinstance(conv_metrics["daily"], list)
        assert isinstance(conv_metrics["weekly"], list)
        assert isinstance(conv_metrics["monthly"], list)
        assert isinstance(conv_metrics["average_length"], (int, float))
        assert isinstance(conv_metrics["completion_rate"], (int, float))
        assert 0 <= conv_metrics["completion_rate"] <= 1

        # Validate usage metrics structure
        usage_metrics = response_data["usage_metrics"]
        assert isinstance(usage_metrics["tokens_by_day"], list)
        assert isinstance(usage_metrics["requests_by_hour"], list)
        assert isinstance(usage_metrics["popular_endpoints"], list)
        assert isinstance(usage_metrics["error_rate"], (int, float))
        assert 0 <= usage_metrics["error_rate"] <= 1

    @pytest.mark.asyncio
    async def test_dashboard_custom_date_range(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard with custom date range parameters."""
        # Arrange
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }

        # Act
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Validate custom date range is reflected
        time_range = response_data["time_range"]
        assert "custom" in time_range["type"] or time_range["type"] == "custom"

    @pytest.mark.asyncio
    async def test_dashboard_invalid_date_range(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard with invalid date range returns validation error."""
        # Arrange - End date before start date
        start_date = datetime.now()
        end_date = start_date - timedelta(days=1)

        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }

        # Act
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_dashboard_response_headers(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard response includes correct headers."""
        # Act
        response = await client.get("/analytics/dashboard", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_dashboard_data_freshness(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard includes data freshness indicators."""
        # Act
        response = await client.get("/analytics/dashboard", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Check that last_updated is recent (within last hour for fresh data)
        last_updated = datetime.fromisoformat(response_data["last_updated"].replace('Z', '+00:00'))
        now = datetime.now(last_updated.tzinfo)
        time_diff = now - last_updated

        # Data should be reasonably fresh
        assert time_diff.total_seconds() < 3600  # Less than 1 hour old

    @pytest.mark.asyncio
    async def test_dashboard_empty_data_handling(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard handles empty data gracefully."""
        # Act - For new users with no data
        response = await client.get("/analytics/dashboard", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Should return zero values for empty data, not errors
        assert response_data["total_conversations"] == 0
        assert response_data["total_messages"] == 0
        assert response_data["total_tokens"] == 0
        assert len(response_data["conversation_metrics"]["daily"]) >= 0
        assert len(response_data["usage_metrics"]["tokens_by_day"]) >= 0

    @pytest.mark.asyncio
    async def test_dashboard_pagination_support(self, client: AsyncClient, auth_headers: dict):
        """Test dashboard supports pagination for large datasets."""
        # Act
        params = {"limit": 10, "offset": 0}
        response = await client.get("/analytics/dashboard", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Check that pagination affects array fields
        if "conversation_metrics" in response_data:
            daily_data = response_data["conversation_metrics"]["daily"]
            if daily_data:
                assert len(daily_data) <= 10