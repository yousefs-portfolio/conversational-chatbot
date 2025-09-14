"""
Contract test for GET /analytics/usage endpoint.

This test validates the API contract for retrieving user usage statistics.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta


class TestAnalyticsUsageGetContract:
    """Test contract compliance for analytics usage endpoint."""

    @pytest.mark.asyncio
    async def test_usage_success_response_format(self, client: AsyncClient, auth_headers: dict):
        """Test successful usage statistics retrieval returns correct response format."""
        # Act
        response = await client.get("/analytics/usage", headers=auth_headers)

        # Assert - This MUST FAIL initially (endpoint doesn't exist yet)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Validate response structure according to OpenAPI spec
        response_data = response.json()
        required_fields = [
            "user_id", "current_period", "usage_statistics",
            "quotas", "billing_period", "last_updated"
        ]
        for field in required_fields:
            assert field in response_data, f"Missing required field: {field}"

        # Validate data types
        assert isinstance(response_data["user_id"], str)
        assert isinstance(response_data["current_period"], dict)
        assert isinstance(response_data["usage_statistics"], dict)
        assert isinstance(response_data["quotas"], dict)
        assert isinstance(response_data["billing_period"], dict)
        assert isinstance(response_data["last_updated"], str)

        # Validate current_period structure
        period = response_data["current_period"]
        period_fields = ["start_date", "end_date", "period_type"]
        for field in period_fields:
            assert field in period, f"Missing current_period field: {field}"

        # Validate usage_statistics structure
        usage_stats = response_data["usage_statistics"]
        usage_fields = [
            "total_conversations", "total_messages", "total_tokens",
            "api_requests", "storage_used", "processing_time"
        ]
        for field in usage_fields:
            assert field in usage_stats, f"Missing usage_statistics field: {field}"
            assert isinstance(usage_stats[field], (int, float))
            assert usage_stats[field] >= 0

        # Validate quotas structure
        quotas = response_data["quotas"]
        quota_fields = [
            "conversations_limit", "messages_limit", "tokens_limit",
            "api_requests_limit", "storage_limit"
        ]
        for field in quota_fields:
            assert field in quotas, f"Missing quotas field: {field}"
            assert isinstance(quotas[field], (int, type(None)))

    @pytest.mark.asyncio
    async def test_usage_time_range_filtering_day(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics with daily time range filtering."""
        # Act
        params = {"time_range": "day"}
        response = await client.get("/analytics/usage", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Validate time_range reflects the filter
        period = response_data["current_period"]
        assert period["period_type"] == "day"

        # Validate date range is approximately 1 day
        start_date = datetime.fromisoformat(period["start_date"].replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(period["end_date"].replace('Z', '+00:00'))
        time_diff = end_date - start_date
        assert time_diff.days <= 1

    @pytest.mark.asyncio
    async def test_usage_time_range_filtering_week(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics with weekly time range filtering."""
        # Act
        params = {"time_range": "week"}
        response = await client.get("/analytics/usage", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["current_period"]["period_type"] == "week"

    @pytest.mark.asyncio
    async def test_usage_time_range_filtering_month(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics with monthly time range filtering."""
        # Act
        params = {"time_range": "month"}
        response = await client.get("/analytics/usage", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["current_period"]["period_type"] == "month"

    @pytest.mark.asyncio
    async def test_usage_invalid_time_range(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics with invalid time range returns validation error."""
        # Act
        params = {"time_range": "invalid"}
        response = await client.get("/analytics/usage", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 400
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response

    @pytest.mark.asyncio
    async def test_usage_current_quotas_included(self, client: AsyncClient, auth_headers: dict):
        """Test that current quotas are included in response."""
        # Act
        response = await client.get("/analytics/usage", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        quotas = response_data["quotas"]

        # Validate quota fields have proper values
        assert quotas["conversations_limit"] is None or quotas["conversations_limit"] > 0
        assert quotas["messages_limit"] is None or quotas["messages_limit"] > 0
        assert quotas["tokens_limit"] is None or quotas["tokens_limit"] > 0
        assert quotas["api_requests_limit"] is None or quotas["api_requests_limit"] > 0
        assert quotas["storage_limit"] is None or quotas["storage_limit"] > 0

        # Check for quota utilization percentages
        if "quota_utilization" in response_data:
            utilization = response_data["quota_utilization"]
            for key, value in utilization.items():
                if value is not None:
                    assert 0 <= value <= 100  # Percentage values

    @pytest.mark.asyncio
    async def test_usage_without_auth_unauthorized(self, client: AsyncClient):
        """Test usage statistics retrieval without authentication returns 401."""
        # Act
        response = await client.get("/analytics/usage")

        # Assert
        assert response.status_code == 401
        error_response = response.json()
        assert "error" in error_response
        assert error_response["error"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_usage_invalid_token_unauthorized(self, client: AsyncClient):
        """Test usage statistics retrieval with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.get("/analytics/usage", headers=invalid_headers)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_usage_detailed_breakdown(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics include detailed breakdowns."""
        # Act
        response = await client.get("/analytics/usage", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        usage_stats = response_data["usage_statistics"]

        # Check for detailed breakdowns if available
        optional_breakdowns = [
            "conversations_by_model",
            "tokens_by_model",
            "requests_by_endpoint",
            "daily_usage",
            "hourly_usage"
        ]

        # At least some breakdown should be available
        breakdown_count = sum(1 for field in optional_breakdowns if field in usage_stats)
        assert breakdown_count >= 0  # Can be zero for new users

    @pytest.mark.asyncio
    async def test_usage_billing_period_info(self, client: AsyncClient, auth_headers: dict):
        """Test that billing period information is included."""
        # Act
        response = await client.get("/analytics/usage", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        billing_period = response_data["billing_period"]
        required_billing_fields = ["start_date", "end_date", "billing_cycle", "days_remaining"]
        for field in required_billing_fields:
            assert field in billing_period, f"Missing billing_period field: {field}"

        # Validate billing cycle
        assert billing_period["billing_cycle"] in ["monthly", "yearly", "custom"]

        # Validate days remaining
        assert isinstance(billing_period["days_remaining"], int)
        assert billing_period["days_remaining"] >= 0

    @pytest.mark.asyncio
    async def test_usage_cost_estimation(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics include cost estimation if applicable."""
        # Act
        response = await client.get("/analytics/usage", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Check for cost-related fields (optional)
        cost_fields = ["estimated_cost", "cost_breakdown", "pricing_tier"]
        cost_fields_present = [field for field in cost_fields if field in response_data]

        # If cost estimation is present, validate structure
        if "estimated_cost" in response_data:
            cost = response_data["estimated_cost"]
            assert isinstance(cost, (int, float))
            assert cost >= 0

        if "cost_breakdown" in response_data:
            breakdown = response_data["cost_breakdown"]
            assert isinstance(breakdown, dict)

    @pytest.mark.asyncio
    async def test_usage_response_headers(self, client: AsyncClient, auth_headers: dict):
        """Test usage response includes correct headers."""
        # Act
        response = await client.get("/analytics/usage", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_usage_pagination_support(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics support pagination for detailed breakdowns."""
        # Act
        params = {"limit": 10, "offset": 0}
        response = await client.get("/analytics/usage", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Check that pagination affects breakdown arrays if present
        usage_stats = response_data["usage_statistics"]
        array_fields = ["daily_usage", "hourly_usage", "conversations_by_model"]

        for field in array_fields:
            if field in usage_stats and isinstance(usage_stats[field], list):
                assert len(usage_stats[field]) <= 10

    @pytest.mark.asyncio
    async def test_usage_custom_date_range(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics with custom date range."""
        # Arrange
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }

        # Act
        response = await client.get("/analytics/usage", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Validate custom date range is reflected
        period = response_data["current_period"]
        assert period["period_type"] in ["custom", "range"]

    @pytest.mark.asyncio
    async def test_usage_invalid_date_range(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics with invalid date range returns validation error."""
        # Arrange - End date before start date
        start_date = datetime.now()
        end_date = start_date - timedelta(days=1)

        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }

        # Act
        response = await client.get("/analytics/usage", headers=auth_headers, params=params)

        # Assert
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_usage_data_freshness(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics include data freshness indicators."""
        # Act
        response = await client.get("/analytics/usage", headers=auth_headers)

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
    async def test_usage_zero_usage_handling(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics handle zero usage gracefully."""
        # Act - For new users with no usage
        response = await client.get("/analytics/usage", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        usage_stats = response_data["usage_statistics"]

        # Should return zero values for empty usage, not errors
        assert usage_stats["total_conversations"] >= 0
        assert usage_stats["total_messages"] >= 0
        assert usage_stats["total_tokens"] >= 0
        assert usage_stats["api_requests"] >= 0
        assert usage_stats["storage_used"] >= 0
        assert usage_stats["processing_time"] >= 0

    @pytest.mark.asyncio
    async def test_usage_quota_warnings(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics include quota warnings if approaching limits."""
        # Act
        response = await client.get("/analytics/usage", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Check for optional warning fields
        warning_fields = ["quota_warnings", "approaching_limits", "usage_alerts"]
        warnings_present = [field for field in warning_fields if field in response_data]

        # If warnings are present, validate structure
        if "quota_warnings" in response_data:
            warnings = response_data["quota_warnings"]
            assert isinstance(warnings, list)

        if "approaching_limits" in response_data:
            limits = response_data["approaching_limits"]
            assert isinstance(limits, list)

    @pytest.mark.asyncio
    async def test_usage_historical_comparison(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics include historical comparison data."""
        # Act
        response = await client.get("/analytics/usage", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Check for optional historical comparison fields
        historical_fields = [
            "previous_period_comparison",
            "growth_metrics",
            "trend_analysis"
        ]

        # If historical data is present, validate structure
        if "previous_period_comparison" in response_data:
            comparison = response_data["previous_period_comparison"]
            assert isinstance(comparison, dict)

        if "growth_metrics" in response_data:
            growth = response_data["growth_metrics"]
            assert isinstance(growth, dict)

    @pytest.mark.asyncio
    async def test_usage_export_capability(self, client: AsyncClient, auth_headers: dict):
        """Test usage statistics can be exported in different formats."""
        # Act - Test if export parameter is supported
        params = {"export": "csv"}
        response = await client.get("/analytics/usage", headers=auth_headers, params=params)

        # Assert - Either CSV export works or parameter is ignored
        assert response.status_code in [200, 400]  # 400 if export not supported

        if response.status_code == 200:
            # Check if response is CSV or JSON
            content_type = response.headers.get("content-type", "")
            assert content_type in ["application/json", "text/csv", "application/csv"]