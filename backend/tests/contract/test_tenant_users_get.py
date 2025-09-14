"""
Contract test for GET /tenants/{tenant_id}/users endpoint.

This test validates the API contract for retrieving tenant users.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from tests.conftest import assert_valid_uuid, assert_datetime_format


class TestTenantUsersGetContract:
    """Test contract compliance for tenant users listing endpoint."""

    @pytest.fixture
    async def tenant_with_users(self, client: AsyncClient, auth_headers: dict):
        """Create a tenant with multiple users for testing."""
        # Create tenant
        tenant_data = {
            "name": "Multi-User Tenant",
            "domain": "multiuser.example.com",
            "plan": "business"
        }
        tenant_response = await client.post("/tenants", headers=auth_headers, json=tenant_data)
        assert tenant_response.status_code == 201
        tenant = tenant_response.json()

        # Add additional users to tenant
        additional_users = [
            {
                "email": "user2@example.com",
                "password": "testpassword123",
                "full_name": "Second User",
                "role": "member"
            },
            {
                "email": "user3@example.com",
                "password": "testpassword123",
                "full_name": "Third User",
                "role": "admin"
            }
        ]

        for user_data in additional_users:
            user_response = await client.post(f"/tenants/{tenant['id']}/users", headers=auth_headers, json=user_data)
            assert user_response.status_code == 201

        return tenant

    @pytest.mark.asyncio
    async def test_get_tenant_users_success(self, client: AsyncClient, auth_headers: dict, tenant_with_users: dict):
        """Test successful tenant users retrieval returns 200."""
        # Act
        response = await client.get(f"/tenants/{tenant_with_users['id']}/users", headers=auth_headers)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()

        # Validate response structure
        assert isinstance(data, dict)
        assert "users" in data
        assert "total_count" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data

        # Validate data types
        assert isinstance(data["users"], list)
        assert isinstance(data["total_count"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["per_page"], int)
        assert isinstance(data["total_pages"], int)

        # Validate pagination values
        assert data["page"] >= 1
        assert data["per_page"] > 0
        assert data["total_pages"] >= 1
        assert data["total_count"] >= 1  # Should have at least the owner

        # Validate user objects
        assert len(data["users"]) <= data["per_page"]
        assert len(data["users"]) > 0

        for user in data["users"]:
            # Validate user structure
            required_user_fields = [
                "id", "email", "full_name", "role", "is_active",
                "created_at", "updated_at", "last_login"
            ]
            for field in required_user_fields:
                assert field in user, f"Missing required field: {field}"

            # Validate data types
            assert isinstance(user["id"], str)
            assert isinstance(user["email"], str)
            assert isinstance(user["full_name"], str)
            assert isinstance(user["role"], str)
            assert isinstance(user["is_active"], bool)
            assert isinstance(user["created_at"], str)
            assert isinstance(user["updated_at"], str)
            # last_login can be null for users who haven't logged in
            if user["last_login"] is not None:
                assert isinstance(user["last_login"], str)

            # Validate formats
            assert_valid_uuid(user["id"])
            assert_datetime_format(user["created_at"])
            assert_datetime_format(user["updated_at"])
            if user["last_login"]:
                assert_datetime_format(user["last_login"])

            # Validate role values
            assert user["role"] in ["owner", "admin", "member", "viewer"]

            # Ensure sensitive data is not included
            assert "password" not in user
            assert "password_hash" not in user

    @pytest.mark.asyncio
    async def test_get_tenant_users_without_auth_unauthorized(self, client: AsyncClient, tenant_with_users: dict):
        """Test tenant users retrieval without authentication returns 401."""
        # Act
        response = await client.get(f"/tenants/{tenant_with_users['id']}/users")

        # Assert
        assert response.status_code == 401
        error_data = response.json()
        assert "error" in error_data
        assert "message" in error_data

    @pytest.mark.asyncio
    async def test_get_tenant_users_invalid_token_unauthorized(self, client: AsyncClient, tenant_with_users: dict):
        """Test tenant users retrieval with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.get(f"/tenants/{tenant_with_users['id']}/users", headers=invalid_headers)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_tenant_users_nonexistent_tenant_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test retrieval of users for non-existent tenant returns 404."""
        # Arrange
        fake_tenant_id = "123e4567-e89b-12d3-a456-426614174000"

        # Act
        response = await client.get(f"/tenants/{fake_tenant_id}/users", headers=auth_headers)

        # Assert
        assert response.status_code == 404
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response
        assert error_response["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_tenant_users_invalid_uuid_format(self, client: AsyncClient, auth_headers: dict):
        """Test retrieval with invalid tenant UUID format returns 422."""
        invalid_ids = [
            "invalid-uuid",
            "123",
            "not-a-uuid-at-all"
        ]

        for invalid_id in invalid_ids:
            # Act
            response = await client.get(f"/tenants/{invalid_id}/users", headers=auth_headers)

            # Assert
            assert response.status_code == 422, f"Expected 422 for invalid UUID: {invalid_id}, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_get_tenant_users_forbidden_access(self, client: AsyncClient, tenant_with_users: dict):
        """Test tenant users retrieval with user who doesn't have access returns 403."""
        # Create unauthorized user
        user_data = {
            "email": "unauthorized@example.com",
            "password": "testpassword123",
            "full_name": "Unauthorized User"
        }
        register_response = await client.post("/auth/register", json=user_data)
        assert register_response.status_code == 201

        login_response = await client.post("/auth/login", json={
            "email": user_data["email"],
            "password": user_data["password"]
        })
        assert login_response.status_code == 200
        unauthorized_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Try to access tenant users
        response = await client.get(f"/tenants/{tenant_with_users['id']}/users", headers=unauthorized_headers)

        # Assert - Should be forbidden
        assert response.status_code == 403
        error_response = response.json()
        assert "error" in error_response
        assert error_response["error"] == "forbidden"

    @pytest.mark.asyncio
    async def test_get_tenant_users_pagination(self, client: AsyncClient, auth_headers: dict, tenant_with_users: dict):
        """Test tenant users pagination parameters."""
        # Test default pagination
        response = await client.get(f"/tenants/{tenant_with_users['id']}/users", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] == 20  # Default page size

        # Test custom pagination
        response = await client.get(
            f"/tenants/{tenant_with_users['id']}/users?page=1&per_page=5",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] == 5
        assert len(data["users"]) <= 5

        # Test page 2 (if there are enough users)
        if data["total_pages"] > 1:
            response = await client.get(
                f"/tenants/{tenant_with_users['id']}/users?page=2&per_page=5",
                headers=auth_headers
            )
            assert response.status_code == 200
            page2_data = response.json()
            assert page2_data["page"] == 2

    @pytest.mark.asyncio
    async def test_get_tenant_users_filter_by_role(self, client: AsyncClient, auth_headers: dict, tenant_with_users: dict):
        """Test filtering tenant users by role."""
        # Test filtering by admin role
        response = await client.get(
            f"/tenants/{tenant_with_users['id']}/users?role=admin",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # All returned users should have admin role
        for user in data["users"]:
            assert user["role"] == "admin"

        # Test filtering by member role
        response = await client.get(
            f"/tenants/{tenant_with_users['id']}/users?role=member",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # All returned users should have member role
        for user in data["users"]:
            assert user["role"] == "member"

    @pytest.mark.asyncio
    async def test_get_tenant_users_filter_by_status(self, client: AsyncClient, auth_headers: dict, tenant_with_users: dict):
        """Test filtering tenant users by active status."""
        # Test filtering by active users
        response = await client.get(
            f"/tenants/{tenant_with_users['id']}/users?is_active=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # All returned users should be active
        for user in data["users"]:
            assert user["is_active"] is True

        # Test filtering by inactive users
        response = await client.get(
            f"/tenants/{tenant_with_users['id']}/users?is_active=false",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # All returned users should be inactive
        for user in data["users"]:
            assert user["is_active"] is False

    @pytest.mark.asyncio
    async def test_get_tenant_users_search(self, client: AsyncClient, auth_headers: dict, tenant_with_users: dict):
        """Test searching tenant users by email or name."""
        # Test search by email
        response = await client.get(
            f"/tenants/{tenant_with_users['id']}/users?search=user2@example.com",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Should find the matching user
        found_user = None
        for user in data["users"]:
            if user["email"] == "user2@example.com":
                found_user = user
                break
        assert found_user is not None

        # Test search by name
        response = await client.get(
            f"/tenants/{tenant_with_users['id']}/users?search=Third User",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Should find the matching user
        found_user = None
        for user in data["users"]:
            if user["full_name"] == "Third User":
                found_user = user
                break
        assert found_user is not None

    @pytest.mark.asyncio
    async def test_get_tenant_users_sorting(self, client: AsyncClient, auth_headers: dict, tenant_with_users: dict):
        """Test sorting tenant users."""
        # Test sorting by email
        response = await client.get(
            f"/tenants/{tenant_with_users['id']}/users?sort_by=email&sort_order=asc",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Verify ascending email sort
        emails = [user["email"] for user in data["users"]]
        assert emails == sorted(emails)

        # Test sorting by created_at descending
        response = await client.get(
            f"/tenants/{tenant_with_users['id']}/users?sort_by=created_at&sort_order=desc",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Verify descending created_at sort
        created_dates = [user["created_at"] for user in data["users"]]
        assert created_dates == sorted(created_dates, reverse=True)

    @pytest.mark.asyncio
    async def test_get_tenant_users_invalid_query_params(self, client: AsyncClient, auth_headers: dict, tenant_with_users: dict):
        """Test invalid query parameters return appropriate errors."""
        invalid_params = [
            "page=0",  # Page must be >= 1
            "page=-1",
            "per_page=0",  # Per page must be > 0
            "per_page=-1",
            "per_page=101",  # Assuming max per_page is 100
            "role=invalid_role",
            "is_active=invalid_boolean",
            "sort_by=invalid_field",
            "sort_order=invalid_order"
        ]

        for param in invalid_params:
            response = await client.get(
                f"/tenants/{tenant_with_users['id']}/users?{param}",
                headers=auth_headers
            )
            # Should return 422 for validation errors
            assert response.status_code == 422, f"Expected 422 for invalid param: {param}, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_get_tenant_users_response_headers(self, client: AsyncClient, auth_headers: dict, tenant_with_users: dict):
        """Test that response includes correct headers."""
        # Act
        response = await client.get(f"/tenants/{tenant_with_users['id']}/users", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_tenant_users_empty_tenant(self, client: AsyncClient, auth_headers: dict):
        """Test getting users for a tenant with only the owner."""
        # Create a new tenant (will only have owner)
        tenant_data = {
            "name": "Empty Tenant",
            "domain": "empty.example.com"
        }
        tenant_response = await client.post("/tenants", headers=auth_headers, json=tenant_data)
        assert tenant_response.status_code == 201
        tenant = tenant_response.json()

        # Get users
        response = await client.get(f"/tenants/{tenant['id']}/users", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1  # Only owner
        assert len(data["users"]) == 1
        assert data["users"][0]["role"] == "owner"