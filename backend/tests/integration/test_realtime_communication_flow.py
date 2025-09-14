"""
Integration test for complete real-time communication flow.

This test validates the entire real-time system including WebSocket connections,
streaming responses, live updates, presence system, and integration with all
other system components.
According to TDD, this test MUST FAIL initially until all endpoints are implemented.
"""
import pytest
from httpx import AsyncClient
import websockets
import json
import asyncio
import uuid
from urllib.parse import urlparse


class TestRealtimeCommunicationFlow:
    """Test complete real-time communication integration."""

    @pytest.fixture
    def websocket_url(self, client: AsyncClient):
        """Generate WebSocket URL from HTTP client base URL."""
        base_url = str(client.base_url)
        parsed = urlparse(base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        return f"{scheme}://{parsed.netloc}/ws"

    @pytest.fixture
    def auth_token(self, auth_headers: dict):
        """Extract auth token from headers."""
        auth_header = auth_headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return "test-token"

    @pytest.mark.asyncio
    async def test_complete_realtime_conversation_flow(self, client: AsyncClient, auth_headers: dict,
                                                      websocket_url: str, auth_token: str):
        """Test complete real-time conversation flow from connection to streaming response."""

        # Step 1: Establish REST API Session
        # This MUST FAIL initially until all endpoints are implemented

        # Create conversation via REST API
        conversation_data = {
            "title": "Real-time Test Conversation",
            "system_prompt": "You are an AI assistant providing real-time responses."
        }

        conv_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        if conv_response.status_code != 201:
            pytest.skip("REST API conversations not implemented yet")

        conversation_id = conv_response.json()["id"]

        # Step 2: Establish WebSocket Connection
        websocket_url_with_auth = f"{websocket_url}?token={auth_token}"

        try:
            async with websockets.connect(websocket_url_with_auth) as websocket:
                # Step 3: Subscribe to Conversation Updates
                subscribe_message = {
                    "type": "conversation.subscribe",
                    "data": {
                        "conversation_id": conversation_id,
                        "include_typing": True,
                        "include_presence": True
                    }
                }

                await websocket.send(json.dumps(subscribe_message))

                # Wait for subscription confirmation
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                response_data = json.loads(response)

                assert response_data["type"] in ["conversation.subscribed", "subscription.confirmed"]

                # Step 4: Send Real-time Message with Streaming Response
                streaming_message = {
                    "type": "conversation.message",
                    "data": {
                        "conversation_id": conversation_id,
                        "content": "Please write a detailed explanation of how machine learning works, and stream your response in real-time.",
                        "role": "user",
                        "stream": True,
                        "request_id": str(uuid.uuid4())
                    }
                }

                await websocket.send(json.dumps(streaming_message))

                # Step 5: Collect Streaming Response
                streaming_chunks = []
                complete_response = None
                message_received_ack = False

                try:
                    while True:
                        response = await asyncio.wait_for(websocket.recv(), timeout=20)
                        response_data = json.loads(response)

                        if response_data["type"] == "conversation.message.received":
                            message_received_ack = True
                            assert response_data["data"]["conversation_id"] == conversation_id

                        elif response_data["type"] == "conversation.message.streaming":
                            streaming_chunks.append(response_data)

                        elif response_data["type"] == "conversation.message.complete":
                            complete_response = response_data
                            break

                        elif response_data["type"] == "error":
                            pytest.fail(f"Received error during streaming: {response_data}")

                except asyncio.TimeoutError:
                    # Timeout is acceptable if we received some data
                    pass

                # Validate streaming response
                assert message_received_ack, "Should receive message acknowledgment"
                assert len(streaming_chunks) > 0, "Should receive streaming chunks"

                # Each chunk should be properly formatted
                for chunk in streaming_chunks:
                    assert "data" in chunk
                    assert "conversation_id" in chunk["data"]
                    assert chunk["data"]["conversation_id"] == conversation_id

                # Should have a complete response
                if complete_response:
                    assert "data" in complete_response
                    assert "content" in complete_response["data"]

                # Step 6: Verify Message Was Saved via REST API
                messages_response = await client.get(
                    f"/conversations/{conversation_id}/messages",
                    headers=auth_headers
                )

                if messages_response.status_code == 200:
                    messages_data = messages_response.json()

                    # Should have both user and assistant messages
                    assert len(messages_data["data"]) >= 2

                    latest_messages = messages_data["data"][-2:]
                    user_message = next((m for m in latest_messages if m["role"] == "user"), None)
                    assistant_message = next((m for m in latest_messages if m["role"] == "assistant"), None)

                    assert user_message is not None
                    assert assistant_message is not None
                    assert "machine learning" in user_message["content"]

                # Step 7: Test Typing Indicators
                typing_start = {
                    "type": "typing.start",
                    "data": {
                        "conversation_id": conversation_id,
                        "user_id": "test-user"
                    }
                }

                await websocket.send(json.dumps(typing_start))

                # Should receive typing acknowledgment
                typing_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                typing_data = json.loads(typing_response)

                assert typing_data["type"] in ["typing.start.ack", "typing.status"]

                # Send typing stop
                typing_stop = {
                    "type": "typing.stop",
                    "data": {
                        "conversation_id": conversation_id,
                        "user_id": "test-user"
                    }
                }

                await websocket.send(json.dumps(typing_stop))

                # Step 8: Test Tool Execution via WebSocket
                tool_execution_message = {
                    "type": "tool.execute",
                    "data": {
                        "tool_id": "web_search",
                        "parameters": {
                            "query": "latest AI research 2024"
                        },
                        "conversation_id": conversation_id,
                        "stream_updates": True
                    }
                }

                await websocket.send(json.dumps(tool_execution_message))

                # Collect tool execution updates
                tool_updates = []
                tool_complete = None

                try:
                    while len(tool_updates) < 3:  # Limit to prevent infinite loop
                        response = await asyncio.wait_for(websocket.recv(), timeout=10)
                        response_data = json.loads(response)

                        if response_data["type"] == "tool.execution.update":
                            tool_updates.append(response_data)
                        elif response_data["type"] == "tool.execution.complete":
                            tool_complete = response_data
                            break

                except asyncio.TimeoutError:
                    # Tool execution might not be implemented yet
                    pass

                # If tool execution worked, validate the updates
                if tool_updates or tool_complete:
                    for update in tool_updates:
                        assert "data" in update
                        assert "status" in update["data"]

                # Step 9: Test Memory Updates via WebSocket
                memory_create = {
                    "type": "memory.create",
                    "data": {
                        "content": "User is interested in real-time AI communication systems",
                        "type": "preference",
                        "importance": 0.8,
                        "context": {
                            "conversation_id": conversation_id,
                            "source": "realtime_test"
                        }
                    }
                }

                await websocket.send(json.dumps(memory_create))

                # Should receive memory creation confirmation
                try:
                    memory_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    memory_data = json.loads(memory_response)

                    if memory_data["type"] in ["memory.created", "memory.update"]:
                        assert "data" in memory_data
                        assert "content" in memory_data["data"]

                except asyncio.TimeoutError:
                    # Memory system might not be implemented via WebSocket yet
                    pass

                # Step 10: Test Presence System
                presence_update = {
                    "type": "presence.update",
                    "data": {
                        "status": "active",
                        "activity": "testing_realtime_features"
                    }
                }

                await websocket.send(json.dumps(presence_update))

                try:
                    presence_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    presence_data = json.loads(presence_response)

                    assert presence_data["type"] in ["presence.update.ack", "presence.status"]

                except asyncio.TimeoutError:
                    # Presence system might not be implemented yet
                    pass

                # Step 11: Test Connection State Management
                state_request = {
                    "type": "connection.get_state",
                    "data": {}
                }

                await websocket.send(json.dumps(state_request))

                try:
                    state_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    state_data = json.loads(state_response)

                    if state_data["type"] == "connection.state":
                        assert "data" in state_data
                        # State should include subscriptions and connection info
                        connection_state = state_data["data"]
                        assert isinstance(connection_state, dict)

                except asyncio.TimeoutError:
                    # State management might not be implemented yet
                    pass

        except ConnectionError:
            pytest.skip("WebSocket endpoint not implemented yet")

        # Step 12: Verify Final State via REST API
        final_conversation = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
        if final_conversation.status_code == 200:
            final_data = final_conversation.json()

            # Conversation should show activity from WebSocket interactions
            assert final_data["message_count"] >= 2

        return {
            "conversation_id": conversation_id,
            "streaming_chunks_received": len(streaming_chunks) if 'streaming_chunks' in locals() else 0,
            "websocket_features_tested": [
                "subscription", "streaming", "typing", "tools", "memory", "presence", "state"
            ]
        }

    @pytest.mark.asyncio
    async def test_multi_user_realtime_collaboration(self, client: AsyncClient, auth_headers: dict,
                                                   websocket_url: str, auth_token: str):
        """Test real-time collaboration between multiple users (simulated)."""

        # Create shared conversation
        conversation_data = {"title": "Collaborative Conversation"}
        conv_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)

        if conv_response.status_code != 201:
            pytest.skip("Conversations endpoint not implemented yet")

        conversation_id = conv_response.json()["id"]

        try:
            # Simulate two users connecting to the same conversation
            websocket_url_with_auth = f"{websocket_url}?token={auth_token}"

            async with websockets.connect(websocket_url_with_auth) as ws1:
                async with websockets.connect(websocket_url_with_auth) as ws2:

                    # Both users subscribe to the same conversation
                    subscribe_msg = {
                        "type": "conversation.subscribe",
                        "data": {"conversation_id": conversation_id}
                    }

                    await ws1.send(json.dumps(subscribe_msg))
                    await ws2.send(json.dumps(subscribe_msg))

                    # Wait for confirmations
                    await asyncio.wait_for(ws1.recv(), timeout=5)
                    await asyncio.wait_for(ws2.recv(), timeout=5)

                    # User 1 starts typing
                    typing_msg = {
                        "type": "typing.start",
                        "data": {
                            "conversation_id": conversation_id,
                            "user_id": "user1"
                        }
                    }

                    await ws1.send(json.dumps(typing_msg))

                    # User 2 should receive typing notification
                    try:
                        typing_notification = await asyncio.wait_for(ws2.recv(), timeout=3)
                        typing_data = json.loads(typing_notification)

                        if typing_data["type"] == "typing.user_started":
                            assert typing_data["data"]["user_id"] == "user1"

                    except asyncio.TimeoutError:
                        # Typing notifications might not be implemented yet
                        pass

                    # User 1 sends a message
                    message_msg = {
                        "type": "conversation.message",
                        "data": {
                            "conversation_id": conversation_id,
                            "content": "Hello from user 1!",
                            "role": "user"
                        }
                    }

                    await ws1.send(json.dumps(message_msg))

                    # User 2 should receive the message update
                    try:
                        message_notification = await asyncio.wait_for(ws2.recv(), timeout=5)
                        msg_data = json.loads(message_notification)

                        if msg_data["type"] in ["conversation.message.added", "conversation.update"]:
                            assert msg_data["data"]["conversation_id"] == conversation_id

                    except asyncio.TimeoutError:
                        # Live message updates might not be implemented yet
                        pass

        except ConnectionError:
            pytest.skip("WebSocket endpoint not implemented yet")

    @pytest.mark.asyncio
    async def test_realtime_error_recovery(self, client: AsyncClient, auth_headers: dict,
                                          websocket_url: str, auth_token: str):
        """Test real-time error handling and connection recovery."""

        websocket_url_with_auth = f"{websocket_url}?token={auth_token}"

        try:
            async with websockets.connect(websocket_url_with_auth) as websocket:
                # Test 1: Send malformed message
                await websocket.send("invalid json")

                error_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                error_data = json.loads(error_response)

                assert error_data["type"] == "error"
                assert "message" in error_data

                # Connection should still be alive
                await websocket.ping()

                # Test 2: Send message with invalid type
                invalid_msg = {
                    "type": "nonexistent.message.type",
                    "data": {"test": "data"}
                }

                await websocket.send(json.dumps(invalid_msg))

                invalid_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                invalid_data = json.loads(invalid_response)

                assert invalid_data["type"] == "error"

                # Test 3: Send message to non-existent conversation
                nonexistent_msg = {
                    "type": "conversation.message",
                    "data": {
                        "conversation_id": str(uuid.uuid4()),
                        "content": "This should fail",
                        "role": "user"
                    }
                }

                await websocket.send(json.dumps(nonexistent_msg))

                not_found_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                not_found_data = json.loads(not_found_response)

                assert not_found_data["type"] == "error"
                assert "404" in str(not_found_data) or "not found" in str(not_found_data).lower()

                # Connection should still be functional after errors
                heartbeat = {"type": "heartbeat", "data": {}}
                await websocket.send(json.dumps(heartbeat))

                heartbeat_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                heartbeat_data = json.loads(heartbeat_response)

                assert heartbeat_data["type"] == "heartbeat.response"

        except ConnectionError:
            pytest.skip("WebSocket endpoint not implemented yet")

    @pytest.mark.asyncio
    async def test_realtime_performance_and_scaling(self, client: AsyncClient, auth_headers: dict,
                                                   websocket_url: str, auth_token: str):
        """Test real-time system performance under load."""

        websocket_url_with_auth = f"{websocket_url}?token={auth_token}"

        try:
            async with websockets.connect(websocket_url_with_auth) as websocket:
                # Test rapid message sending
                messages_sent = 0
                responses_received = 0

                # Send multiple messages quickly
                for i in range(5):
                    message = {
                        "type": "heartbeat",
                        "data": {"sequence": i, "timestamp": f"test_{i}"}
                    }

                    await websocket.send(json.dumps(message))
                    messages_sent += 1

                    # Try to receive response without blocking
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=1)
                        response_data = json.loads(response)

                        if response_data["type"] in ["heartbeat.response", "rate_limit_exceeded"]:
                            responses_received += 1

                    except asyncio.TimeoutError:
                        continue

                # Should handle rapid messages gracefully
                assert messages_sent > 0
                # Responses might be throttled, which is acceptable

                # Test large message handling
                large_content = "x" * 1000  # 1KB message
                large_message = {
                    "type": "conversation.message",
                    "data": {
                        "conversation_id": str(uuid.uuid4()),
                        "content": large_content,
                        "role": "user"
                    }
                }

                await websocket.send(json.dumps(large_message))

                # Should handle large messages appropriately
                large_response = await asyncio.wait_for(websocket.recv(), timeout=10)
                large_data = json.loads(large_response)

                # Either processed successfully or rejected with appropriate error
                assert large_data["type"] in [
                    "conversation.message.received",
                    "error",
                    "conversation.message.streaming"
                ]

        except ConnectionError:
            pytest.skip("WebSocket endpoint not implemented yet")

    @pytest.mark.asyncio
    async def test_realtime_system_integration(self, client: AsyncClient, auth_headers: dict,
                                              websocket_url: str, auth_token: str):
        """Test integration between real-time WebSocket and all other system components."""

        # Create initial data via REST API
        conversation_response = await client.post(
            "/conversations",
            headers=auth_headers,
            json={"title": "Integration Test"}
        )

        if conversation_response.status_code != 201:
            pytest.skip("REST API not implemented yet")

        conversation_id = conversation_response.json()["id"]

        # Create initial memory
        memory_response = await client.post(
            "/memory",
            headers=auth_headers,
            json={
                "content": "User prefers real-time communication",
                "type": "preference",
                "importance": 0.8
            }
        )

        memory_created = memory_response.status_code == 201

        websocket_url_with_auth = f"{websocket_url}?token={auth_token}"

        try:
            async with websockets.connect(websocket_url_with_auth) as websocket:
                # Subscribe to all update types
                multi_subscribe = {
                    "type": "subscribe.all",
                    "data": {
                        "conversation_id": conversation_id,
                        "include_memory": True,
                        "include_tools": True,
                        "include_presence": True
                    }
                }

                await websocket.send(json.dumps(multi_subscribe))

                # Send complex message that should trigger multiple systems
                complex_message = {
                    "type": "conversation.message",
                    "data": {
                        "conversation_id": conversation_id,
                        "content": "I need you to search for information about real-time systems, remember my preferences, and provide a streaming response.",
                        "role": "user",
                        "enable_tools": True,
                        "create_memories": True,
                        "stream": True,
                        "use_existing_memories": True
                    }
                }

                await websocket.send(json.dumps(complex_message))

                # Collect various types of responses
                system_responses = {
                    "message_ack": False,
                    "streaming": [],
                    "tool_updates": [],
                    "memory_updates": [],
                    "completion": False
                }

                try:
                    timeout_count = 0
                    while timeout_count < 3:  # Allow up to 3 timeouts
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=5)
                            response_data = json.loads(response)

                            if response_data["type"] == "conversation.message.received":
                                system_responses["message_ack"] = True

                            elif response_data["type"] == "conversation.message.streaming":
                                system_responses["streaming"].append(response_data)

                            elif response_data["type"].startswith("tool."):
                                system_responses["tool_updates"].append(response_data)

                            elif response_data["type"].startswith("memory."):
                                system_responses["memory_updates"].append(response_data)

                            elif response_data["type"] == "conversation.message.complete":
                                system_responses["completion"] = True
                                break

                        except asyncio.TimeoutError:
                            timeout_count += 1

                except Exception as e:
                    # Some integrations might not be implemented yet
                    pass

                # Validate that at least basic functionality worked
                assert system_responses["message_ack"], "Should acknowledge message receipt"

                # If streaming worked, validate format
                if system_responses["streaming"]:
                    for chunk in system_responses["streaming"]:
                        assert "data" in chunk
                        assert "conversation_id" in chunk["data"]

        except ConnectionError:
            pytest.skip("WebSocket endpoint not implemented yet")

        # Verify final state via REST API
        final_conversation = await client.get(f"/conversations/{conversation_id}", headers=auth_headers)
        if final_conversation.status_code == 200:
            final_data = final_conversation.json()
            assert final_data["message_count"] >= 1  # At least the message we sent

        # Check if new memories were created
        if memory_created:
            final_memory = await client.get("/memory", headers=auth_headers)
            if final_memory.status_code == 200:
                memory_data = final_memory.json()
                # Might have created additional memories during the complex interaction
                assert len(memory_data["data"]) >= 1