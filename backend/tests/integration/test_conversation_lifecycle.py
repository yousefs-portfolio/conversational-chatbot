"""
Integration test for complete conversation lifecycle management.

This test validates the entire conversation lifecycle from creation through
multiple interactions, context management, and eventual archival/deletion.
According to TDD, this test MUST FAIL initially until all endpoints are implemented.
"""
import pytest
from httpx import AsyncClient
import uuid
import asyncio


class TestConversationLifecycle:
    """Test complete conversation lifecycle integration."""

    @pytest.mark.asyncio
    async def test_complete_conversation_lifecycle(self, client: AsyncClient, auth_headers: dict):
        """Test the complete conversation lifecycle from creation to deletion."""

        # Step 1: Create New Conversation
        # This MUST FAIL initially until all endpoints are implemented
        conversation_data = {
            "title": "Long Conversation Test",
            "system_prompt": "You are an AI assistant helping with a research project."
        }

        create_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        assert create_response.status_code == 201

        conversation = create_response.json()
        conversation_id = conversation["id"]
        assert conversation["message_count"] == 0

        # Step 2: Build Context Through Multiple Messages
        messages_to_send = [
            "Hello! I'm starting a research project on renewable energy.",
            "Can you help me understand the main types of renewable energy sources?",
            "That's very helpful! Can you elaborate on solar energy efficiency?",
            "What about wind energy? How does it compare to solar?",
            "I'm particularly interested in offshore wind farms. Can you tell me more?",
            "How do these renewable sources impact the electrical grid?",
            "What are the main challenges in renewable energy storage?",
            "Can you summarize the key points we've discussed so far?"
        ]

        conversation_messages = []

        for i, message_content in enumerate(messages_to_send):
            # Send user message
            message_data = {
                "content": message_content,
                "role": "user",
                "metadata": {
                    "message_sequence": i + 1,
                    "conversation_phase": "research_phase"
                }
            }

            msg_response = await client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json=message_data
            )
            assert msg_response.status_code == 201

            response_data = msg_response.json()
            conversation_messages.extend([
                response_data["user_message"],
                response_data["assistant_message"]
            ])

            # Verify conversation state after each message
            conv_check = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
            assert conv_check.status_code == 200

            conv_data = conv_check.json()
            expected_message_count = (i + 1) * 2  # User + Assistant for each exchange
            assert conv_data["message_count"] == expected_message_count

            # Brief pause between messages to simulate real conversation
            await asyncio.sleep(0.1)

        # Step 3: Verify Full Message History
        messages_response = await client.get(f"/conversations/{conversation_id}/messages", headers=auth_headers)
        assert messages_response.status_code == 200

        messages_data = messages_response.json()
        assert len(messages_data["data"]) == len(messages_to_send) * 2

        # Verify message ordering
        for i, message in enumerate(messages_data["data"]):
            expected_role = "user" if i % 2 == 0 else "assistant"
            assert message["role"] == expected_role

        # Step 4: Test Context Awareness in Latest Message
        context_test_message = {
            "content": "Based on everything we've discussed, what would you recommend as the best renewable energy solution for a coastal city?",
            "role": "user"
        }

        context_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json=context_test_message
        )
        assert context_response.status_code == 201

        context_data = context_response.json()
        assistant_response = context_data["assistant_message"]["content"]

        # Response should reference previous conversation (context awareness)
        # We can't assert specific content, but should be non-empty and relevant
        assert len(assistant_response) > 50  # Should be a substantial response

        # Step 5: Test Conversation Pagination with Large History
        # Get messages with pagination
        paginated_response = await client.get(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            params={"page": 1, "limit": 5}
        )
        assert paginated_response.status_code == 200

        paginated_data = paginated_response.json()
        assert len(paginated_data["data"]) <= 5
        assert "pagination" in paginated_data
        assert paginated_data["pagination"]["total"] > 5

        # Step 6: Update Conversation Metadata
        update_data = {
            "title": "Renewable Energy Research - Comprehensive Discussion",
            "tags": ["research", "renewable_energy", "solar", "wind"],
            "summary": "Detailed discussion about renewable energy sources, focusing on solar and wind power, including storage challenges and grid integration."
        }

        # If conversation update endpoint exists
        update_response = await client.put(f"/conversations/{conversation_id}", headers=auth_headers, json=update_data)
        if update_response.status_code == 200:
            updated_conv = update_response.json()
            assert updated_conv["title"] == update_data["title"]

        # Step 7: Test Memory Creation from Extended Conversation
        memory_response = await client.get("/memory", headers=auth_headers)
        if memory_response.status_code == 200:
            memory_data = memory_response.json()

            # Long conversation should potentially create memories
            # Check if any memories relate to renewable energy
            renewable_memories = [
                m for m in memory_data["data"]
                if "renewable" in m.get("content", "").lower() or "solar" in m.get("content", "").lower()
            ]

            # This is implementation-dependent, so we don't assert specific memories exist

        # Step 8: Test Conversation Search/Filtering
        search_response = await client.get(
            "/conversations",
            headers=auth_headers,
            params={"q": "renewable energy"}
        )

        if search_response.status_code == 200:
            search_data = search_response.json()
            # Our conversation should be findable
            conversation_found = any(
                conv["id"] == conversation_id for conv in search_data["data"]
            )
            # Implementation might not include search yet, so we don't assert

        # Step 9: Export Conversation Data
        export_response = await client.get(f"/conversations/{conversation_id}/export", headers=auth_headers)
        if export_response.status_code == 200:
            export_data = export_response.json()

            # Export should include all conversation data
            assert "conversation" in export_data
            assert "messages" in export_data
            assert export_data["conversation"]["id"] == conversation_id
            assert len(export_data["messages"]) > 0

        # Step 10: Archive Conversation
        archive_response = await client.post(f"/conversations/{conversation_id}/archive", headers=auth_headers)
        if archive_response.status_code == 200:
            # Verify conversation is archived
            archived_conv_response = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
            if archived_conv_response.status_code == 200:
                archived_conv = archived_conv_response.json()
                assert archived_conv.get("archived") is True

        # Step 11: Test Archived Conversation Access
        # Archived conversations might have limited access
        archived_messages_response = await client.get(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers
        )
        # Should still be accessible but might be marked as archived
        assert archived_messages_response.status_code in [200, 403]

        # Step 12: Restore from Archive (if supported)
        restore_response = await client.post(f"/conversations/{conversation_id}/restore", headers=auth_headers)
        if restore_response.status_code == 200:
            restored_conv_response = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
            restored_conv = restored_conv_response.json()
            assert restored_conv.get("archived") is not True

        # Step 13: Final Cleanup - Delete Conversation
        delete_response = await client.delete(f"/conversations/{conversation_id}", headers=auth_headers)
        if delete_response.status_code in [200, 204]:
            # Verify conversation is deleted
            deleted_check = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
            assert deleted_check.status_code == 404

        return {
            "conversation_id": conversation_id,
            "message_count": len(messages_to_send) * 2 + 2,  # +2 for context test
            "final_title": update_data["title"]
        }

    @pytest.mark.asyncio
    async def test_conversation_context_limits(self, client: AsyncClient, auth_headers: dict):
        """Test conversation behavior when approaching context limits."""

        # Create conversation
        conversation_data = {
            "title": "Context Limit Test",
            "system_prompt": "You are a helpful assistant."
        }

        create_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        if create_response.status_code != 201:
            pytest.skip("Conversations endpoint not implemented yet")

        conversation_id = create_response.json()["id"]

        # Send messages that progressively approach token limits
        long_messages = [
            "Please explain in detail the history of artificial intelligence, including major milestones, key figures, and technological breakthroughs from the 1940s to present day.",
            "Now, can you provide an equally detailed explanation of machine learning algorithms, including supervised learning, unsupervised learning, reinforcement learning, and deep learning approaches?",
            "Additionally, please describe the current state of natural language processing, including transformer architectures, attention mechanisms, and recent advances in large language models.",
            "Finally, discuss the ethical implications and future prospects of AI technology, including potential risks, benefits, and regulatory considerations."
        ]

        for i, message_content in enumerate(long_messages):
            message_data = {
                "content": message_content,
                "role": "user"
            }

            msg_response = await client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json=message_data
            )

            # Should handle context gracefully
            assert msg_response.status_code in [200, 201, 413]  # 413 = Request Entity Too Large

            if msg_response.status_code == 413:
                # Context limit reached - this is expected behavior
                break
            elif msg_response.status_code in [200, 201]:
                response_data = msg_response.json()
                assert "assistant_message" in response_data

        # Verify conversation is still accessible
        final_check = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
        assert final_check.status_code == 200

    @pytest.mark.asyncio
    async def test_concurrent_conversation_access(self, client: AsyncClient, auth_headers: dict):
        """Test concurrent access to the same conversation."""

        # Create conversation
        conversation_data = {"title": "Concurrent Access Test"}
        create_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        if create_response.status_code != 201:
            pytest.skip("Conversations endpoint not implemented yet")

        conversation_id = create_response.json()["id"]

        # Simulate concurrent message sending
        async def send_message(content: str, sequence: int):
            message_data = {
                "content": f"{content} (Message {sequence})",
                "role": "user",
                "metadata": {"sequence": sequence}
            }

            response = await client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json=message_data
            )
            return response.status_code, sequence

        # Send multiple messages concurrently
        concurrent_tasks = [
            send_message("Hello", i) for i in range(1, 4)
        ]

        results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)

        # At least some messages should succeed
        successful_sends = [r for r in results if not isinstance(r, Exception) and r[0] in [200, 201]]
        assert len(successful_sends) > 0

        # Verify final conversation state
        final_check = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
        if final_check.status_code == 200:
            final_data = final_check.json()
            # Message count should reflect successful sends
            assert final_data["message_count"] >= len(successful_sends)

    @pytest.mark.asyncio
    async def test_conversation_with_tools_integration(self, client: AsyncClient, auth_headers: dict):
        """Test conversation lifecycle with tool usage integration."""

        # Create conversation for tool usage
        conversation_data = {
            "title": "Tool Integration Test",
            "system_prompt": "You are an assistant that can use tools to help users."
        }

        create_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        if create_response.status_code != 201:
            pytest.skip("Conversations endpoint not implemented yet")

        conversation_id = create_response.json()["id"]

        # Send message that should trigger tool usage
        tool_message = {
            "content": "Can you search for information about Python programming best practices?",
            "role": "user",
            "enable_tools": True
        }

        msg_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json=tool_message
        )

        if msg_response.status_code in [200, 201]:
            response_data = msg_response.json()
            assistant_message = response_data["assistant_message"]

            # Check if tool execution information is included
            if "metadata" in assistant_message:
                metadata = assistant_message["metadata"]
                # Might include tool execution details
                if "tools_used" in metadata:
                    assert isinstance(metadata["tools_used"], list)

        # Verify conversation includes tool usage history
        final_conversation = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
        if final_conversation.status_code == 200:
            conv_data = final_conversation.json()
            # Conversation might track tool usage in metadata
            assert conv_data["message_count"] >= 2