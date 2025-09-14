"""
Contract test for POST /auth/logout endpoint.

This test validates the API contract for user logout.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient


class TestAuthLogoutContract:
    """Test contract compliance for user logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient, auth_headers: dict):
        """Test successful logout returns 200."""
        # Act
        response = await client.post("/auth/logout", headers=auth_headers)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_logout_without_auth_unauthorized(self, client: AsyncClient):
        """Test logout without authentication returns 401."""
        response = await client.post("/auth/logout")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_invalid_token_unauthorized(self, client: AsyncClient):
        """Test logout with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.post("/auth/logout", headers=invalid_headers)
        assert response.status_code == 401