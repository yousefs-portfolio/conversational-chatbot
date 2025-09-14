"""
Contract test for PUT /preferences endpoint.

This test validates the API contract for updating user preferences.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient


class TestPreferencesUpdateContract:
    """Test contract compliance for user preferences update endpoint."""

    @pytest.fixture
    def valid_preferences_update(self):
        """Valid preferences update data."""
        return {
            "general": {
                "language": "en",
                "timezone": "America/New_York",
                "date_format": "MM/DD/YYYY"
            },
            "chat": {
                "max_context_length": 8000,
                "auto_save": True,
                "show_timestamps": False
            },
            "ai_model": {
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2000
            }
        }

    @pytest.fixture
    def partial_preferences_update(self):
        """Partial preferences update data."""
        return {
            "interface": {
                "theme": "dark",
                "font_size": "medium"
            }
        }

    @pytest.fixture
    def single_preference_update(self):
        """Single preference update."""
        return {
            "notifications": {
                "enabled": False
            }
        }

    @pytest.mark.asyncio
    async def test_update_preferences_success(self, client: AsyncClient, auth_headers: dict,
                                             valid_preferences_update: dict):
        """Test successful preferences update returns 200."""
        # Act
        response = await client.put("/preferences", headers=auth_headers, json=valid_preferences_update)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_update_preferences_response_format(self, client: AsyncClient, auth_headers: dict,
                                                     valid_preferences_update: dict):
        """Test preferences update response has correct format."""
        response = await client.put("/preferences", headers=auth_headers, json=valid_preferences_update)

        assert response.status_code == 200
        data = response.json()

        # Response should include updated preferences
        assert isinstance(data, dict)

        # Validate that submitted preferences are reflected in response
        for category, settings in valid_preferences_update.items():
            if category in data:
                assert isinstance(data[category], dict)
                for setting, value in settings.items():
                    if setting in data[category]:
                        assert data[category][setting] == value

    @pytest.mark.asyncio
    async def test_update_preferences_partial_update(self, client: AsyncClient, auth_headers: dict,
                                                    partial_preferences_update: dict):
        """Test partial preferences update."""
        response = await client.put("/preferences", headers=auth_headers, json=partial_preferences_update)

        assert response.status_code == 200
        data = response.json()

        # Only specified preferences should be updated, others should remain unchanged
        for category, settings in partial_preferences_update.items():
            assert category in data
            for setting, value in settings.items():
                assert data[category][setting] == value

    @pytest.mark.asyncio
    async def test_update_single_preference(self, client: AsyncClient, auth_headers: dict,
                                          single_preference_update: dict):
        """Test updating a single preference."""
        response = await client.put("/preferences", headers=auth_headers, json=single_preference_update)

        assert response.status_code == 200
        data = response.json()

        # Single preference should be updated
        category = list(single_preference_update.keys())[0]
        assert category in data
        for setting, value in single_preference_update[category].items():
            assert data[category][setting] == value

    @pytest.mark.asyncio
    async def test_update_preferences_without_auth_unauthorized(self, client: AsyncClient,
                                                               valid_preferences_update: dict):
        """Test preferences update without authentication returns 401."""
        response = await client.put("/preferences", json=valid_preferences_update)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_preferences_invalid_token_unauthorized(self, client: AsyncClient,
                                                                valid_preferences_update: dict):
        """Test preferences update with invalid token returns 401."""
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await client.put("/preferences", headers=invalid_headers, json=valid_preferences_update)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_preferences_validation_errors(self, client: AsyncClient, auth_headers: dict):
        """Test preferences update with various validation errors."""
        # Test invalid temperature value
        invalid_data = {
            "ai_model": {
                "temperature": 3.0  # Should be between 0.0 and 2.0
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test invalid language code
        invalid_data = {
            "general": {
                "language": "invalid_lang"  # Should be valid ISO code
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test invalid timezone
        invalid_data = {
            "general": {
                "timezone": "Invalid/Timezone"
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_preferences_ai_model_validation(self, client: AsyncClient, auth_headers: dict):
        """Test AI model preferences validation."""
        # Test invalid provider
        invalid_data = {
            "ai_model": {
                "provider": "invalid_provider"
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test invalid model for provider
        invalid_data = {
            "ai_model": {
                "provider": "openai",
                "model": "non_existent_model"
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test negative max_tokens
        invalid_data = {
            "ai_model": {
                "max_tokens": -100
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_preferences_empty_update(self, client: AsyncClient, auth_headers: dict):
        """Test preferences update with empty data."""
        response = await client.put("/preferences", headers=auth_headers, json={})

        # Empty update should succeed (no changes)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_preferences_invalid_category(self, client: AsyncClient, auth_headers: dict):
        """Test preferences update with invalid category."""
        invalid_data = {
            "invalid_category": {
                "some_setting": "some_value"
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_preferences_invalid_setting(self, client: AsyncClient, auth_headers: dict):
        """Test preferences update with invalid setting."""
        invalid_data = {
            "general": {
                "invalid_setting": "some_value"
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_preferences_type_validation(self, client: AsyncClient, auth_headers: dict):
        """Test preferences update with wrong data types."""
        # Test boolean setting with string value
        invalid_data = {
            "notifications": {
                "enabled": "true"  # Should be boolean
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test integer setting with string value
        invalid_data = {
            "chat": {
                "max_context_length": "4000"  # Should be integer
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_preferences_range_validation(self, client: AsyncClient, auth_headers: dict):
        """Test preferences update with values outside valid ranges."""
        # Test context length too large
        invalid_data = {
            "chat": {
                "max_context_length": 1000000  # Assuming max is lower
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

        # Test negative data retention days
        invalid_data = {
            "privacy": {
                "data_retention_days": -1
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_preferences_cascading_validation(self, client: AsyncClient, auth_headers: dict):
        """Test preferences update with cascading validation rules."""
        # Some preferences might depend on others
        # For example, certain models might only be available for specific providers
        invalid_data = {
            "ai_model": {
                "provider": "anthropic",
                "model": "gpt-4"  # GPT-4 is not an Anthropic model
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=invalid_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_preferences_preserves_other_settings(self, client: AsyncClient, auth_headers: dict):
        """Test that preferences update preserves unmodified settings."""
        # First, set some initial preferences
        initial_data = {
            "general": {
                "language": "en",
                "timezone": "UTC"
            },
            "chat": {
                "max_context_length": 4000
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=initial_data)
        assert response.status_code == 200

        # Then, update only one category
        update_data = {
            "interface": {
                "theme": "dark"
            }
        }
        response = await client.put("/preferences", headers=auth_headers, json=update_data)
        assert response.status_code == 200

        # Verify the response includes both old and new preferences
        data = response.json()
        assert "interface" in data
        assert data["interface"]["theme"] == "dark"

        # Original preferences should still be present
        if "general" in data:
            assert data["general"]["language"] == "en"
        if "chat" in data:
            assert data["chat"]["max_context_length"] == 4000

    @pytest.mark.asyncio
    async def test_update_preferences_returns_full_preferences(self, client: AsyncClient, auth_headers: dict,
                                                              valid_preferences_update: dict):
        """Test that preferences update returns complete user preferences."""
        response = await client.put("/preferences", headers=auth_headers, json=valid_preferences_update)

        assert response.status_code == 200
        data = response.json()

        # Response should include all user preferences, not just updated ones
        assert isinstance(data, dict)
        assert len(data) > 0

        # All updated preferences should be reflected
        for category, settings in valid_preferences_update.items():
            if category in data:
                for setting, value in settings.items():
                    if setting in data[category]:
                        assert data[category][setting] == value