"""
Contract test for GET /tenants/{tenant_id} endpoint.

This test validates the API contract for retrieving tenant information.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from tests.conftest import assert_valid_uuid, assert_datetime_format


class TestTenantsGetContract:
    """Test contract compliance for tenant retrieval endpoint."""

    @pytest.fixture
    async def existing_tenant(self, client: AsyncClient, auth_headers: dict):
        """Create a tenant for testing retrieval."""
        tenant_data = {
            "name": "Test Tenant for Retrieval",
            "domain": "retrieval-test.example.com",
            "plan": "business",
            "settings": {
                "max_users": 50,
                "features": ["analytics", "custom_branding"]
            }
        }

        response = await client.post("/tenants", headers=auth_headers, json=tenant_data)
        assert response.status_code == 201
        return response.json()

    @pytest.mark.asyncio
    async def test_get_tenant_success(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test successful tenant retrieval returns 200."""
        # Act
        response = await client.get(f"/tenants/{existing_tenant['id']}", headers=auth_headers)

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

        # Validate data values match created tenant
        assert data["id"] == existing_tenant["id"]
        assert data["name"] == existing_tenant["name"]
        assert data["domain"] == existing_tenant["domain"]
        assert data["plan"] == existing_tenant["plan"]
        assert data["settings"] == existing_tenant["settings"]
        assert data["is_active"] == existing_tenant["is_active"]

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

        # Validate user_count is non-negative
        assert data["user_count"] >= 0

    @pytest.mark.asyncio
    async def test_get_tenant_without_auth_unauthorized(self, client: AsyncClient, existing_tenant: dict):
        """Test tenant retrieval without authentication returns 401."""
        # Act
        response = await client.get(f"/tenants/{existing_tenant['id']}")

        # Assert
        assert response.status_code == 401
        error_data = response.json()
        assert "error" in error_data
        assert "message" in error_data

    @pytest.mark.asyncio
    async def test_get_tenant_invalid_token_unauthorized(self, client: AsyncClient, existing_tenant: dict):
        """Test tenant retrieval with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.get(f"/tenants/{existing_tenant['id']}", headers=invalid_headers)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_tenant_nonexistent_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test retrieval of non-existent tenant returns 404."""
        # Arrange
        fake_tenant_id = "123e4567-e89b-12d3-a456-426614174000"

        # Act
        response = await client.get(f"/tenants/{fake_tenant_id}", headers=auth_headers)

        # Assert
        assert response.status_code == 404
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response
        assert error_response["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_tenant_invalid_uuid_format(self, client: AsyncClient, auth_headers: dict):
        """Test retrieval with invalid UUID format returns 422."""
        invalid_ids = [
            "invalid-uuid",
            "123",
            "not-a-uuid-at-all",
            "12345678-1234-1234-1234-12345678901",  # Too short
            "12345678-1234-1234-1234-1234567890123"  # Too long
        ]

        for invalid_id in invalid_ids:
            # Act
            response = await client.get(f"/tenants/{invalid_id}", headers=auth_headers)

            # Assert
            assert response.status_code == 422, f"Expected 422 for invalid UUID: {invalid_id}, got {response.status_code}"
            error_response = response.json()
            assert "error" in error_response

    @pytest.mark.asyncio
    async def test_get_tenant_forbidden_access(self, client: AsyncClient):
        """Test tenant retrieval with user who doesn't have access returns 403."""
        # This test assumes the user doesn't have access to the tenant
        # Create a tenant with one user, then try to access with different user

        # First create a user and tenant
        user1_data = {
            "email": "tenant_owner@example.com",
            "password": "testpassword123",
            "full_name": "Tenant Owner"
        }
        register_response = await client.post("/auth/register", json=user1_data)
        assert register_response.status_code == 201

        login_response = await client.post("/auth/login", json={
            "email": user1_data["email"],
            "password": user1_data["password"]
        })
        assert login_response.status_code == 200
        user1_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Create tenant as user1
        tenant_data = {
            "name": "User1 Tenant",
            "domain": "user1.example.com"
        }
        tenant_response = await client.post("/tenants", headers=user1_headers, json=tenant_data)
        assert tenant_response.status_code == 201
        tenant = tenant_response.json()

        # Create second user
        user2_data = {
            "email": "other_user@example.com",
            "password": "testpassword123",
            "full_name": "Other User"
        }
        register_response2 = await client.post("/auth/register", json=user2_data)
        assert register_response2.status_code == 201

        login_response2 = await client.post("/auth/login", json={
            "email": user2_data["email"],
            "password": user2_data["password"]
        })
        assert login_response2.status_code == 200
        user2_headers = {"Authorization": f"Bearer {login_response2.json()['access_token']}"}

        # Try to access tenant as user2
        response = await client.get(f"/tenants/{tenant['id']}", headers=user2_headers)

        # Assert - Should be forbidden
        assert response.status_code == 403
        error_response = response.json()
        assert "error" in error_response
        assert error_response["error"] == "forbidden"

    @pytest.mark.asyncio
    async def test_get_tenant_response_headers(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test that response includes correct headers."""
        # Act
        response = await client.get(f"/tenants/{existing_tenant['id']}", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_tenant_with_users(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test tenant retrieval includes correct user count."""
        # Act
        response = await client.get(f"/tenants/{existing_tenant['id']}", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Should have at least 1 user (the owner)
        assert data["user_count"] >= 1

    @pytest.mark.asyncio
    async def test_get_tenant_cached_response(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test that multiple requests return consistent data."""
        # Act - Make multiple requests
        response1 = await client.get(f"/tenants/{existing_tenant['id']}", headers=auth_headers)
        response2 = await client.get(f"/tenants/{existing_tenant['id']}", headers=auth_headers)

        # Assert
        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Should return identical data
        assert data1 == data2

    @pytest.mark.asyncio
    async def test_get_tenant_permissions_check(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test that tenant retrieval properly checks user permissions."""
        # This test ensures only authorized users can view tenant details
        # Act
        response = await client.get(f"/tenants/{existing_tenant['id']}", headers=auth_headers)

        # Assert - User should have access since they created the tenant
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == existing_tenant["id"]

    @pytest.mark.asyncio
    async def test_get_tenant_includes_all_required_fields(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test that response includes all fields required by the API specification."""
        # Act
        response = await client.get(f"/tenants/{existing_tenant['id']}", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Check all required fields are present and not null
        required_fields = [
            "id", "name", "domain", "plan", "settings", "is_active",
            "created_at", "updated_at", "owner_id", "user_count"
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
            assert data[field] is not None, f"Field {field} should not be null"