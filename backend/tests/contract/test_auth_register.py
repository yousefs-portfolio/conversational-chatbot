"""
Contract test for POST /auth/register endpoint.

This test validates the API contract defined in openapi.yaml without any implementation.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient


class TestAuthRegisterContract:
    """Test contract compliance for user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success_response_format(self, client: AsyncClient):
        """Test successful registration returns correct response format."""
        # Arrange
        valid_user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "full_name": "New Test User"
        }

        # Act
        response = await client.post("/auth/register", json=valid_user_data)

        # Assert - This MUST FAIL initially (endpoint doesn't exist yet)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"

        # Validate response structure according to OpenAPI spec
        response_data = response.json()
        assert "id" in response_data
        assert "email" in response_data
        assert "full_name" in response_data
        assert "is_active" in response_data
        assert "is_verified" in response_data
        assert "created_at" in response_data
        assert "updated_at" in response_data

        # Validate data types
        assert isinstance(response_data["id"], str)
        assert isinstance(response_data["email"], str)
        assert isinstance(response_data["full_name"], str)
        assert isinstance(response_data["is_active"], bool)
        assert isinstance(response_data["is_verified"], bool)
        assert isinstance(response_data["created_at"], str)
        assert isinstance(response_data["updated_at"], str)

        # Validate business logic
        assert response_data["email"] == valid_user_data["email"]
        assert response_data["full_name"] == valid_user_data["full_name"]
        assert response_data["is_active"] is True
        assert response_data["is_verified"] is False

        # Validate UUID format
        import uuid
        uuid.UUID(response_data["id"])  # Should not raise exception

        # Validate datetime format
        from datetime import datetime
        datetime.fromisoformat(response_data["created_at"].replace('Z', '+00:00'))
        datetime.fromisoformat(response_data["updated_at"].replace('Z', '+00:00'))

        # Ensure password is not in response
        assert "password" not in response_data
        assert "password_hash" not in response_data

    @pytest.mark.asyncio
    async def test_register_with_tenant_id(self, client: AsyncClient):
        """Test registration with optional tenant_id."""
        # Arrange
        user_data_with_tenant = {
            "email": "tenant_user@example.com",
            "password": "securepassword123",
            "full_name": "Tenant User",
            "tenant_id": "123e4567-e89b-12d3-a456-426614174000"
        }

        # Act
        response = await client.post("/auth/register", json=user_data_with_tenant)

        # Assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["email"] == user_data_with_tenant["email"]

    @pytest.mark.asyncio
    async def test_register_validation_errors(self, client: AsyncClient):
        """Test validation error response format (400)."""
        # Test cases for validation errors
        validation_test_cases = [
            # Missing required fields
            {
                "data": {"email": "test@example.com"},
                "description": "missing password and full_name"
            },
            {
                "data": {"password": "test123"},
                "description": "missing email and full_name"
            },
            {
                "data": {"full_name": "Test User"},
                "description": "missing email and password"
            },
            # Invalid email format
            {
                "data": {
                    "email": "not-an-email",
                    "password": "testpassword123",
                    "full_name": "Test User"
                },
                "description": "invalid email format"
            },
            # Password too short
            {
                "data": {
                    "email": "test@example.com",
                    "password": "short",
                    "full_name": "Test User"
                },
                "description": "password too short"
            },
            # Full name too short
            {
                "data": {
                    "email": "test@example.com",
                    "password": "testpassword123",
                    "full_name": "A"
                },
                "description": "full_name too short"
            },
            # Full name too long
            {
                "data": {
                    "email": "test@example.com",
                    "password": "testpassword123",
                    "full_name": "A" * 101  # Over 100 character limit
                },
                "description": "full_name too long"
            }
        ]

        for test_case in validation_test_cases:
            # Act
            response = await client.post("/auth/register", json=test_case["data"])

            # Assert
            assert response.status_code == 400, f"Expected 400 for {test_case['description']}, got {response.status_code}"

            # Validate error response structure
            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response
            assert isinstance(error_response["error"], str)
            assert isinstance(error_response["message"], str)

    @pytest.mark.asyncio
    async def test_register_duplicate_email_conflict(self, client: AsyncClient):
        """Test duplicate email returns 409 conflict."""
        # Arrange
        user_data = {
            "email": "duplicate@example.com",
            "password": "testpassword123",
            "full_name": "First User"
        }

        # Act - Register first user
        first_response = await client.post("/auth/register", json=user_data)
        assert first_response.status_code == 201

        # Act - Try to register with same email
        duplicate_data = user_data.copy()
        duplicate_data["full_name"] = "Second User"
        second_response = await client.post("/auth/register", json=duplicate_data)

        # Assert
        assert second_response.status_code == 409, f"Expected 409, got {second_response.status_code}"

        # Validate conflict error response
        error_response = second_response.json()
        assert "error" in error_response
        assert "message" in error_response
        assert error_response["error"] == "conflict"

    @pytest.mark.asyncio
    async def test_register_request_content_type(self, client: AsyncClient):
        """Test that endpoint only accepts application/json."""
        # Arrange
        user_data = {
            "email": "test@example.com",
            "password": "testpassword123",
            "full_name": "Test User"
        }

        # Act - Send as form data instead of JSON
        response = await client.post(
            "/auth/register",
            data=user_data,  # form data instead of json
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Assert - Should reject non-JSON content
        assert response.status_code in [400, 415, 422]  # Bad Request, Unsupported Media Type, or Unprocessable Entity

    @pytest.mark.asyncio
    async def test_register_empty_request_body(self, client: AsyncClient):
        """Test empty request body returns validation error."""
        # Act
        response = await client.post("/auth/register", json={})

        # Assert
        assert response.status_code == 400
        error_response = response.json()
        assert "error" in error_response

    @pytest.mark.asyncio
    async def test_register_null_values(self, client: AsyncClient):
        """Test null values in required fields."""
        # Arrange
        invalid_data = {
            "email": None,
            "password": None,
            "full_name": None
        }

        # Act
        response = await client.post("/auth/register", json=invalid_data)

        # Assert
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_register_extra_fields_ignored(self, client: AsyncClient):
        """Test that extra fields in request are ignored."""
        # Arrange
        user_data_with_extras = {
            "email": "extrafields@example.com",
            "password": "testpassword123",
            "full_name": "Extra Fields User",
            "extra_field": "should be ignored",
            "admin": True,  # Should not make user admin
            "id": "should-be-ignored"  # ID should be generated
        }

        # Act
        response = await client.post("/auth/register", json=user_data_with_extras)

        # Assert
        assert response.status_code == 201
        response_data = response.json()

        # Extra fields should not appear in response
        assert "extra_field" not in response_data
        assert "admin" not in response_data

        # ID should be generated, not use provided value
        assert response_data["id"] != "should-be-ignored"

    @pytest.mark.asyncio
    async def test_register_response_headers(self, client: AsyncClient):
        """Test that response includes correct headers."""
        # Arrange
        user_data = {
            "email": "headers@example.com",
            "password": "testpassword123",
            "full_name": "Headers Test User"
        }

        # Act
        response = await client.post("/auth/register", json=user_data)

        # Assert
        assert response.status_code == 201
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_register_unicode_handling(self, client: AsyncClient):
        """Test that unicode characters are handled correctly."""
        # Arrange
        unicode_user_data = {
            "email": "unicode@example.com",
            "password": "testpassword123",
            "full_name": "Test User 测试用户 🌟"
        }

        # Act
        response = await client.post("/auth/register", json=unicode_user_data)

        # Assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["full_name"] == unicode_user_data["full_name"]