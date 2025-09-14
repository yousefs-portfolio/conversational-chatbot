"""
Contract test for POST /tenants endpoint.

This test validates the API contract for creating new tenants.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from tests.conftest import assert_valid_uuid, assert_datetime_format


class TestTenantsPostContract:
    """Test contract compliance for tenant creation endpoint."""

    @pytest.fixture
    def valid_tenant_data(self):
        """Valid tenant creation data."""
        return {
            "name": "Test Organization",
            "domain": "test-org.example.com",
            "plan": "business",
            "settings": {
                "max_users": 100,
                "features": ["analytics", "custom_branding", "sso"]
            }
        }

    @pytest.fixture
    def minimal_tenant_data(self):
        """Minimal valid tenant data."""
        return {
            "name": "Minimal Tenant",
            "domain": "minimal.example.com"
        }

    @pytest.mark.asyncio
    async def test_create_tenant_success(self, client: AsyncClient, auth_headers: dict, valid_tenant_data: dict):
        """Test successful tenant creation returns 201."""
        # Act
        response = await client.post("/tenants", headers=auth_headers, json=valid_tenant_data)

        # Assert - This MUST FAIL initially
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        data = response.json()

        # Validate response structure
        required_fields = [
            "id", "name", "domain", "plan", "settings",
            "is_active", "created_at", "updated_at", "owner_id"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Validate data values
        assert data["name"] == valid_tenant_data["name"]
        assert data["domain"] == valid_tenant_data["domain"]
        assert data["plan"] == valid_tenant_data["plan"]
        assert data["settings"] == valid_tenant_data["settings"]
        assert data["is_active"] is True

        # Validate data types
        assert isinstance(data["id"], str)
        assert isinstance(data["name"], str)
        assert isinstance(data["domain"], str)
        assert isinstance(data["plan"], str)
        assert isinstance(data["settings"], dict)
        assert isinstance(data["is_active"], bool)
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)
        assert isinstance(data["owner_id"], str)

        # Validate UUID and datetime formats
        assert_valid_uuid(data["id"])
        assert_valid_uuid(data["owner_id"])
        assert_datetime_format(data["created_at"])
        assert_datetime_format(data["updated_at"])

    @pytest.mark.asyncio
    async def test_create_tenant_minimal_data(self, client: AsyncClient, auth_headers: dict, minimal_tenant_data: dict):
        """Test tenant creation with minimal required data."""
        # Act
        response = await client.post("/tenants", headers=auth_headers, json=minimal_tenant_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == minimal_tenant_data["name"]
        assert data["domain"] == minimal_tenant_data["domain"]
        assert data["plan"] == "free"  # Default plan
        assert data["settings"] == {}  # Default empty settings
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_tenant_without_auth_unauthorized(self, client: AsyncClient, valid_tenant_data: dict):
        """Test tenant creation without authentication returns 401."""
        # Act
        response = await client.post("/tenants", json=valid_tenant_data)

        # Assert
        assert response.status_code == 401
        error_data = response.json()
        assert "error" in error_data
        assert "message" in error_data

    @pytest.mark.asyncio
    async def test_create_tenant_invalid_token_unauthorized(self, client: AsyncClient, valid_tenant_data: dict):
        """Test tenant creation with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.post("/tenants", headers=invalid_headers, json=valid_tenant_data)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_tenant_validation_errors(self, client: AsyncClient, auth_headers: dict):
        """Test validation error responses for invalid tenant data."""
        validation_test_cases = [
            # Missing required fields
            {
                "data": {"domain": "test.example.com"},
                "description": "missing name"
            },
            {
                "data": {"name": "Test Tenant"},
                "description": "missing domain"
            },
            {
                "data": {},
                "description": "missing all required fields"
            },
            # Invalid data types
            {
                "data": {"name": 123, "domain": "test.example.com"},
                "description": "invalid name type"
            },
            {
                "data": {"name": "Test", "domain": 123},
                "description": "invalid domain type"
            },
            {
                "data": {"name": "Test", "domain": "test.com", "plan": 123},
                "description": "invalid plan type"
            },
            {
                "data": {"name": "Test", "domain": "test.com", "settings": "invalid"},
                "description": "invalid settings type"
            },
            # Invalid field values
            {
                "data": {"name": "", "domain": "test.example.com"},
                "description": "empty name"
            },
            {
                "data": {"name": "Test", "domain": ""},
                "description": "empty domain"
            },
            {
                "data": {"name": "A" * 101, "domain": "test.example.com"},
                "description": "name too long"
            },
            {
                "data": {"name": "Test", "domain": "invalid-domain"},
                "description": "invalid domain format"
            },
            {
                "data": {"name": "Test", "domain": "test.com", "plan": "invalid-plan"},
                "description": "invalid plan value"
            }
        ]

        for test_case in validation_test_cases:
            # Act
            response = await client.post("/tenants", headers=auth_headers, json=test_case["data"])

            # Assert
            assert response.status_code == 422, f"Expected 422 for {test_case['description']}, got {response.status_code}"

            # Validate error response structure
            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response

    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_domain_conflict(self, client: AsyncClient, auth_headers: dict):
        """Test duplicate domain returns 409 conflict."""
        # Arrange
        tenant_data = {
            "name": "First Tenant",
            "domain": "duplicate.example.com"
        }

        # Act - Create first tenant
        first_response = await client.post("/tenants", headers=auth_headers, json=tenant_data)
        assert first_response.status_code == 201

        # Act - Try to create tenant with same domain
        duplicate_data = {
            "name": "Second Tenant",
            "domain": "duplicate.example.com"
        }
        second_response = await client.post("/tenants", headers=auth_headers, json=duplicate_data)

        # Assert
        assert second_response.status_code == 409
        error_response = second_response.json()
        assert "error" in error_response
        assert "message" in error_response
        assert error_response["error"] == "conflict"

    @pytest.mark.asyncio
    async def test_create_tenant_with_custom_settings(self, client: AsyncClient, auth_headers: dict):
        """Test tenant creation with custom settings."""
        # Arrange
        tenant_data = {
            "name": "Custom Settings Tenant",
            "domain": "custom.example.com",
            "plan": "enterprise",
            "settings": {
                "max_users": 500,
                "features": ["analytics", "custom_branding", "sso", "api_access"],
                "branding": {
                    "logo_url": "https://example.com/logo.png",
                    "primary_color": "#007bff"
                }
            }
        }

        # Act
        response = await client.post("/tenants", headers=auth_headers, json=tenant_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["settings"] == tenant_data["settings"]
        assert data["plan"] == "enterprise"

    @pytest.mark.asyncio
    async def test_create_tenant_plan_validation(self, client: AsyncClient, auth_headers: dict):
        """Test tenant plan validation."""
        valid_plans = ["free", "business", "enterprise"]

        for plan in valid_plans:
            tenant_data = {
                "name": f"Tenant {plan}",
                "domain": f"{plan}.example.com",
                "plan": plan
            }

            response = await client.post("/tenants", headers=auth_headers, json=tenant_data)
            assert response.status_code == 201
            assert response.json()["plan"] == plan

    @pytest.mark.asyncio
    async def test_create_tenant_empty_request_body(self, client: AsyncClient, auth_headers: dict):
        """Test empty request body returns validation error."""
        # Act
        response = await client.post("/tenants", headers=auth_headers, json={})

        # Assert
        assert response.status_code == 422
        error_response = response.json()
        assert "error" in error_response

    @pytest.mark.asyncio
    async def test_create_tenant_null_values(self, client: AsyncClient, auth_headers: dict):
        """Test null values in required fields."""
        # Arrange
        invalid_data = {
            "name": None,
            "domain": None
        }

        # Act
        response = await client.post("/tenants", headers=auth_headers, json=invalid_data)

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_tenant_response_headers(self, client: AsyncClient, auth_headers: dict, valid_tenant_data: dict):
        """Test that response includes correct headers."""
        # Act
        response = await client.post("/tenants", headers=auth_headers, json=valid_tenant_data)

        # Assert
        assert response.status_code == 201
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_create_tenant_unicode_handling(self, client: AsyncClient, auth_headers: dict):
        """Test that unicode characters are handled correctly."""
        # Arrange
        unicode_tenant_data = {
            "name": "Test Org 测试机构 🌟",
            "domain": "unicode.example.com"
        }

        # Act
        response = await client.post("/tenants", headers=auth_headers, json=unicode_tenant_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == unicode_tenant_data["name"]