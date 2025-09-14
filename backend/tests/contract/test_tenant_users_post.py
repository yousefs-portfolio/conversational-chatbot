"""
Contract test for POST /tenants/{tenant_id}/users endpoint.

This test validates the API contract for adding users to a tenant.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from tests.conftest import assert_valid_uuid, assert_datetime_format


class TestTenantUsersPostContract:
    """Test contract compliance for adding users to tenant endpoint."""

    @pytest.fixture
    async def existing_tenant(self, client: AsyncClient, auth_headers: dict):
        """Create a tenant for testing user addition."""
        tenant_data = {
            "name": "User Addition Test Tenant",
            "domain": "useradd.example.com",
            "plan": "business"
        }
        response = await client.post("/tenants", headers=auth_headers, json=tenant_data)
        assert response.status_code == 201
        return response.json()

    @pytest.fixture
    def valid_user_data(self):
        """Valid user addition data."""
        return {
            "email": "newuser@example.com",
            "password": "testpassword123",
            "full_name": "New Tenant User",
            "role": "member"
        }

    @pytest.fixture
    def invite_user_data(self):
        """Valid user invitation data (without password)."""
        return {
            "email": "inviteduser@example.com",
            "full_name": "Invited User",
            "role": "admin"
        }

    @pytest.mark.asyncio
    async def test_add_user_to_tenant_success(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict, valid_user_data: dict):
        """Test successful user addition to tenant returns 201."""
        # Act
        response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=valid_user_data)

        # Assert - This MUST FAIL initially
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        data = response.json()

        # Validate response structure
        required_fields = [
            "id", "email", "full_name", "role", "is_active",
            "is_verified", "tenant_id", "created_at", "updated_at"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Validate data values
        assert data["email"] == valid_user_data["email"]
        assert data["full_name"] == valid_user_data["full_name"]
        assert data["role"] == valid_user_data["role"]
        assert data["tenant_id"] == existing_tenant["id"]
        assert data["is_active"] is True
        assert data["is_verified"] is False  # New users should be unverified

        # Validate data types
        assert isinstance(data["id"], str)
        assert isinstance(data["email"], str)
        assert isinstance(data["full_name"], str)
        assert isinstance(data["role"], str)
        assert isinstance(data["is_active"], bool)
        assert isinstance(data["is_verified"], bool)
        assert isinstance(data["tenant_id"], str)
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

        # Validate formats
        assert_valid_uuid(data["id"])
        assert_valid_uuid(data["tenant_id"])
        assert_datetime_format(data["created_at"])
        assert_datetime_format(data["updated_at"])

        # Ensure password is not in response
        assert "password" not in data
        assert "password_hash" not in data

    @pytest.mark.asyncio
    async def test_invite_user_to_tenant_success(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict, invite_user_data: dict):
        """Test successful user invitation to tenant (no password required)."""
        # Act
        response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=invite_user_data)

        # Assert
        assert response.status_code == 201
        data = response.json()

        # Validate invitation-specific behavior
        assert data["email"] == invite_user_data["email"]
        assert data["full_name"] == invite_user_data["full_name"]
        assert data["role"] == invite_user_data["role"]
        assert data["is_active"] is False  # Invited users start inactive
        assert data["is_verified"] is False

        # Should include invitation fields
        assert "invitation_token" in data
        assert "invitation_expires_at" in data
        assert isinstance(data["invitation_token"], str)
        assert isinstance(data["invitation_expires_at"], str)
        assert_datetime_format(data["invitation_expires_at"])

    @pytest.mark.asyncio
    async def test_add_user_without_auth_unauthorized(self, client: AsyncClient, existing_tenant: dict, valid_user_data: dict):
        """Test adding user without authentication returns 401."""
        # Act
        response = await client.post(f"/tenants/{existing_tenant['id']}/users", json=valid_user_data)

        # Assert
        assert response.status_code == 401
        error_data = response.json()
        assert "error" in error_data
        assert "message" in error_data

    @pytest.mark.asyncio
    async def test_add_user_invalid_token_unauthorized(self, client: AsyncClient, existing_tenant: dict, valid_user_data: dict):
        """Test adding user with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=invalid_headers, json=valid_user_data)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_add_user_nonexistent_tenant_not_found(self, client: AsyncClient, auth_headers: dict, valid_user_data: dict):
        """Test adding user to non-existent tenant returns 404."""
        # Arrange
        fake_tenant_id = "123e4567-e89b-12d3-a456-426614174000"

        # Act
        response = await client.post(f"/tenants/{fake_tenant_id}/users", headers=auth_headers, json=valid_user_data)

        # Assert
        assert response.status_code == 404
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response
        assert error_response["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_add_user_invalid_uuid_format(self, client: AsyncClient, auth_headers: dict, valid_user_data: dict):
        """Test adding user with invalid tenant UUID format returns 422."""
        invalid_ids = [
            "invalid-uuid",
            "123",
            "not-a-uuid-at-all"
        ]

        for invalid_id in invalid_ids:
            # Act
            response = await client.post(f"/tenants/{invalid_id}/users", headers=auth_headers, json=valid_user_data)

            # Assert
            assert response.status_code == 422, f"Expected 422 for invalid UUID: {invalid_id}, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_add_user_validation_errors(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test validation error responses for invalid user data."""
        validation_test_cases = [
            # Missing required fields
            {
                "data": {"full_name": "Test User", "role": "member"},
                "description": "missing email"
            },
            {
                "data": {"email": "test@example.com", "role": "member"},
                "description": "missing full_name"
            },
            # Invalid email format
            {
                "data": {
                    "email": "not-an-email",
                    "full_name": "Test User",
                    "role": "member"
                },
                "description": "invalid email format"
            },
            # Invalid data types
            {
                "data": {
                    "email": 123,
                    "full_name": "Test User",
                    "role": "member"
                },
                "description": "invalid email type"
            },
            {
                "data": {
                    "email": "test@example.com",
                    "full_name": 123,
                    "role": "member"
                },
                "description": "invalid full_name type"
            },
            {
                "data": {
                    "email": "test@example.com",
                    "full_name": "Test User",
                    "role": 123
                },
                "description": "invalid role type"
            },
            # Invalid field values
            {
                "data": {
                    "email": "",
                    "full_name": "Test User",
                    "role": "member"
                },
                "description": "empty email"
            },
            {
                "data": {
                    "email": "test@example.com",
                    "full_name": "",
                    "role": "member"
                },
                "description": "empty full_name"
            },
            {
                "data": {
                    "email": "test@example.com",
                    "full_name": "A" * 101,
                    "role": "member"
                },
                "description": "full_name too long"
            },
            {
                "data": {
                    "email": "test@example.com",
                    "full_name": "Test User",
                    "role": "invalid-role"
                },
                "description": "invalid role value"
            },
            # Password validation (when provided)
            {
                "data": {
                    "email": "test@example.com",
                    "full_name": "Test User",
                    "role": "member",
                    "password": "short"
                },
                "description": "password too short"
            }
        ]

        for test_case in validation_test_cases:
            # Act
            response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=test_case["data"])

            # Assert
            assert response.status_code == 422, f"Expected 422 for {test_case['description']}, got {response.status_code}"

            # Validate error response structure
            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response

    @pytest.mark.asyncio
    async def test_add_user_duplicate_email_conflict(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test adding user with duplicate email returns 409 conflict."""
        # Arrange
        user_data = {
            "email": "duplicate_in_tenant@example.com",
            "full_name": "First User",
            "role": "member"
        }

        # Act - Add first user
        first_response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=user_data)
        assert first_response.status_code == 201

        # Act - Try to add user with same email to same tenant
        duplicate_data = user_data.copy()
        duplicate_data["full_name"] = "Second User"
        second_response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=duplicate_data)

        # Assert
        assert second_response.status_code == 409
        error_response = second_response.json()
        assert "error" in error_response
        assert error_response["error"] == "conflict"

    @pytest.mark.asyncio
    async def test_add_user_forbidden_access(self, client: AsyncClient, existing_tenant: dict, valid_user_data: dict):
        """Test adding user with insufficient permissions returns 403."""
        # Create user with member role (should not be able to add users)
        member_user_data = {
            "email": "member@example.com",
            "password": "testpassword123",
            "full_name": "Member User"
        }
        register_response = await client.post("/auth/register", json=member_user_data)
        assert register_response.status_code == 201

        login_response = await client.post("/auth/login", json={
            "email": member_user_data["email"],
            "password": member_user_data["password"]
        })
        assert login_response.status_code == 200
        member_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Try to add user as member (should fail)
        response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=member_headers, json=valid_user_data)

        # Assert - Should be forbidden
        assert response.status_code == 403
        error_response = response.json()
        assert "error" in error_response
        assert error_response["error"] == "forbidden"

    @pytest.mark.asyncio
    async def test_add_user_role_validation(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test user role validation."""
        valid_roles = ["member", "admin", "viewer"]

        for role in valid_roles:
            user_data = {
                "email": f"{role}@example.com",
                "full_name": f"{role.title()} User",
                "role": role
            }

            response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=user_data)
            assert response.status_code == 201
            assert response.json()["role"] == role

        # Test that owner role cannot be assigned
        owner_data = {
            "email": "cannot_be_owner@example.com",
            "full_name": "Cannot Be Owner",
            "role": "owner"
        }
        response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=owner_data)
        assert response.status_code == 422  # Should reject owner role assignment

    @pytest.mark.asyncio
    async def test_add_user_tenant_limits(self, client: AsyncClient, auth_headers: dict):
        """Test tenant user limits based on plan."""
        # Create a free plan tenant
        tenant_data = {
            "name": "Free Plan Tenant",
            "domain": "freeplan.example.com",
            "plan": "free"
        }
        tenant_response = await client.post("/tenants", headers=auth_headers, json=tenant_data)
        assert tenant_response.status_code == 201
        tenant = tenant_response.json()

        # Assuming free plan allows only 1 user (the owner)
        user_data = {
            "email": "exceeds_limit@example.com",
            "full_name": "Exceeds Limit",
            "role": "member"
        }

        # This might succeed or fail depending on plan limits
        response = await client.post(f"/tenants/{tenant['id']}/users", headers=auth_headers, json=user_data)

        # If it fails, it should be due to plan limits
        if response.status_code == 402:  # Payment Required
            error_response = response.json()
            assert "error" in error_response
            assert "limit" in error_response["message"].lower()

    @pytest.mark.asyncio
    async def test_add_existing_system_user_to_tenant(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test adding an existing system user to a tenant."""
        # First create a user in the system
        existing_user_data = {
            "email": "existing_system_user@example.com",
            "password": "testpassword123",
            "full_name": "Existing System User"
        }
        register_response = await client.post("/auth/register", json=existing_user_data)
        assert register_response.status_code == 201

        # Now add this existing user to tenant (should not require password)
        tenant_user_data = {
            "email": "existing_system_user@example.com",
            "role": "member"
        }

        response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=tenant_user_data)

        # Should succeed and add existing user to tenant
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == existing_user_data["email"]
        assert data["full_name"] == existing_user_data["full_name"]  # Should use existing data
        assert data["role"] == "member"

    @pytest.mark.asyncio
    async def test_add_user_empty_request_body(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test adding user with empty request body returns validation error."""
        # Act
        response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json={})

        # Assert
        assert response.status_code == 422
        error_response = response.json()
        assert "error" in error_response

    @pytest.mark.asyncio
    async def test_add_user_null_values(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test adding user with null values in required fields."""
        # Arrange
        invalid_data = {
            "email": None,
            "full_name": None,
            "role": None
        }

        # Act
        response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=invalid_data)

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_add_user_response_headers(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict, valid_user_data: dict):
        """Test that response includes correct headers."""
        # Act
        response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=valid_user_data)

        # Assert
        assert response.status_code == 201
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_add_user_unicode_handling(self, client: AsyncClient, auth_headers: dict, existing_tenant: dict):
        """Test that unicode characters are handled correctly."""
        # Arrange
        unicode_user_data = {
            "email": "unicode@example.com",
            "full_name": "用户 测试 🌟",
            "role": "member"
        }

        # Act
        response = await client.post(f"/tenants/{existing_tenant['id']}/users", headers=auth_headers, json=unicode_user_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["full_name"] == unicode_user_data["full_name"]