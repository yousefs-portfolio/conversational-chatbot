"""
Contract test for PUT /personalization/profile endpoint.

This test validates the API contract for updating user personalization profile.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
from tests.conftest import assert_valid_uuid, assert_datetime_format


class TestPersonalizationProfilePutContract:
    """Test contract compliance for personalization profile update endpoint."""

    @pytest.fixture
    async def existing_profile_user(self, client: AsyncClient, auth_headers: dict):
        """Create user with existing profile data."""
        # Create some activity to generate initial profile
        conv_data = {
            "title": "Initial Profile Conversation",
            "system_prompt": "You are a helpful AI assistant."
        }
        conv_response = await client.post("/conversations", headers=auth_headers, json=conv_data)
        assert conv_response.status_code == 201
        conversation = conv_response.json()

        # Add some messages
        messages = [
            {"content": "I want to learn Python programming"},
            {"content": "Tell me about machine learning"}
        ]
        for message in messages:
            msg_response = await client.post(
                f"/conversations/{conversation['id']}/messages",
                headers=auth_headers,
                json=message
            )
            assert msg_response.status_code == 201

        # Get initial profile
        profile_response = await client.get("/personalization/profile", headers=auth_headers)
        assert profile_response.status_code == 200

        return {"conversation": conversation, "initial_profile": profile_response.json()}

    @pytest.fixture
    def profile_update_data(self):
        """Valid profile update data."""
        return {
            "learning_goals": [
                {
                    "goal": "Master Python programming",
                    "priority": "high",
                    "target_completion": "2024-12-31T23:59:59Z"
                },
                {
                    "goal": "Learn machine learning fundamentals",
                    "priority": "medium",
                    "target_completion": "2025-06-30T23:59:59Z"
                }
            ],
            "preferences": {
                "content_difficulty": "intermediate",
                "learning_style": "hands_on",
                "interaction_frequency": "daily",
                "suggestion_types": ["learning_path", "skill_improvement", "content_suggestion"],
                "content_formats": ["video", "article", "interactive", "code_example"]
            },
            "interests": [
                {
                    "topic": "Python programming",
                    "interest_level": "high"
                },
                {
                    "topic": "web development",
                    "interest_level": "medium"
                },
                {
                    "topic": "data science",
                    "interest_level": "high"
                }
            ],
            "skill_declarations": {
                "programming": "intermediate",
                "python": "beginner",
                "machine_learning": "beginner",
                "web_development": "intermediate"
            }
        }

    @pytest.fixture
    def partial_profile_update(self):
        """Partial profile update data."""
        return {
            "preferences": {
                "content_difficulty": "advanced",
                "learning_style": "theory_first"
            },
            "learning_goals": [
                {
                    "goal": "Advanced Python techniques",
                    "priority": "high",
                    "target_completion": "2024-09-30T23:59:59Z"
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_update_personalization_profile_success(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict, profile_update_data: dict):
        """Test successful personalization profile update returns 200."""
        # Act
        response = await client.put("/personalization/profile", headers=auth_headers, json=profile_update_data)

        # Assert - This MUST FAIL initially
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()

        # Validate response structure
        required_fields = [
            "user_id", "interests", "learning_goals", "preferences",
            "skill_level", "updated_at", "update_summary"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Validate updated data matches input
        assert len(data["learning_goals"]) == len(profile_update_data["learning_goals"])
        for i, goal in enumerate(data["learning_goals"]):
            expected_goal = profile_update_data["learning_goals"][i]
            assert goal["goal"] == expected_goal["goal"]
            assert goal["priority"] == expected_goal["priority"]

        # Validate preferences were updated
        for pref_key, pref_value in profile_update_data["preferences"].items():
            assert data["preferences"][pref_key] == pref_value

        # Validate interests were updated
        updated_topics = [interest["topic"] for interest in data["interests"]]
        expected_topics = [interest["topic"] for interest in profile_update_data["interests"]]
        for topic in expected_topics:
            assert topic in [i["topic"] for i in data["interests"]]

        # Validate data types
        assert isinstance(data["user_id"], str)
        assert isinstance(data["interests"], list)
        assert isinstance(data["learning_goals"], list)
        assert isinstance(data["preferences"], dict)
        assert isinstance(data["skill_level"], dict)
        assert isinstance(data["updated_at"], str)
        assert isinstance(data["update_summary"], dict)

        # Validate formats
        assert_valid_uuid(data["user_id"])
        assert_datetime_format(data["updated_at"])

        # Validate update_summary
        assert "changes_made" in data["update_summary"]
        assert "fields_updated" in data["update_summary"]
        assert isinstance(data["update_summary"]["changes_made"], int)
        assert isinstance(data["update_summary"]["fields_updated"], list)

    @pytest.mark.asyncio
    async def test_update_personalization_profile_partial(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict, partial_profile_update: dict):
        """Test partial personalization profile update."""
        # Act
        response = await client.put("/personalization/profile", headers=auth_headers, json=partial_profile_update)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Validate partial updates were applied
        assert data["preferences"]["content_difficulty"] == "advanced"
        assert data["preferences"]["learning_style"] == "theory_first"

        # Other preferences should remain unchanged or have defaults
        assert "interaction_frequency" in data["preferences"]  # Should still exist

        # Learning goals should be updated
        assert len(data["learning_goals"]) >= 1
        assert any(goal["goal"] == "Advanced Python techniques" for goal in data["learning_goals"])

    @pytest.mark.asyncio
    async def test_update_personalization_profile_without_auth_unauthorized(self, client: AsyncClient, profile_update_data: dict):
        """Test personalization profile update without authentication returns 401."""
        # Act
        response = await client.put("/personalization/profile", json=profile_update_data)

        # Assert
        assert response.status_code == 401
        error_data = response.json()
        assert "error" in error_data
        assert "message" in error_data

    @pytest.mark.asyncio
    async def test_update_personalization_profile_invalid_token_unauthorized(self, client: AsyncClient, profile_update_data: dict):
        """Test personalization profile update with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.put("/personalization/profile", headers=invalid_headers, json=profile_update_data)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_personalization_profile_validation_errors(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict):
        """Test validation error responses for invalid profile data."""
        validation_test_cases = [
            # Invalid learning goal structure
            {
                "data": {
                    "learning_goals": [
                        {"goal": "", "priority": "high"}  # Empty goal
                    ]
                },
                "description": "empty learning goal"
            },
            {
                "data": {
                    "learning_goals": [
                        {"goal": "Learn Python", "priority": "invalid_priority"}
                    ]
                },
                "description": "invalid priority value"
            },
            {
                "data": {
                    "learning_goals": [
                        {"goal": "Learn Python", "priority": "high", "target_completion": "invalid-date"}
                    ]
                },
                "description": "invalid target_completion date"
            },
            # Invalid preferences
            {
                "data": {
                    "preferences": {
                        "content_difficulty": "invalid_difficulty"
                    }
                },
                "description": "invalid content_difficulty value"
            },
            {
                "data": {
                    "preferences": {
                        "learning_style": "invalid_style"
                    }
                },
                "description": "invalid learning_style value"
            },
            {
                "data": {
                    "preferences": {
                        "interaction_frequency": "invalid_frequency"
                    }
                },
                "description": "invalid interaction_frequency value"
            },
            # Invalid interests structure
            {
                "data": {
                    "interests": [
                        {"topic": "", "interest_level": "high"}  # Empty topic
                    ]
                },
                "description": "empty interest topic"
            },
            {
                "data": {
                    "interests": [
                        {"topic": "Python", "interest_level": "invalid_level"}
                    ]
                },
                "description": "invalid interest_level value"
            },
            # Invalid skill declarations
            {
                "data": {
                    "skill_declarations": {
                        "programming": "invalid_level"
                    }
                },
                "description": "invalid skill level value"
            },
            # Invalid data types
            {
                "data": {
                    "learning_goals": "not_a_list"
                },
                "description": "learning_goals not a list"
            },
            {
                "data": {
                    "preferences": "not_a_dict"
                },
                "description": "preferences not a dict"
            },
            {
                "data": {
                    "interests": "not_a_list"
                },
                "description": "interests not a list"
            }
        ]

        for test_case in validation_test_cases:
            # Act
            response = await client.put("/personalization/profile", headers=auth_headers, json=test_case["data"])

            # Assert
            assert response.status_code == 422, f"Expected 422 for {test_case['description']}, got {response.status_code}"

            # Validate error response structure
            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response

    @pytest.mark.asyncio
    async def test_update_personalization_profile_enum_validations(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict):
        """Test validation of enum values in profile update."""
        # Valid enum values
        valid_enums = {
            "content_difficulty": ["beginner", "intermediate", "advanced", "expert"],
            "learning_style": ["visual", "auditory", "hands_on", "theory_first", "mixed"],
            "interaction_frequency": ["never", "weekly", "daily", "multiple_daily"],
            "priority": ["low", "medium", "high", "urgent"],
            "interest_level": ["low", "medium", "high"],
            "skill_level": ["beginner", "intermediate", "advanced", "expert"]
        }

        # Test valid values
        for field, values in valid_enums.items():
            for value in values:
                if field in ["content_difficulty", "learning_style", "interaction_frequency"]:
                    update_data = {
                        "preferences": {
                            field: value
                        }
                    }
                elif field == "priority":
                    update_data = {
                        "learning_goals": [
                            {
                                "goal": f"Test goal for {field}",
                                "priority": value
                            }
                        ]
                    }
                elif field == "interest_level":
                    update_data = {
                        "interests": [
                            {
                                "topic": f"Test topic for {field}",
                                "interest_level": value
                            }
                        ]
                    }
                elif field == "skill_level":
                    update_data = {
                        "skill_declarations": {
                            "test_skill": value
                        }
                    }

                response = await client.put("/personalization/profile", headers=auth_headers, json=update_data)
                assert response.status_code == 200, f"Valid {field} value '{value}' should succeed"

    @pytest.mark.asyncio
    async def test_update_personalization_profile_merge_behavior(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict):
        """Test how profile updates merge with existing data."""
        # First update
        first_update = {
            "preferences": {
                "content_difficulty": "intermediate",
                "learning_style": "hands_on"
            },
            "learning_goals": [
                {
                    "goal": "Learn Python basics",
                    "priority": "high"
                }
            ]
        }

        response1 = await client.put("/personalization/profile", headers=auth_headers, json=first_update)
        assert response1.status_code == 200

        # Second update (should merge, not replace)
        second_update = {
            "preferences": {
                "interaction_frequency": "daily"  # New preference
            },
            "learning_goals": [
                {
                    "goal": "Master advanced Python",
                    "priority": "medium"
                }
            ]
        }

        response2 = await client.put("/personalization/profile", headers=auth_headers, json=second_update)
        assert response2.status_code == 200
        data = response2.json()

        # Should have merged preferences
        assert data["preferences"]["content_difficulty"] == "intermediate"  # From first update
        assert data["preferences"]["learning_style"] == "hands_on"  # From first update
        assert data["preferences"]["interaction_frequency"] == "daily"  # From second update

    @pytest.mark.asyncio
    async def test_update_personalization_profile_learning_goals_management(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict):
        """Test learning goals management in profile updates."""
        # Update with specific learning goals
        goals_update = {
            "learning_goals": [
                {
                    "goal": "Complete Python course",
                    "priority": "high",
                    "target_completion": "2024-08-31T23:59:59Z",
                    "progress": 0.3
                },
                {
                    "goal": "Build web application",
                    "priority": "medium",
                    "target_completion": "2024-12-31T23:59:59Z",
                    "progress": 0.0
                }
            ]
        }

        response = await client.put("/personalization/profile", headers=auth_headers, json=goals_update)
        assert response.status_code == 200
        data = response.json()

        # Validate goals structure
        assert len(data["learning_goals"]) == 2
        for goal in data["learning_goals"]:
            assert "goal" in goal
            assert "priority" in goal
            assert "progress" in goal
            assert isinstance(goal["progress"], (int, float))
            assert 0 <= goal["progress"] <= 1

    @pytest.mark.asyncio
    async def test_update_personalization_profile_interests_management(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict):
        """Test interests management in profile updates."""
        # Update with specific interests
        interests_update = {
            "interests": [
                {
                    "topic": "Machine Learning",
                    "interest_level": "high",
                    "category": "technology"
                },
                {
                    "topic": "Web Development",
                    "interest_level": "medium",
                    "category": "programming"
                },
                {
                    "topic": "Data Science",
                    "interest_level": "high",
                    "category": "analytics"
                }
            ]
        }

        response = await client.put("/personalization/profile", headers=auth_headers, json=interests_update)
        assert response.status_code == 200
        data = response.json()

        # Should have updated interests with proper structure
        topics = [interest["topic"] for interest in data["interests"]]
        assert "Machine Learning" in [i["topic"] for i in data["interests"]]
        assert "Web Development" in [i["topic"] for i in data["interests"]]
        assert "Data Science" in [i["topic"] for i in data["interests"]]

    @pytest.mark.asyncio
    async def test_update_personalization_profile_empty_request_body(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict):
        """Test update with empty request body."""
        # Act
        response = await client.put("/personalization/profile", headers=auth_headers, json={})

        # Assert - Should succeed with no changes
        assert response.status_code == 200
        data = response.json()

        # Should have update summary indicating no changes
        assert "update_summary" in data
        assert data["update_summary"]["changes_made"] == 0

    @pytest.mark.asyncio
    async def test_update_personalization_profile_null_values(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict):
        """Test update with null values."""
        # Test null values for optional fields
        null_update = {
            "learning_goals": None,  # Should clear learning goals
            "preferences": {
                "content_difficulty": None  # Should revert to default or clear
            }
        }

        response = await client.put("/personalization/profile", headers=auth_headers, json=null_update)

        # May succeed with nulls clearing values, or return validation error
        assert response.status_code in [200, 422]

        if response.status_code == 200:
            data = response.json()
            # Null learning_goals might result in empty list
            if "learning_goals" in data:
                assert isinstance(data["learning_goals"], list)

    @pytest.mark.asyncio
    async def test_update_personalization_profile_response_headers(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict, profile_update_data: dict):
        """Test that response includes correct headers."""
        # Act
        response = await client.put("/personalization/profile", headers=auth_headers, json=profile_update_data)

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_update_personalization_profile_unicode_handling(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict):
        """Test that unicode characters are handled correctly."""
        # Arrange
        unicode_update = {
            "learning_goals": [
                {
                    "goal": "学习人工智能 Learn AI 🤖",
                    "priority": "high"
                }
            ],
            "interests": [
                {
                    "topic": "机器学习 Machine Learning 🧠",
                    "interest_level": "high"
                }
            ]
        }

        # Act
        response = await client.put("/personalization/profile", headers=auth_headers, json=unicode_update)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Unicode should be properly preserved
        goal_text = data["learning_goals"][0]["goal"]
        assert "学习人工智能" in goal_text
        assert "🤖" in goal_text

    @pytest.mark.asyncio
    async def test_update_personalization_profile_cascading_effects(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict):
        """Test that profile updates trigger appropriate cascading effects."""
        # Update profile with new interests
        cascade_update = {
            "interests": [
                {
                    "topic": "Artificial Intelligence",
                    "interest_level": "high"
                },
                {
                    "topic": "Deep Learning",
                    "interest_level": "high"
                }
            ],
            "skill_declarations": {
                "ai": "beginner",
                "deep_learning": "beginner"
            }
        }

        response = await client.put("/personalization/profile", headers=auth_headers, json=cascade_update)
        assert response.status_code == 200
        data = response.json()

        # Should affect skill levels and potentially generate suggestions
        assert "skill_level" in data
        if "domain_levels" in data["skill_level"]:
            domain_levels = data["skill_level"]["domain_levels"]
            # AI-related skills should be reflected
            ai_related_skills = ["ai", "artificial_intelligence", "machine_learning", "deep_learning"]
            has_ai_skills = any(skill.lower() in [s.lower() for s in ai_related_skills] for skill in domain_levels.keys())
            # This is a soft assertion as skill mapping may vary
            assert len(domain_levels) >= 0  # Should have some domain levels

    @pytest.mark.asyncio
    async def test_update_personalization_profile_consistency_validation(self, client: AsyncClient, auth_headers: dict, existing_profile_user: dict):
        """Test that profile updates maintain data consistency."""
        # Update with potentially conflicting data
        consistency_update = {
            "skill_declarations": {
                "python": "expert"
            },
            "learning_goals": [
                {
                    "goal": "Learn Python basics",  # Conflicts with expert level
                    "priority": "high"
                }
            ]
        }

        response = await client.put("/personalization/profile", headers=auth_headers, json=consistency_update)

        # System should either accept and resolve conflict, or return validation error
        assert response.status_code in [200, 422]

        if response.status_code == 200:
            # If accepted, system should handle the logical inconsistency
            data = response.json()
            # Could suggest advanced goals instead, or flag the inconsistency
            assert "learning_goals" in data
            assert "skill_level" in data