"""
Contract test for POST /proactive/suggestions/{suggestion_id}/respond endpoint.

This test validates the API contract for responding to proactive suggestions.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from tests.conftest import assert_valid_uuid, assert_datetime_format


class TestProactiveRespondPostContract:
    """Test contract compliance for responding to proactive suggestions endpoint."""

    @pytest.fixture
    async def user_with_suggestions(self, client: AsyncClient, auth_headers: dict):
        """Create user with conversation history and get suggestions for testing responses."""
        # Create conversation and messages to generate suggestions
        conversation_data = {
            "title": "Test Conversation for Suggestion Response",
            "system_prompt": "You are a helpful AI assistant."
        }
        conv_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        assert conv_response.status_code == 201
        conversation = conv_response.json()

        # Add messages to create history
        messages = [
            {"content": "I want to learn Python programming"},
            {"content": "What are the best practices for web development?"},
            {"content": "Can you recommend some machine learning resources?"}
        ]

        for message in messages:
            msg_response = await client.post(
                f"/conversations/{conversation['id']}/messages",
                headers=auth_headers,
                json=message
            )
            assert msg_response.status_code == 201

        # Get suggestions
        suggestions_response = await client.get("/proactive/suggestions", headers=auth_headers)
        assert suggestions_response.status_code == 200
        suggestions_data = suggestions_response.json()

        # Return first suggestion for testing
        suggestion = suggestions_data["suggestions"][0] if suggestions_data["suggestions"] else None
        return {"conversation": conversation, "suggestion": suggestion}

    @pytest.fixture
    def accept_response_data(self):
        """Valid accept response data."""
        return {
            "action": "accept",
            "feedback": "This suggestion is helpful and relevant to my learning goals."
        }

    @pytest.fixture
    def dismiss_response_data(self):
        """Valid dismiss response data."""
        return {
            "action": "dismiss",
            "reason": "not_relevant",
            "feedback": "I'm not interested in this topic right now."
        }

    @pytest.fixture
    def postpone_response_data(self):
        """Valid postpone response data."""
        return {
            "action": "postpone",
            "postpone_until": "2024-12-31T23:59:59Z",
            "feedback": "I'll look into this later when I have more time."
        }

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_accept_success(self, client: AsyncClient, auth_headers: dict, user_with_suggestions: dict, accept_response_data: dict):
        """Test successfully accepting a proactive suggestion returns 200."""
        # Skip if no suggestions available
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        # Act
        response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=auth_headers,
            json=accept_response_data
        )

        # Assert - This MUST FAIL initially
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()

        # Validate response structure
        required_fields = [
            "suggestion_id", "action", "status", "responded_at",
            "feedback_recorded", "next_actions"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Validate data values
        assert data["suggestion_id"] == suggestion["id"]
        assert data["action"] == "accept"
        assert data["status"] == "accepted"
        assert data["feedback_recorded"] is True

        # Validate data types
        assert isinstance(data["suggestion_id"], str)
        assert isinstance(data["action"], str)
        assert isinstance(data["status"], str)
        assert isinstance(data["responded_at"], str)
        assert isinstance(data["feedback_recorded"], bool)
        assert isinstance(data["next_actions"], list)

        # Validate formats
        assert_valid_uuid(data["suggestion_id"])
        assert_datetime_format(data["responded_at"])

        # Validate next_actions structure
        for action in data["next_actions"]:
            assert "type" in action
            assert "description" in action
            assert isinstance(action["type"], str)
            assert isinstance(action["description"], str)

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_dismiss_success(self, client: AsyncClient, auth_headers: dict, user_with_suggestions: dict, dismiss_response_data: dict):
        """Test successfully dismissing a proactive suggestion returns 200."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        # Act
        response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=auth_headers,
            json=dismiss_response_data
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Validate response values for dismiss action
        assert data["action"] == "dismiss"
        assert data["status"] == "dismissed"
        assert "reason" in data
        assert data["reason"] == dismiss_response_data["reason"]

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_postpone_success(self, client: AsyncClient, auth_headers: dict, user_with_suggestions: dict, postpone_response_data: dict):
        """Test successfully postponing a proactive suggestion returns 200."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        # Act
        response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=auth_headers,
            json=postpone_response_data
        )

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Validate response values for postpone action
        assert data["action"] == "postpone"
        assert data["status"] == "postponed"
        assert "postpone_until" in data
        assert data["postpone_until"] == postpone_response_data["postpone_until"]

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_without_auth_unauthorized(self, client: AsyncClient, user_with_suggestions: dict, accept_response_data: dict):
        """Test responding to suggestion without authentication returns 401."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        # Act
        response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            json=accept_response_data
        )

        # Assert
        assert response.status_code == 401
        error_data = response.json()
        assert "error" in error_data
        assert "message" in error_data

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_invalid_token_unauthorized(self, client: AsyncClient, user_with_suggestions: dict, accept_response_data: dict):
        """Test responding to suggestion with invalid token returns 401."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=invalid_headers,
            json=accept_response_data
        )

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_nonexistent_not_found(self, client: AsyncClient, auth_headers: dict, accept_response_data: dict):
        """Test responding to non-existent suggestion returns 404."""
        # Arrange
        fake_suggestion_id = "123e4567-e89b-12d3-a456-426614174000"

        # Act
        response = await client.post(
            f"/proactive/suggestions/{fake_suggestion_id}/respond",
            headers=auth_headers,
            json=accept_response_data
        )

        # Assert
        assert response.status_code == 404
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response
        assert error_response["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_invalid_uuid_format(self, client: AsyncClient, auth_headers: dict, accept_response_data: dict):
        """Test responding with invalid suggestion UUID format returns 422."""
        invalid_ids = [
            "invalid-uuid",
            "123",
            "not-a-uuid-at-all"
        ]

        for invalid_id in invalid_ids:
            # Act
            response = await client.post(
                f"/proactive/suggestions/{invalid_id}/respond",
                headers=auth_headers,
                json=accept_response_data
            )

            # Assert
            assert response.status_code == 422, f"Expected 422 for invalid UUID: {invalid_id}, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_validation_errors(self, client: AsyncClient, auth_headers: dict, user_with_suggestions: dict):
        """Test validation error responses for invalid response data."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        validation_test_cases = [
            # Missing required fields
            {
                "data": {"feedback": "Missing action"},
                "description": "missing action"
            },
            {
                "data": {},
                "description": "empty request body"
            },
            # Invalid action values
            {
                "data": {"action": "invalid_action"},
                "description": "invalid action value"
            },
            {
                "data": {"action": 123},
                "description": "invalid action type"
            },
            # Invalid reason for dismiss
            {
                "data": {"action": "dismiss", "reason": "invalid_reason"},
                "description": "invalid dismiss reason"
            },
            # Missing postpone_until for postpone action
            {
                "data": {"action": "postpone"},
                "description": "missing postpone_until for postpone action"
            },
            # Invalid postpone_until format
            {
                "data": {
                    "action": "postpone",
                    "postpone_until": "invalid-date"
                },
                "description": "invalid postpone_until format"
            },
            # Past date for postpone_until
            {
                "data": {
                    "action": "postpone",
                    "postpone_until": "2020-01-01T00:00:00Z"
                },
                "description": "past date for postpone_until"
            },
            # Invalid data types
            {
                "data": {
                    "action": "accept",
                    "feedback": 123
                },
                "description": "invalid feedback type"
            }
        ]

        for test_case in validation_test_cases:
            # Act
            response = await client.post(
                f"/proactive/suggestions/{suggestion['id']}/respond",
                headers=auth_headers,
                json=test_case["data"]
            )

            # Assert
            assert response.status_code == 422, f"Expected 422 for {test_case['description']}, got {response.status_code}"

            # Validate error response structure
            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_already_responded_conflict(self, client: AsyncClient, auth_headers: dict, user_with_suggestions: dict, accept_response_data: dict):
        """Test responding to already responded suggestion returns 409 conflict."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        # First response
        first_response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=auth_headers,
            json=accept_response_data
        )
        assert first_response.status_code == 200

        # Second response to same suggestion
        second_response_data = {
            "action": "dismiss",
            "reason": "not_relevant"
        }
        second_response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=auth_headers,
            json=second_response_data
        )

        # Assert
        assert second_response.status_code == 409
        error_response = second_response.json()
        assert "error" in error_response
        assert error_response["error"] == "conflict"

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_expired(self, client: AsyncClient, auth_headers: dict, user_with_suggestions: dict, accept_response_data: dict):
        """Test responding to expired suggestion returns 410 Gone."""
        # This test assumes we can find or create an expired suggestion
        # For now, we'll create a suggestion that would be expired
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        # For an expired suggestion, we expect 410 Gone
        # This test might need modification based on how expiration is handled
        response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=auth_headers,
            json=accept_response_data
        )

        # If the suggestion is not expired, this should succeed
        # If it is expired, it should return 410
        if response.status_code == 410:
            error_response = response.json()
            assert "error" in error_response
            assert "expired" in error_response["message"].lower()
        else:
            # If not expired, should succeed
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_forbidden_access(self, client: AsyncClient, user_with_suggestions: dict, accept_response_data: dict):
        """Test responding to suggestion by different user returns 403."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        # Create different user
        other_user_data = {
            "email": "other_user_respond@example.com",
            "password": "testpassword123",
            "full_name": "Other User"
        }
        register_response = await client.post("/auth/register", json=other_user_data)
        assert register_response.status_code == 201

        login_response = await client.post("/auth/login", json={
            "email": other_user_data["email"],
            "password": other_user_data["password"]
        })
        assert login_response.status_code == 200
        other_user_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Try to respond to suggestion as different user
        response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=other_user_headers,
            json=accept_response_data
        )

        # Assert - Should be forbidden
        assert response.status_code == 403
        error_response = response.json()
        assert "error" in error_response
        assert error_response["error"] == "forbidden"

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_reason_values(self, client: AsyncClient, auth_headers: dict, user_with_suggestions: dict):
        """Test valid dismiss reason values."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        valid_reasons = [
            "not_relevant", "already_know", "too_advanced", "too_basic",
            "not_interested", "timing_not_right", "prefer_different_approach"
        ]

        for reason in valid_reasons:
            # Create new suggestion for each test (or use different endpoint)
            dismiss_data = {
                "action": "dismiss",
                "reason": reason,
                "feedback": f"Testing dismiss with reason: {reason}"
            }

            # Note: This might fail if we can only respond once per suggestion
            # In real implementation, might need multiple suggestions or reset capability
            response = await client.post(
                f"/proactive/suggestions/{suggestion['id']}/respond",
                headers=auth_headers,
                json=dismiss_data
            )

            # Should succeed for first valid reason, then conflict for subsequent ones
            assert response.status_code in [200, 409], f"Unexpected status for reason {reason}: {response.status_code}"

            if response.status_code == 200:
                data = response.json()
                assert data["reason"] == reason
                break  # Only test first successful response to avoid conflicts

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_with_metadata(self, client: AsyncClient, auth_headers: dict, user_with_suggestions: dict):
        """Test responding with additional metadata."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        response_data = {
            "action": "accept",
            "feedback": "This is very helpful!",
            "metadata": {
                "rating": 5,
                "usefulness": "high",
                "user_intent": "learning"
            }
        }

        response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=auth_headers,
            json=response_data
        )

        assert response.status_code == 200
        data = response.json()

        # Metadata might be included in response or stored for analytics
        if "metadata" in data:
            assert data["metadata"] == response_data["metadata"]

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_response_headers(self, client: AsyncClient, auth_headers: dict, user_with_suggestions: dict, accept_response_data: dict):
        """Test that response includes correct headers."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        # Act
        response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=auth_headers,
            json=accept_response_data
        )

        # Assert
        if response.status_code == 200:
            assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_respond_to_suggestion_unicode_feedback(self, client: AsyncClient, auth_headers: dict, user_with_suggestions: dict):
        """Test that unicode characters in feedback are handled correctly."""
        suggestion = user_with_suggestions["suggestion"]
        if not suggestion:
            pytest.skip("No suggestions available for testing")

        unicode_response = {
            "action": "accept",
            "feedback": "这个建议很有用! Very helpful suggestion 🌟"
        }

        response = await client.post(
            f"/proactive/suggestions/{suggestion['id']}/respond",
            headers=auth_headers,
            json=unicode_response
        )

        if response.status_code == 200:
            # Unicode should be properly handled
            assert "feedback_recorded" in response.json()
            assert response.json()["feedback_recorded"] is True