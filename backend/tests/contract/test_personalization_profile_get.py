"""
Contract test for GET /personalization/profile endpoint.

This test validates the API contract for retrieving user personalization profile.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from tests.conftest import assert_valid_uuid, assert_datetime_format


class TestPersonalizationProfileGetContract:
    """Test contract compliance for personalization profile retrieval endpoint."""

    @pytest.fixture
    async def user_with_activity(self, client: AsyncClient, auth_headers: dict):
        """Create user with some activity to generate a meaningful profile."""
        # Create conversations
        conversations = []
        for i in range(3):
            conv_data = {
                "title": f"Learning Conversation {i+1}",
                "system_prompt": "You are a helpful AI assistant."
            }
            conv_response = await client.post("/conversations", headers=auth_headers, json=conv_data)
            assert conv_response.status_code == 201
            conversations.append(conv_response.json())

        # Add messages to create user interaction patterns
        topics = [
            ["Python programming", "web development", "Django framework"],
            ["machine learning", "data science", "neural networks"],
            ["cloud computing", "AWS services", "DevOps practices"]
        ]

        for i, conversation in enumerate(conversations):
            for topic in topics[i]:
                message_data = {"content": f"I want to learn about {topic}"}
                msg_response = await client.post(
                    f"/conversations/{conversation['id']}/messages",
                    headers=auth_headers,
                    json=message_data
                )
                assert msg_response.status_code == 201

        return {"conversations": conversations, "topics": topics}

    @pytest.mark.asyncio
    async def test_get_personalization_profile_success(self, client: AsyncClient, auth_headers: dict, user_with_activity: dict):
        """Test successful personalization profile retrieval returns 200."""
        # Act
        response = await client.get("/personalization/profile", headers=auth_headers)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()

        # Validate response structure
        required_fields = [
            "user_id", "interests", "learning_goals", "preferences",
            "interaction_patterns", "skill_level", "topics_of_interest",
            "generated_at", "last_updated"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Validate data types
        assert isinstance(data["user_id"], str)
        assert isinstance(data["interests"], list)
        assert isinstance(data["learning_goals"], list)
        assert isinstance(data["preferences"], dict)
        assert isinstance(data["interaction_patterns"], dict)
        assert isinstance(data["skill_level"], dict)
        assert isinstance(data["topics_of_interest"], list)
        assert isinstance(data["generated_at"], str)
        assert isinstance(data["last_updated"], str)

        # Validate formats
        assert_valid_uuid(data["user_id"])
        assert_datetime_format(data["generated_at"])
        assert_datetime_format(data["last_updated"])

        # Validate interests structure
        for interest in data["interests"]:
            assert isinstance(interest, dict)
            interest_fields = ["topic", "confidence_score", "frequency", "last_engaged"]
            for field in interest_fields:
                assert field in interest, f"Missing field in interest: {field}"
            assert isinstance(interest["topic"], str)
            assert isinstance(interest["confidence_score"], (int, float))
            assert isinstance(interest["frequency"], int)
            assert isinstance(interest["last_engaged"], str)
            assert 0 <= interest["confidence_score"] <= 1
            assert interest["frequency"] > 0
            assert_datetime_format(interest["last_engaged"])

        # Validate learning_goals structure
        for goal in data["learning_goals"]:
            assert isinstance(goal, dict)
            goal_fields = ["goal", "priority", "progress", "estimated_completion"]
            for field in goal_fields:
                assert field in goal, f"Missing field in learning goal: {field}"
            assert isinstance(goal["goal"], str)
            assert isinstance(goal["priority"], str)
            assert isinstance(goal["progress"], (int, float))
            assert goal["priority"] in ["low", "medium", "high"]
            assert 0 <= goal["progress"] <= 1

        # Validate preferences structure
        preference_fields = [
            "content_difficulty", "learning_style", "interaction_frequency",
            "suggestion_types", "content_formats"
        ]
        for field in preference_fields:
            assert field in data["preferences"], f"Missing preference field: {field}"

        # Validate interaction_patterns structure
        pattern_fields = [
            "avg_session_duration", "peak_activity_hours", "common_question_types",
            "response_preferences", "engagement_metrics"
        ]
        for field in pattern_fields:
            assert field in data["interaction_patterns"], f"Missing interaction pattern field: {field}"

        # Validate skill_level structure
        skill_fields = ["overall_level", "domain_levels", "learning_pace"]
        for field in skill_fields:
            assert field in data["skill_level"], f"Missing skill level field: {field}"

        assert data["skill_level"]["overall_level"] in ["beginner", "intermediate", "advanced", "expert"]
        assert isinstance(data["skill_level"]["domain_levels"], dict)
        assert data["skill_level"]["learning_pace"] in ["slow", "moderate", "fast"]

        # Validate topics_of_interest structure
        for topic in data["topics_of_interest"]:
            assert isinstance(topic, dict)
            topic_fields = ["name", "relevance_score", "category"]
            for field in topic_fields:
                assert field in topic, f"Missing field in topic: {field}"
            assert isinstance(topic["name"], str)
            assert isinstance(topic["relevance_score"], (int, float))
            assert isinstance(topic["category"], str)
            assert 0 <= topic["relevance_score"] <= 1

    @pytest.mark.asyncio
    async def test_get_personalization_profile_without_auth_unauthorized(self, client: AsyncClient):
        """Test personalization profile retrieval without authentication returns 401."""
        # Act
        response = await client.get("/personalization/profile")

        # Assert
        assert response.status_code == 401
        error_data = response.json()
        assert "error" in error_data
        assert "message" in error_data

    @pytest.mark.asyncio
    async def test_get_personalization_profile_invalid_token_unauthorized(self, client: AsyncClient):
        """Test personalization profile retrieval with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.get("/personalization/profile", headers=invalid_headers)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_personalization_profile_new_user(self, client: AsyncClient):
        """Test personalization profile for new user with minimal data."""
        # Create new user with no activity
        new_user_data = {
            "email": "newuser_profile@example.com",
            "password": "testpassword123",
            "full_name": "New User Profile"
        }
        register_response = await client.post("/auth/register", json=new_user_data)
        assert register_response.status_code == 201

        login_response = await client.post("/auth/login", json={
            "email": new_user_data["email"],
            "password": new_user_data["password"]
        })
        assert login_response.status_code == 200
        new_user_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Get profile for new user
        response = await client.get("/personalization/profile", headers=new_user_headers)
        assert response.status_code == 200
        data = response.json()

        # New user should have minimal/default profile
        assert len(data["interests"]) == 0 or all(i["confidence_score"] < 0.5 for i in data["interests"])
        assert len(data["learning_goals"]) == 0
        assert data["skill_level"]["overall_level"] in ["beginner", "intermediate"]  # Default levels
        assert len(data["topics_of_interest"]) >= 0  # Could have some default topics

    @pytest.mark.asyncio
    async def test_get_personalization_profile_with_privacy_settings(self, client: AsyncClient, auth_headers: dict, user_with_activity: dict):
        """Test personalization profile respects privacy settings."""
        # Set privacy settings first (assuming there's an endpoint for this)
        # This test validates that sensitive information is filtered based on user privacy preferences

        response = await client.get("/personalization/profile", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Ensure no sensitive personal information is exposed
        sensitive_fields = [
            "email", "password", "personal_details", "location_data",
            "device_info", "ip_address", "browsing_history"
        ]
        for field in sensitive_fields:
            assert field not in data, f"Sensitive field {field} should not be in profile"

    @pytest.mark.asyncio
    async def test_get_personalization_profile_include_recommendations(self, client: AsyncClient, auth_headers: dict, user_with_activity: dict):
        """Test personalization profile with recommendations included."""
        # Test with include_recommendations parameter
        response = await client.get("/personalization/profile?include_recommendations=true", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Should include recommendations section
        assert "recommendations" in data
        assert isinstance(data["recommendations"], dict)

        recommendation_types = [
            "suggested_topics", "learning_paths", "content_recommendations",
            "skill_improvements", "next_steps"
        ]
        for rec_type in recommendation_types:
            if rec_type in data["recommendations"]:
                assert isinstance(data["recommendations"][rec_type], list)

    @pytest.mark.asyncio
    async def test_get_personalization_profile_detailed_view(self, client: AsyncClient, auth_headers: dict, user_with_activity: dict):
        """Test personalization profile with detailed analytics."""
        # Test with detailed parameter
        response = await client.get("/personalization/profile?detail_level=full", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Should include additional detailed analytics
        detailed_fields = [
            "activity_timeline", "engagement_history", "learning_progression",
            "interaction_analytics", "content_consumption_patterns"
        ]

        for field in detailed_fields:
            if field in data:
                assert isinstance(data[field], (dict, list))

    @pytest.mark.asyncio
    async def test_get_personalization_profile_specific_categories(self, client: AsyncClient, auth_headers: dict, user_with_activity: dict):
        """Test filtering personalization profile by specific categories."""
        # Test filtering by technology category
        response = await client.get("/personalization/profile?categories=technology,programming", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Should filter interests and topics to specified categories
        for interest in data["interests"]:
            # Interest should be related to specified categories
            topic_lower = interest["topic"].lower()
            assert any(cat in topic_lower for cat in ["technology", "programming", "python", "web", "development"])

    @pytest.mark.asyncio
    async def test_get_personalization_profile_time_range(self, client: AsyncClient, auth_headers: dict, user_with_activity: dict):
        """Test personalization profile for specific time range."""
        # Test with time range parameters
        response = await client.get(
            "/personalization/profile?from_date=2024-01-01T00:00:00Z&to_date=2024-12-31T23:59:59Z",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Profile should be based on activity within the specified time range
        # All timestamps should be within range (if available)
        for interest in data["interests"]:
            from datetime import datetime
            last_engaged = datetime.fromisoformat(interest["last_engaged"].replace('Z', '+00:00'))
            # Should be within reasonable bounds (this is a basic check)
            assert last_engaged.year >= 2024

    @pytest.mark.asyncio
    async def test_get_personalization_profile_invalid_query_params(self, client: AsyncClient, auth_headers: dict):
        """Test invalid query parameters return appropriate errors."""
        invalid_params = [
            "detail_level=invalid_level",
            "include_recommendations=invalid_boolean",
            "categories=",  # Empty categories
            "from_date=invalid-date",
            "to_date=invalid-date",
            "limit=-1",  # Negative limit
            "limit=0"   # Zero limit
        ]

        for param in invalid_params:
            response = await client.get(f"/personalization/profile?{param}", headers=auth_headers)
            # Should return 422 for validation errors
            assert response.status_code == 422, f"Expected 422 for invalid param: {param}, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_get_personalization_profile_caching_behavior(self, client: AsyncClient, auth_headers: dict, user_with_activity: dict):
        """Test that personalization profile is properly cached."""
        # First request
        response1 = await client.get("/personalization/profile", headers=auth_headers)
        assert response1.status_code == 200
        data1 = response1.json()

        # Second request (should be from cache or recently updated)
        response2 = await client.get("/personalization/profile", headers=auth_headers)
        assert response2.status_code == 200
        data2 = response2.json()

        # Generated_at should be the same or very recent
        from datetime import datetime
        gen_time1 = datetime.fromisoformat(data1["generated_at"].replace('Z', '+00:00'))
        gen_time2 = datetime.fromisoformat(data2["generated_at"].replace('Z', '+00:00'))

        # Times should be identical (cached) or very close (regenerated)
        time_diff = abs((gen_time2 - gen_time1).total_seconds())
        assert time_diff <= 300  # Within 5 minutes

    @pytest.mark.asyncio
    async def test_get_personalization_profile_consistency(self, client: AsyncClient, auth_headers: dict, user_with_activity: dict):
        """Test that personalization profile data is consistent and logical."""
        response = await client.get("/personalization/profile", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Confidence scores should be normalized between 0 and 1
        for interest in data["interests"]:
            assert 0 <= interest["confidence_score"] <= 1
            assert interest["frequency"] >= 0

        # Progress should be between 0 and 1
        for goal in data["learning_goals"]:
            assert 0 <= goal["progress"] <= 1

        # Relevance scores should be between 0 and 1
        for topic in data["topics_of_interest"]:
            assert 0 <= topic["relevance_score"] <= 1

        # Overall skill level should be consistent with domain levels
        overall_level = data["skill_level"]["overall_level"]
        domain_levels = data["skill_level"]["domain_levels"]

        level_values = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}
        overall_value = level_values[overall_level]

        # Overall level should be reasonable compared to domain levels
        if domain_levels:
            domain_values = [level_values.get(level, 1) for level in domain_levels.values()]
            avg_domain_level = sum(domain_values) / len(domain_values)
            # Overall should be within reasonable range of average domain level
            assert abs(overall_value - avg_domain_level) <= 2

    @pytest.mark.asyncio
    async def test_get_personalization_profile_response_headers(self, client: AsyncClient, auth_headers: dict, user_with_activity: dict):
        """Test that response includes correct headers."""
        # Act
        response = await client.get("/personalization/profile", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_personalization_profile_data_freshness(self, client: AsyncClient, auth_headers: dict, user_with_activity: dict):
        """Test that profile data reflects recent activity."""
        # Get current profile
        response = await client.get("/personalization/profile", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Add new conversation activity
        new_conv_data = {
            "title": "Fresh Activity Conversation",
            "system_prompt": "You are a helpful assistant."
        }
        conv_response = await client.post("/conversations", headers=auth_headers, json=new_conv_data)
        assert conv_response.status_code == 201
        new_conversation = conv_response.json()

        # Add message about a new topic
        new_message = {"content": "I want to learn about blockchain technology"}
        msg_response = await client.post(
            f"/conversations/{new_conversation['id']}/messages",
            headers=auth_headers,
            json=new_message
        )
        assert msg_response.status_code == 201

        # Get updated profile (might need to trigger profile regeneration)
        updated_response = await client.get("/personalization/profile?refresh=true", headers=auth_headers)

        # Profile should be updated or marked for update
        if updated_response.status_code == 200:
            updated_data = updated_response.json()
            # last_updated should be more recent
            from datetime import datetime
            original_updated = datetime.fromisoformat(data["last_updated"].replace('Z', '+00:00'))
            new_updated = datetime.fromisoformat(updated_data["last_updated"].replace('Z', '+00:00'))
            assert new_updated >= original_updated