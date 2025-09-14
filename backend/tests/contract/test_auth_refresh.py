"""
Contract test for POST /auth/refresh endpoint.

This test validates the API contract for token refresh.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient


class TestAuthRefreshContract:
    """Test contract compliance for token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_success_response_format(self, client: AsyncClient, sample_user_data: dict):
        """Test successful token refresh returns correct response format."""
        # Arrange - Register and login to get refresh token
        await client.post("/auth/register", json=sample_user_data)
        login_response = await client.post("/auth/login", json={
            "email": sample_user_data["email"],
            "password": sample_user_data["password"]
        })
        refresh_token = login_response.json()["refresh_token"]

        refresh_data = {"refresh_token": refresh_token}

        # Act
        response = await client.post("/auth/refresh", json=refresh_data)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200

        # Validate response structure
        response_data = response.json()
        required_fields = ["access_token", "refresh_token", "token_type", "expires_in", "user"]
        for field in required_fields:
            assert field in response_data

        # Validate token_type
        assert response_data["token_type"] == "bearer"

        # New tokens should be different from old ones
        assert response_data["access_token"] != login_response.json()["access_token"]

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_unauthorized(self, client: AsyncClient):
        """Test refresh with invalid token returns 401."""
        invalid_tokens = [
            "invalid-token",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature",
            "",
            None
        ]

        for token in invalid_tokens:
            response = await client.post("/auth/refresh", json={"refresh_token": token})
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_missing_token_validation(self, client: AsyncClient):
        """Test refresh without token returns 400."""
        response = await client.post("/auth/refresh", json={})
        assert response.status_code == 400