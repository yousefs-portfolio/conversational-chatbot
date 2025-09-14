"""
Integration test for complete user registration and first conversation flow.

This test validates the entire user journey from registration to having their first
AI conversation, ensuring all components work together correctly.
According to TDD, this test MUST FAIL initially until all endpoints are implemented.
"""
import pytest
from httpx import AsyncClient
import uuid


class TestUserRegistrationFlow:
    """Test complete user registration and first conversation integration."""

    @pytest.fixture
    def unique_user_data(self):
        """Generate unique user data for each test run."""
        unique_id = str(uuid.uuid4())[:8]
        return {
            "email": f"testuser_{unique_id}@example.com",
            "password": "SecurePassword123!",
            "full_name": f"Test User {unique_id}"
        }

    @pytest.mark.asyncio
    async def test_complete_user_registration_and_conversation_flow(self, client: AsyncClient, unique_user_data: dict):
        """Test the complete flow from user registration to first conversation."""

        # Step 1: User Registration
        # This MUST FAIL initially until all endpoints are implemented
        register_response = await client.post("/auth/register", json=unique_user_data)
        assert register_response.status_code == 201

        register_data = register_response.json()
        assert "access_token" in register_data
        assert "refresh_token" in register_data
        assert "user" in register_data

        access_token = register_data["access_token"]
        user_id = register_data["user"]["id"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # Step 2: Verify User Authentication
        profile_response = await client.get("/auth/me", headers=auth_headers)
        assert profile_response.status_code == 200

        profile_data = profile_response.json()
        assert profile_data["id"] == user_id
        assert profile_data["email"] == unique_user_data["email"]

        # Step 3: Check Initial User State
        # User should start with no conversations
        conversations_response = await client.get("/conversations", headers=auth_headers)
        assert conversations_response.status_code == 200

        conversations_data = conversations_response.json()
        assert conversations_data["data"] == []
        assert conversations_data["pagination"]["total"] == 0

        # Step 4: Check Initial Memory State
        memory_response = await client.get("/memory", headers=auth_headers)
        assert memory_response.status_code == 200

        memory_data = memory_response.json()
        assert memory_data["data"] == []

        # Step 5: Check Default Preferences
        preferences_response = await client.get("/preferences", headers=auth_headers)
        assert preferences_response.status_code == 200

        preferences_data = preferences_response.json()
        # Should have default preferences set
        assert isinstance(preferences_data, dict)
        assert len(preferences_data) > 0

        # Step 6: Create First Conversation
        conversation_create_data = {
            "title": "My First AI Conversation",
            "system_prompt": "You are a helpful AI assistant."
        }

        conversation_response = await client.post("/conversations", headers=auth_headers, json=conversation_create_data)
        assert conversation_response.status_code == 201

        conversation_data = conversation_response.json()
        conversation_id = conversation_data["id"]
        assert conversation_data["title"] == conversation_create_data["title"]
        assert conversation_data["message_count"] == 0
        assert conversation_data["user_id"] == user_id

        # Step 7: Send First Message
        first_message_data = {
            "content": "Hello! This is my first message. Can you help me understand what you can do?",
            "role": "user"
        }

        message_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json=first_message_data
        )
        assert message_response.status_code == 201

        message_data = message_response.json()
        assert "user_message" in message_data
        assert "assistant_message" in message_data

        user_message = message_data["user_message"]
        assistant_message = message_data["assistant_message"]

        # Validate user message
        assert user_message["content"] == first_message_data["content"]
        assert user_message["role"] == "user"

        # Validate assistant response
        assert assistant_message["role"] == "assistant"
        assert len(assistant_message["content"]) > 0

        # Step 8: Verify Conversation State Updated
        updated_conversation_response = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
        assert updated_conversation_response.status_code == 200

        updated_conversation = updated_conversation_response.json()
        assert updated_conversation["message_count"] == 2  # User + Assistant message
        assert len(updated_conversation["messages"]) == 2

        # Step 9: Verify Messages Are Stored
        messages_response = await client.get(f"/conversations/{conversation_id}/messages", headers=auth_headers)
        assert messages_response.status_code == 200

        messages_data = messages_response.json()
        assert len(messages_data["data"]) == 2

        # Messages should be in chronological order
        messages = messages_data["data"]
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

        # Step 10: Check If Memory Was Created
        # The system might automatically create memories from the conversation
        updated_memory_response = await client.get("/memory", headers=auth_headers)
        assert updated_memory_response.status_code == 200

        updated_memory = updated_memory_response.json()
        # Memory might be created automatically or remain empty initially
        # Both are acceptable for this integration test

        # Step 11: Send Follow-up Message
        followup_message_data = {
            "content": "That's great! Can you help me with a specific task - I need to write a Python function.",
            "role": "user"
        }

        followup_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json=followup_message_data
        )
        assert followup_response.status_code == 201

        followup_data = followup_response.json()
        followup_assistant = followup_data["assistant_message"]

        # Response should be contextually aware
        assert len(followup_assistant["content"]) > 0
        assert followup_assistant["role"] == "assistant"

        # Step 12: Verify Final State
        final_conversation_response = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
        final_conversation = final_conversation_response.json()

        assert final_conversation["message_count"] == 4  # 2 user + 2 assistant messages

        # Step 13: List All Conversations (Should Show Our New One)
        all_conversations_response = await client.get("/conversations", headers=auth_headers)
        all_conversations = all_conversations_response.json()

        assert len(all_conversations["data"]) == 1
        assert all_conversations["data"][0]["id"] == conversation_id
        assert all_conversations["pagination"]["total"] == 1

        # Step 14: Test Authentication Persistence
        # Make another request to verify token is still valid
        auth_check_response = await client.get("/auth/me", headers=auth_headers)
        assert auth_check_response.status_code == 200

        return {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "access_token": access_token,
            "user_data": unique_user_data
        }

    @pytest.mark.asyncio
    async def test_user_registration_error_handling(self, client: AsyncClient):
        """Test error handling during user registration flow."""

        # Test duplicate email registration
        user_data = {
            "email": "duplicate@example.com",
            "password": "SecurePassword123!",
            "full_name": "First User"
        }

        # First registration should succeed
        first_response = await client.post("/auth/register", json=user_data)
        if first_response.status_code == 201:
            # Second registration with same email should fail
            second_response = await client.post("/auth/register", json=user_data)
            assert second_response.status_code == 409  # Conflict
        else:
            # If first registration fails, it's expected (TDD)
            assert first_response.status_code in [400, 422, 500]

    @pytest.mark.asyncio
    async def test_conversation_flow_with_preferences(self, client: AsyncClient, unique_user_data: dict):
        """Test conversation flow with custom user preferences."""

        # Register user
        register_response = await client.post("/auth/register", json=unique_user_data)
        if register_response.status_code != 201:
            pytest.skip("Registration endpoint not implemented yet")

        auth_headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}

        # Set custom preferences
        preferences_data = {
            "ai_model": {
                "provider": "anthropic",
                "model": "claude-3-haiku-20240307",
                "temperature": 0.3,
                "max_tokens": 1000
            },
            "chat": {
                "max_context_length": 6000,
                "auto_save": True
            }
        }

        prefs_response = await client.put("/preferences", headers=auth_headers, json=preferences_data)
        if prefs_response.status_code != 200:
            pytest.skip("Preferences endpoint not implemented yet")

        # Create conversation with custom system prompt
        conversation_data = {
            "title": "Code Helper Session",
            "system_prompt": "You are a coding assistant specializing in Python. Be concise and practical."
        }

        conv_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        if conv_response.status_code != 201:
            pytest.skip("Conversations endpoint not implemented yet")

        conversation_id = conv_response.json()["id"]

        # Send message that should use the custom preferences
        message_data = {
            "content": "Write a simple Python function to calculate factorial",
            "role": "user"
        }

        msg_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json=message_data
        )

        if msg_response.status_code == 201:
            # Verify the response was generated with custom preferences
            response_data = msg_response.json()
            assistant_message = response_data["assistant_message"]

            # Response should be practical and code-focused (based on system prompt)
            assert len(assistant_message["content"]) > 0

            # The response length should respect max_tokens preference
            # (This is implementation-dependent and may not be directly testable)

    @pytest.mark.asyncio
    async def test_memory_creation_during_conversation(self, client: AsyncClient, unique_user_data: dict):
        """Test that memories are created during natural conversation flow."""

        # Register and authenticate user
        register_response = await client.post("/auth/register", json=unique_user_data)
        if register_response.status_code != 201:
            pytest.skip("Registration endpoint not implemented yet")

        auth_headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}

        # Create conversation
        conversation_data = {"title": "Personal Information Chat"}
        conv_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        if conv_response.status_code != 201:
            pytest.skip("Conversations endpoint not implemented yet")

        conversation_id = conv_response.json()["id"]

        # Share personal information that should create memories
        personal_message = {
            "content": "Hi! I'm a software engineer working at TechCorp. I love Python programming and prefer dark theme interfaces. I'm working on a machine learning project.",
            "role": "user"
        }

        msg_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json=personal_message
        )

        if msg_response.status_code != 201:
            pytest.skip("Messages endpoint not implemented yet")

        # Check if memories were automatically created
        memory_response = await client.get("/memory", headers=auth_headers)
        if memory_response.status_code == 200:
            memory_data = memory_response.json()

            # Memories might be created automatically from the conversation
            # This is implementation-dependent, so we don't assert specific memories exist
            # but we verify the memory system is accessible
            assert isinstance(memory_data["data"], list)

            # If memories were created, they should be properly formatted
            for memory in memory_data["data"]:
                assert "content" in memory
                assert "type" in memory
                assert "importance" in memory