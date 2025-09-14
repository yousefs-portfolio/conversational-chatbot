"""
Contract test for PUT /tenants/{tenant_id} endpoint.

This test validates the API contract for updating tenant information.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from tests.conftest import assert_valid_uuid, assert_datetime_format


class TestTenantsPutContract:
    """Test contract compliance for tenant update endpoint."""

    @pytest.fixture
    async def existing_tenant(self, client: AsyncClient, auth_headers: dict):
        """Create a tenant for testing updates."""
        tenant_data = {
            "name": "Test Tenant for Update",
            "domain": "update-test.example.com",
            "plan": "business",
            "settings": {
                "max_users": 50,
                "features": ["analytics"]
            }
        }

        response = await client.post("/tenants", headers=auth_headers, json=tenant_data)
        assert response.status_code == 201
        return response.json()

    @pytest.fixture
    def update_tenant_data(self):
        """Valid tenant update data."""
        return {
            "name": "Updated Tenant Name",
            "plan": "enterprise",
            "settings": {
                "max_users": 200,
                "features": ["analytics", "custom_branding", "sso"],
                "branding": {
                    "logo_url": "https://example.com/new-logo.png",
                    "primary_color": "#ff6b35"
                }
            }
        }

    @pytest.mark.asyncio
    async def test_update_tenant_success(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict, update_tenant_data: dict):
        """Test successful tenant update returns 200."""
        # Act
        response = await client.put(f"/tenants/{existing_tenant['id']}", headers=auth_headers, json=update_tenant_data)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()

        # Validate response structure
        required_fields = [
            "id", "name", "domain", "plan", "settings", "is_active",
            "created_at", "updated_at", "owner_id", "user_count"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Validate updated fields
        assert data["name"] == update_tenant_data["name"]
        assert data["plan"] == update_tenant_data["plan"]
        assert data["settings"] == update_tenant_data["settings"]

        # Validate unchanged fields
        assert data["id"] == existing_tenant["id"]
        assert data["domain"] == existing_tenant["domain"]  # Domain should not change
        assert data["is_active"] == existing_tenant["is_active"]
        assert data["created_at"] == existing_tenant["created_at"]
        assert data["owner_id"] == existing_tenant["owner_id"]

        # Validate updated_at has changed
        assert data["updated_at"] != existing_tenant["updated_at"]

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
        assert isinstance(data["user_count"], int)

        # Validate formats
        assert_valid_uuid(data["id"])
        assert_valid_uuid(data["owner_id"])
        assert_datetime_format(data["created_at"])
        assert_datetime_format(data["updated_at"])

    @pytest.mark.asyncio
    async def test_update_tenant_partial_data(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test partial tenant update."""
        # Arrange - Update only name
        partial_update = {
            "name": "Partially Updated Tenant"
        }

        # Act
        response = await client.put(f"/tenants/{existing_tenant['id']}", headers=auth_headers, json=partial_update)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Updated field
        assert data["name"] == partial_update["name"]

        # Unchanged fields
        assert data["plan"] == existing_tenant["plan"]
        assert data["settings"] == existing_tenant["settings"]
        assert data["domain"] == existing_tenant["domain"]

    @pytest.mark.asyncio
    async def test_update_tenant_without_auth_unauthorized(self, client: AsyncClient, existing_tenant: dict, update_tenant_data: dict):
        """Test tenant update without authentication returns 401."""
        # Act
        response = await client.put(f"/tenants/{existing_tenant['id']}", json=update_tenant_data)

        # Assert
        assert response.status_code == 401
        error_data = response.json()
        assert "error" in error_data
        assert "message" in error_data

    @pytest.mark.asyncio
    async def test_update_tenant_invalid_token_unauthorized(self, client: AsyncClient, existing_tenant: dict, update_tenant_data: dict):
        """Test tenant update with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.put(f"/tenants/{existing_tenant['id']}", headers=invalid_headers, json=update_tenant_data)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_tenant_nonexistent_not_found(self, client: AsyncClient, auth_headers: dict, update_tenant_data: dict):
        """Test update of non-existent tenant returns 404."""
        # Arrange
        fake_tenant_id = "123e4567-e89b-12d3-a456-426614174000"

        # Act
        response = await client.put(f"/tenants/{fake_tenant_id}", headers=auth_headers, json=update_tenant_data)

        # Assert
        assert response.status_code == 404
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response
        assert error_response["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_update_tenant_invalid_uuid_format(self, client: AsyncClient, auth_headers: dict, update_tenant_data: dict):
        """Test update with invalid UUID format returns 422."""
        invalid_ids = [
            "invalid-uuid",
            "123",
            "not-a-uuid-at-all"
        ]

        for invalid_id in invalid_ids:
            # Act
            response = await client.put(f"/tenants/{invalid_id}", headers=auth_headers, json=update_tenant_data)

            # Assert
            assert response.status_code == 422, f"Expected 422 for invalid UUID: {invalid_id}, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_update_tenant_validation_errors(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test validation error responses for invalid update data."""
        validation_test_cases = [
            # Invalid data types
            {
                "data": {"name": 123},
                "description": "invalid name type"
            },
            {
                "data": {"plan": 123},
                "description": "invalid plan type"
            },
            {
                "data": {"settings": "invalid"},
                "description": "invalid settings type"
            },
            {
                "data": {"is_active": "invalid"},
                "description": "invalid is_active type"
            },
            # Invalid field values
            {
                "data": {"name": ""},
                "description": "empty name"
            },
            {
                "data": {"name": "A" * 101},
                "description": "name too long"
            },
            {
                "data": {"plan": "invalid-plan"},
                "description": "invalid plan value"
            },
            # Attempting to change read-only fields
            {
                "data": {"domain": "new-domain.example.com"},
                "description": "attempting to change domain"
            },
            {
                "data": {"id": "123e4567-e89b-12d3-a456-426614174000"},
                "description": "attempting to change id"
            },
            {
                "data": {"owner_id": "123e4567-e89b-12d3-a456-426614174000"},
                "description": "attempting to change owner_id"
            }
        ]

        for test_case in validation_test_cases:
            # Act
            response = await client.put(f"/tenants/{existing_tenant['id']}", headers=auth_headers, json=test_case["data"])

            # Assert
            assert response.status_code == 422, f"Expected 422 for {test_case['description']}, got {response.status_code}"

            # Validate error response structure
            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response

    @pytest.mark.asyncio
    async def test_update_tenant_forbidden_access(self, client: AsyncClient, existing_tenant: dict, update_tenant_data: dict):
        """Test tenant update with user who doesn't have access returns 403."""
        # Create second user
        user2_data = {
            "email": "unauthorized_user@example.com",
            "password": "testpassword123",
            "full_name": "Unauthorized User"
        }
        register_response = await client.post("/auth/register", json=user2_data)
        assert register_response.status_code == 201

        login_response = await client.post("/auth/login", json={
            "email": user2_data["email"],
            "password": user2_data["password"]
        })
        assert login_response.status_code == 200
        user2_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Try to update tenant as unauthorized user
        response = await client.put(f"/tenants/{existing_tenant['id']}", headers=user2_headers, json=update_tenant_data)

        # Assert - Should be forbidden
        assert response.status_code == 403
        error_response = response.json()
        assert "error" in error_response
        assert error_response["error"] == "forbidden"

    @pytest.mark.asyncio
    async def test_update_tenant_settings_merge(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test that settings are properly merged/replaced during update."""
        # Arrange - Update with new settings
        settings_update = {
            "settings": {
                "max_users": 150,
                "features": ["analytics", "api_access"],
                "new_feature": {
                    "enabled": True,
                    "config": {"timeout": 30}
                }
            }
        }

        # Act
        response = await client.put(f"/tenants/{existing_tenant['id']}", headers=auth_headers, json=settings_update)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["settings"] == settings_update["settings"]

    @pytest.mark.asyncio
    async def test_update_tenant_plan_changes(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test updating tenant plan."""
        valid_plans = ["free", "business", "enterprise"]

        for plan in valid_plans:
            plan_update = {"plan": plan}

            response = await client.put(f"/tenants/{existing_tenant['id']}", headers=auth_headers, json=plan_update)
            assert response.status_code == 200
            data = response.json()
            assert data["plan"] == plan

    @pytest.mark.asyncio
    async def test_update_tenant_empty_request_body(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test update with empty request body."""
        # Act
        response = await client.put(f"/tenants/{existing_tenant['id']}", headers=auth_headers, json={})

        # Assert - Should succeed with no changes
        assert response.status_code == 200
        data = response.json()

        # Should match original tenant data (except updated_at)
        assert data["name"] == existing_tenant["name"]
        assert data["plan"] == existing_tenant["plan"]
        assert data["settings"] == existing_tenant["settings"]

    @pytest.mark.asyncio
    async def test_update_tenant_null_values(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test update with null values."""
        # Arrange - Some fields allow null, others don't
        null_data = {
            "name": None,  # Should be invalid
            "settings": None  # May be valid (empty settings)
        }

        # Act
        response = await client.put(f"/tenants/{existing_tenant['id']}", headers=auth_headers, json=null_data)

        # Assert - Should return validation error for null name
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_tenant_response_headers(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict, update_tenant_data: dict):
        """Test that response includes correct headers."""
        # Act
        response = await client.put(f"/tenants/{existing_tenant['id']}", headers=auth_headers, json=update_tenant_data)

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_update_tenant_unicode_handling(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test that unicode characters are handled correctly in updates."""
        # Arrange
        unicode_update = {
            "name": "Updated Org 更新机构 🚀"
        }

        # Act
        response = await client.put(f"/tenants/{existing_tenant['id']}", headers=auth_headers, json=unicode_update)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == unicode_update["name"]