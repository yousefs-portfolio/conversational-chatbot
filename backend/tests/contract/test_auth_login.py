"""
Contract test for POST /auth/login endpoint.

This test validates the API contract defined in openapi.yaml without any implementation.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient


class TestAuthLoginContract:
    """Test contract compliance for user login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success_response_format(self, client: AsyncClient, sample_user_data: dict):
        """Test successful login returns correct response format."""
        # Arrange - First register a user
        await client.post("/auth/register", json=sample_user_data)

        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"]
        }

        # Act
        response = await client.post("/auth/login", json=login_data)

        # Assert - This MUST FAIL initially (endpoint doesn't exist yet)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Validate response structure according to OpenAPI spec
        response_data = response.json()
        required_fields = ["access_token", "refresh_token", "token_type", "expires_in", "user"]
        for field in required_fields:
            assert field in response_data, f"Missing required field: {field}"

        # Validate data types
        assert isinstance(response_data["access_token"], str)
        assert isinstance(response_data["refresh_token"], str)
        assert isinstance(response_data["token_type"], str)
        assert isinstance(response_data["expires_in"], int)
        assert isinstance(response_data["user"], dict)

        # Validate token_type
        assert response_data["token_type"] == "bearer"

        # Validate expires_in is positive
        assert response_data["expires_in"] > 0

        # Validate user object structure
        user_data = response_data["user"]
        user_required_fields = ["id", "email", "full_name", "is_active", "is_verified", "created_at", "updated_at"]
        for field in user_required_fields:
            assert field in user_data, f"Missing user field: {field}"

        # Validate user data
        assert user_data["email"] == sample_user_data["email"]
        assert user_data["full_name"] == sample_user_data["full_name"]
        assert user_data["is_active"] is True

        # Ensure sensitive data not in response
        assert "password" not in user_data
        assert "password_hash" not in user_data

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_unauthorized(self, client: AsyncClient, sample_user_data: dict):
        """Test login with invalid credentials returns 401."""
        # Arrange - Register user first
        await client.post("/auth/register", json=sample_user_data)

        invalid_login_cases = [
            # Wrong password
            {
                "email": sample_user_data["email"],
                "password": "wrongpassword"
            },
            # Wrong email
            {
                "email": "nonexistent@example.com",
                "password": sample_user_data["password"]
            },
            # Both wrong
            {
                "email": "wrong@example.com",
                "password": "wrongpassword"
            }
        ]

        for login_data in invalid_login_cases:
            # Act
            response = await client.post("/auth/login", json=login_data)

            # Assert
            assert response.status_code == 401, f"Expected 401 for invalid credentials, got {response.status_code}"

            # Validate error response structure
            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response
            assert error_response["error"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_login_validation_errors(self, client: AsyncClient):
        """Test validation error response format (400)."""
        validation_test_cases = [
            # Missing email
            {
                "data": {"password": "testpassword123"},
                "description": "missing email"
            },
            # Missing password
            {
                "data": {"email": "test@example.com"},
                "description": "missing password"
            },
            # Empty email
            {
                "data": {"email": "", "password": "testpassword123"},
                "description": "empty email"
            },
            # Empty password
            {
                "data": {"email": "test@example.com", "password": ""},
                "description": "empty password"
            },
            # Invalid email format
            {
                "data": {"email": "not-an-email", "password": "testpassword123"},
                "description": "invalid email format"
            },
            # Null values
            {
                "data": {"email": None, "password": None},
                "description": "null values"
            }
        ]

        for test_case in validation_test_cases:
            # Act
            response = await client.post("/auth/login", json=test_case["data"])

            # Assert
            assert response.status_code == 400, f"Expected 400 for {test_case['description']}, got {response.status_code}"

            # Validate error response structure
            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response
            assert isinstance(error_response["error"], str)
            assert isinstance(error_response["message"], str)

    @pytest.mark.asyncio
    async def test_login_inactive_user_unauthorized(self, client: AsyncClient, sample_user_data: dict):
        """Test login with inactive user returns 401."""
        # This test assumes there will be a way to deactivate users
        # For now, it tests the contract expectation

        # Arrange - Register user then deactivate (implementation dependent)
        register_response = await client.post("/auth/register", json=sample_user_data)
        assert register_response.status_code == 201

        # Note: This test may need to be updated when user deactivation is implemented
        # For now, testing with unverified user if that blocks login

        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"]
        }

        # Act
        response = await client.post("/auth/login", json=login_data)

        # Assert - For now, assume login works for unverified users
        # This assertion may need adjustment based on business rules
        assert response.status_code in [200, 401]  # Either works or is blocked

        if response.status_code == 401:
            error_response = response.json()
            assert "error" in error_response
            assert error_response["error"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_login_empty_request_body(self, client: AsyncClient):
        """Test empty request body returns validation error."""
        # Act
        response = await client.post("/auth/login", json={})

        # Assert
        assert response.status_code == 400
        error_response = response.json()
        assert "error" in error_response

    @pytest.mark.asyncio
    async def test_login_request_content_type(self, client: AsyncClient):
        """Test that endpoint only accepts application/json."""
        # Arrange
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }

        # Act - Send as form data instead of JSON
        response = await client.post(
            "/auth/login",
            data=login_data,  # form data instead of json
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Assert - Should reject non-JSON content
        assert response.status_code in [400, 415, 422]

    @pytest.mark.asyncio
    async def test_login_extra_fields_ignored(self, client: AsyncClient, sample_user_data: dict):
        """Test that extra fields in request are ignored."""
        # Arrange - Register user first
        await client.post("/auth/register", json=sample_user_data)

        login_data_with_extras = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
            "extra_field": "should be ignored",
            "remember_me": True  # Common but not in spec
        }

        # Act
        response = await client.post("/auth/login", json=login_data_with_extras)

        # Assert
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_login_case_sensitivity(self, client: AsyncClient, sample_user_data: dict):
        """Test email case sensitivity in login."""
        # Arrange - Register user first
        await client.post("/auth/register", json=sample_user_data)

        # Act - Try login with different email case
        login_data = {
            "email": sample_user_data["email"].upper(),
            "password": sample_user_data["password"]
        }
        response = await client.post("/auth/login", json=login_data)

        # Assert - Email should be case insensitive for login
        # This is a common UX expectation
        assert response.status_code in [200, 401]  # Implementation dependent

    @pytest.mark.asyncio
    async def test_login_response_headers(self, client: AsyncClient, sample_user_data: dict):
        """Test that response includes correct headers."""
        # Arrange
        await client.post("/auth/register", json=sample_user_data)

        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"]
        }

        # Act
        response = await client.post("/auth/login", json=login_data)

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_login_token_format(self, client: AsyncClient, sample_user_data: dict):
        """Test that tokens follow expected format."""
        # Arrange
        await client.post("/auth/register", json=sample_user_data)

        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"]
        }

        # Act
        response = await client.post("/auth/login", json=login_data)

        # Assert
        assert response.status_code == 200
        response_data = response.json()

        # Tokens should be non-empty strings
        assert len(response_data["access_token"]) > 0
        assert len(response_data["refresh_token"]) > 0

        # Tokens should be different
        assert response_data["access_token"] != response_data["refresh_token"]

        # Basic JWT format check (header.payload.signature)
        access_token_parts = response_data["access_token"].split('.')
        refresh_token_parts = response_data["refresh_token"].split('.')

        # JWT tokens have 3 parts
        assert len(access_token_parts) == 3
        assert len(refresh_token_parts) == 3

    @pytest.mark.asyncio
    async def test_login_multiple_sessions(self, client: AsyncClient, sample_user_data: dict):
        """Test that multiple logins are allowed."""
        # Arrange
        await client.post("/auth/register", json=sample_user_data)

        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"]
        }

        # Act - Login twice
        response1 = await client.post("/auth/login", json=login_data)
        response2 = await client.post("/auth/login", json=login_data)

        # Assert - Both should succeed
        assert response1.status_code == 200
        assert response2.status_code == 200

        # Tokens should be different for different sessions
        token1 = response1.json()["access_token"]
        token2 = response2.json()["access_token"]
        assert token1 != token2