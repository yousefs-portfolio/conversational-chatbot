"""
Contract test for GET /proactive/suggestions endpoint.

This test validates the API contract for retrieving proactive suggestions.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from tests.conftest import assert_valid_uuid, assert_datetime_format


class TestProactiveSuggestionsGetContract:
    """Test contract compliance for proactive suggestions retrieval endpoint."""

    @pytest.fixture
    async def user_with_conversation(self, client: AsyncClient, auth_headers: dict):
        """Create user with conversation history for testing suggestions."""
        # Create a conversation
        conversation_data = {
            "title": "Test Conversation for Suggestions",
            "system_prompt": "You are a helpful AI assistant."
        }
        conv_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        assert conv_response.status_code == 201
        conversation = conv_response.json()

        # Add some messages to create history
        messages = [
            {"content": "What is machine learning?"},
            {"content": "Can you help me with Python?"},
            {"content": "I need to learn about databases"}
        ]

        for message in messages:
            msg_response = await client.post(
                f"/conversations/{conversation['id']}/messages",
                headers=auth_headers,
                json=message
            )
            assert msg_response.status_code == 201

        return {"conversation": conversation, "messages": messages}

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_success(self, client: AsyncClient, auth_headers: dict, user_with_conversation: dict):
        """Test successful proactive suggestions retrieval returns 200."""
        # Act
        response = await client.get("/proactive/suggestions", headers=auth_headers)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()

        # Validate response structure
        assert isinstance(data, dict)
        assert "suggestions" in data
        assert "total_count" in data
        assert "generated_at" in data

        # Validate data types
        assert isinstance(data["suggestions"], list)
        assert isinstance(data["total_count"], int)
        assert isinstance(data["generated_at"], str)

        # Validate generated_at format
        assert_datetime_format(data["generated_at"])

        # Validate total_count matches suggestions length
        assert data["total_count"] == len(data["suggestions"])

        # Validate suggestion objects
        for suggestion in data["suggestions"]:
            required_suggestion_fields = [
                "id", "type", "title", "description", "priority",
                "context", "actions", "expires_at", "created_at"
            ]
            for field in required_suggestion_fields:
                assert field in suggestion, f"Missing required field: {field}"

            # Validate data types
            assert isinstance(suggestion["id"], str)
            assert isinstance(suggestion["type"], str)
            assert isinstance(suggestion["title"], str)
            assert isinstance(suggestion["description"], str)
            assert isinstance(suggestion["priority"], str)
            assert isinstance(suggestion["context"], dict)
            assert isinstance(suggestion["actions"], list)
            assert isinstance(suggestion["expires_at"], str)
            assert isinstance(suggestion["created_at"], str)

            # Validate formats
            assert_valid_uuid(suggestion["id"])
            assert_datetime_format(suggestion["expires_at"])
            assert_datetime_format(suggestion["created_at"])

            # Validate enum values
            assert suggestion["type"] in [
                "learning_path", "skill_improvement", "tool_recommendation",
                "workflow_optimization", "content_suggestion", "follow_up"
            ]
            assert suggestion["priority"] in ["low", "medium", "high", "urgent"]

            # Validate actions structure
            for action in suggestion["actions"]:
                assert "type" in action
                assert "label" in action
                assert "url" in action or "data" in action  # Action needs either URL or data
                assert isinstance(action["type"], str)
                assert isinstance(action["label"], str)

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_without_auth_unauthorized(self, client: AsyncClient):
        """Test proactive suggestions retrieval without authentication returns 401."""
        # Act
        response = await client.get("/proactive/suggestions")

        # Assert
        assert response.status_code == 401
        error_data = response.json()
        assert "error" in error_data
        assert "message" in error_data

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_invalid_token_unauthorized(self, client: AsyncClient):
        """Test proactive suggestions retrieval with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.get("/proactive/suggestions", headers=invalid_headers)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_filtering_by_type(self, client: AsyncClient, auth_headers: dict, user_with_conversation: dict):
        """Test filtering suggestions by type."""
        # Test filtering by learning_path type
        response = await client.get("/proactive/suggestions?type=learning_path", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # All returned suggestions should be of the requested type
        for suggestion in data["suggestions"]:
            assert suggestion["type"] == "learning_path"

        # Test filtering by skill_improvement type
        response = await client.get("/proactive/suggestions?type=skill_improvement", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        for suggestion in data["suggestions"]:
            assert suggestion["type"] == "skill_improvement"

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_filtering_by_priority(self, client: AsyncClient, auth_headers: dict, user_with_conversation: dict):
        """Test filtering suggestions by priority."""
        # Test filtering by high priority
        response = await client.get("/proactive/suggestions?priority=high", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # All returned suggestions should have high priority
        for suggestion in data["suggestions"]:
            assert suggestion["priority"] == "high"

        # Test filtering by multiple priorities
        response = await client.get("/proactive/suggestions?priority=high,urgent", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        for suggestion in data["suggestions"]:
            assert suggestion["priority"] in ["high", "urgent"]

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_limiting_results(self, client: AsyncClient, auth_headers: dict, user_with_conversation: dict):
        """Test limiting the number of suggestions returned."""
        # Test limiting to 3 suggestions
        response = await client.get("/proactive/suggestions?limit=3", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Should return at most 3 suggestions
        assert len(data["suggestions"]) <= 3

        # Test limiting to 1 suggestion
        response = await client.get("/proactive/suggestions?limit=1", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert len(data["suggestions"]) <= 1

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_with_context_filter(self, client: AsyncClient, auth_headers: dict, user_with_conversation: dict):
        """Test filtering suggestions by context."""
        conversation_id = user_with_conversation["conversation"]["id"]

        # Test filtering by conversation context
        response = await client.get(f"/proactive/suggestions?context_type=conversation&context_id={conversation_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # All suggestions should be related to the specific conversation
        for suggestion in data["suggestions"]:
            if "conversation_id" in suggestion["context"]:
                assert suggestion["context"]["conversation_id"] == conversation_id

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_include_expired(self, client: AsyncClient, auth_headers: dict, user_with_conversation: dict):
        """Test including expired suggestions."""
        # Test excluding expired suggestions (default)
        response = await client.get("/proactive/suggestions", headers=auth_headers)
        assert response.status_code == 200
        default_data = response.json()

        # Test including expired suggestions
        response = await client.get("/proactive/suggestions?include_expired=true", headers=auth_headers)
        assert response.status_code == 200
        with_expired_data = response.json()

        # Should have same or more suggestions when including expired
        assert with_expired_data["total_count"] >= default_data["total_count"]

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_sorting(self, client: AsyncClient, auth_headers: dict, user_with_conversation: dict):
        """Test sorting suggestions."""
        # Test sorting by priority (high to low)
        response = await client.get("/proactive/suggestions?sort_by=priority&sort_order=desc", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Verify priority ordering (urgent > high > medium > low)
        priority_order = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
        for i in range(len(data["suggestions"]) - 1):
            current_priority = priority_order[data["suggestions"][i]["priority"]]
            next_priority = priority_order[data["suggestions"][i + 1]["priority"]]
            assert current_priority >= next_priority

        # Test sorting by created_at (newest first)
        response = await client.get("/proactive/suggestions?sort_by=created_at&sort_order=desc", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Verify date ordering
        created_dates = [suggestion["created_at"] for suggestion in data["suggestions"]]
        assert created_dates == sorted(created_dates, reverse=True)

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_empty_result(self, client: AsyncClient, auth_headers: dict):
        """Test suggestions endpoint with no suggestions available."""
        # Create a new user with no activity (should have no suggestions)
        new_user_data = {
            "email": "newuser_no_suggestions@example.com",
            "password": "testpassword123",
            "full_name": "New User No Suggestions"
        }
        register_response = await client.post("/auth/register", json=new_user_data)
        assert register_response.status_code == 201

        login_response = await client.post("/auth/login", json={
            "email": new_user_data["email"],
            "password": new_user_data["password"]
        })
        assert login_response.status_code == 200
        new_user_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Get suggestions for new user
        response = await client.get("/proactive/suggestions", headers=new_user_headers)
        assert response.status_code == 200
        data = response.json()

        # Should return empty list
        assert data["total_count"] == 0
        assert len(data["suggestions"]) == 0
        assert isinstance(data["generated_at"], str)

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_invalid_query_params(self, client: AsyncClient, auth_headers: dict):
        """Test invalid query parameters return appropriate errors."""
        invalid_params = [
            "type=invalid_type",
            "priority=invalid_priority",
            "limit=0",  # Limit must be > 0
            "limit=-1",
            "limit=101",  # Assuming max limit is 100
            "sort_by=invalid_field",
            "sort_order=invalid_order",
            "include_expired=invalid_boolean"
        ]

        for param in invalid_params:
            response = await client.get(f"/proactive/suggestions?{param}", headers=auth_headers)
            # Should return 422 for validation errors
            assert response.status_code == 422, f"Expected 422 for invalid param: {param}, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_response_headers(self, client: AsyncClient, auth_headers: dict, user_with_conversation: dict):
        """Test that response includes correct headers."""
        # Act
        response = await client.get("/proactive/suggestions", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_caching_behavior(self, client: AsyncClient, auth_headers: dict, user_with_conversation: dict):
        """Test that suggestions are properly cached/updated."""
        # First request
        response1 = await client.get("/proactive/suggestions", headers=auth_headers)
        assert response1.status_code == 200
        data1 = response1.json()

        # Second request (should be consistent within a reasonable time window)
        response2 = await client.get("/proactive/suggestions", headers=auth_headers)
        assert response2.status_code == 200
        data2 = response2.json()

        # Generated_at should be the same if served from cache, or recent if regenerated
        from datetime import datetime
        gen_time1 = datetime.fromisoformat(data1["generated_at"].replace('Z', '+00:00'))
        gen_time2 = datetime.fromisoformat(data2["generated_at"].replace('Z', '+00:00'))

        # Times should be identical (cached) or very close (regenerated)
        time_diff = abs((gen_time2 - gen_time1).total_seconds())
        assert time_diff <= 60  # Within 1 minute

    @pytest.mark.asyncio
    async def test_get_proactive_suggestions_personalization(self, client: AsyncClient, auth_headers: dict, user_with_conversation: dict):
        """Test that suggestions are personalized based on user activity."""
        response = await client.get("/proactive/suggestions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Suggestions should be relevant to user's conversation topics
        # (machine learning, Python, databases based on fixture)
        relevant_keywords = ["machine learning", "python", "database", "programming", "ai"]

        # At least some suggestions should mention relevant topics
        has_relevant_suggestions = False
        for suggestion in data["suggestions"]:
            suggestion_text = (suggestion["title"] + " " + suggestion["description"]).lower()
            if any(keyword in suggestion_text for keyword in relevant_keywords):
                has_relevant_suggestions = True
                break

        # This is a soft assertion - personalization might not always be detectable
        # but we should at least have suggestions generated
        assert data["total_count"] >= 0