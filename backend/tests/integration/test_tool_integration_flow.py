"""
Integration test for complete tool integration and execution flow.

This test validates the entire tool ecosystem including discovery, execution,
chaining, error handling, and integration with conversations and memory.
According to TDD, this test MUST FAIL initially until all endpoints are implemented.
"""
import pytest
from httpx import AsyncClient
import uuid
import asyncio
import json


class TestToolIntegrationFlow:
    """Test complete tool integration and execution flow."""

    @pytest.mark.asyncio
    async def test_complete_tool_discovery_and_execution_flow(self, client: AsyncClient, auth_headers: dict):
        """Test the complete flow from tool discovery to execution and result handling."""

        # Step 1: Discover Available Tools
        # This MUST FAIL initially until all endpoints are implemented
        tools_response = await client.get("/tools", headers=auth_headers)
        assert tools_response.status_code == 200

        tools_data = tools_response.json()
        available_tools = tools_data["data"]
        assert isinstance(available_tools, list)

        if not available_tools:
            pytest.skip("No tools available for testing")

        # Find a suitable tool for testing (prefer web_search if available)
        test_tool = None
        for tool in available_tools:
            if tool["name"] in ["web_search", "file_read", "code_execute"]:
                test_tool = tool
                break

        if not test_tool:
            test_tool = available_tools[0]  # Use first available tool

        tool_id = test_tool["id"]
        tool_schema = test_tool["schema"]

        # Step 2: Validate Tool Schema
        assert "type" in tool_schema
        assert "properties" in tool_schema
        assert isinstance(tool_schema["properties"], dict)

        # Step 3: Prepare Tool Parameters
        # Create valid parameters based on tool schema
        if tool_id == "web_search":
            execution_params = {
                "query": "Python programming best practices",
                "max_results": 3
            }
        elif tool_id == "file_read":
            execution_params = {
                "path": "/tmp/test_file.txt"
            }
        elif tool_id == "code_execute":
            execution_params = {
                "code": "print('Hello from tool execution test')",
                "language": "python"
            }
        else:
            # Generic parameters for unknown tool
            execution_params = {}
            for prop_name, prop_schema in tool_schema["properties"].items():
                if prop_schema.get("type") == "string":
                    execution_params[prop_name] = "test_value"
                elif prop_schema.get("type") == "integer":
                    execution_params[prop_name] = 10
                elif prop_schema.get("type") == "boolean":
                    execution_params[prop_name] = True

        # Step 4: Execute Tool Synchronously
        execution_data = {
            "parameters": execution_params,
            "context": {
                "user_request": "Testing tool execution",
                "execution_id": str(uuid.uuid4())
            }
        }

        execute_response = await client.post(
            f"/tools/{tool_id}/execute",
            headers=auth_headers,
            json=execution_data
        )
        assert execute_response.status_code in [200, 202]

        execution_result = execute_response.json()
        assert "execution_id" in execution_result
        assert "status" in execution_result

        execution_id = execution_result["execution_id"]

        # Step 5: Handle Async Execution (if applicable)
        if execution_result["status"] in ["pending", "running"]:
            # Poll for completion
            max_attempts = 10
            for attempt in range(max_attempts):
                await asyncio.sleep(1)

                status_response = await client.get(
                    f"/tools/{tool_id}/executions/{execution_id}",
                    headers=auth_headers
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data["status"] in ["completed", "failed"]:
                        execution_result = status_data
                        break
                elif status_response.status_code == 404:
                    # Execution tracking not implemented yet
                    break

        # Step 6: Validate Execution Result
        if execution_result["status"] == "completed":
            assert "result" in execution_result
            assert execution_result["result"] is not None
        elif execution_result["status"] == "failed":
            assert "error" in execution_result
            # Failed execution is acceptable for testing

        # Step 7: Verify Execution History
        history_response = await client.get(f"/tools/{tool_id}/executions", headers=auth_headers)
        if history_response.status_code == 200:
            history_data = history_response.json()

            # Our execution should appear in history
            our_execution = None
            for execution in history_data["data"]:
                if execution["id"] == execution_id:
                    our_execution = execution
                    break

            if our_execution:
                assert our_execution["tool_id"] == tool_id
                assert our_execution["status"] in ["completed", "failed", "pending", "running"]

        # Step 8: Test Tool Integration with Conversation
        # Create conversation that uses tools
        conversation_data = {
            "title": "Tool Integration Test Conversation",
            "system_prompt": "You are an assistant that can use tools to help users."
        }

        conv_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        if conv_response.status_code == 201:
            conversation_id = conv_response.json()["id"]

            # Send message that should trigger tool usage
            tool_message_data = {
                "content": f"Please use the {test_tool['name']} tool to help me with my request.",
                "role": "user",
                "enable_tools": True,
                "preferred_tools": [tool_id]
            }

            tool_msg_response = await client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json=tool_message_data
            )

            if tool_msg_response.status_code in [200, 201]:
                msg_data = tool_msg_response.json()
                assistant_message = msg_data["assistant_message"]

                # Assistant should mention tool usage or show results
                assert len(assistant_message["content"]) > 0

                # Check for tool usage metadata
                if "metadata" in assistant_message:
                    metadata = assistant_message["metadata"]
                    if "tools_used" in metadata:
                        assert tool_id in str(metadata["tools_used"])

        return {
            "tool_id": tool_id,
            "execution_id": execution_id,
            "status": execution_result["status"],
            "conversation_id": conversation_id if 'conversation_id' in locals() else None
        }

    @pytest.mark.asyncio
    async def test_tool_chaining_and_workflow(self, client: AsyncClient, auth_headers: dict):
        """Test chaining multiple tools in a workflow."""

        # Get available tools
        tools_response = await client.get("/tools", headers=auth_headers)
        if tools_response.status_code != 200:
            pytest.skip("Tools endpoint not implemented yet")

        tools_data = tools_response.json()
        available_tools = tools_data["data"]

        if len(available_tools) < 2:
            pytest.skip("Need at least 2 tools for chaining test")

        # Select tools for chaining
        tool1 = available_tools[0]
        tool2 = available_tools[1]

        # Execute first tool
        execution1_data = {
            "parameters": {"test": "value1"},
            "context": {
                "workflow_id": str(uuid.uuid4()),
                "step": 1
            }
        }

        execute1_response = await client.post(
            f"/tools/{tool1['id']}/execute",
            headers=auth_headers,
            json=execution1_data
        )

        if execute1_response.status_code not in [200, 202]:
            pytest.skip(f"Tool {tool1['id']} execution failed")

        result1 = execute1_response.json()

        # Use result from first tool as input for second tool
        if result1["status"] == "completed" and "result" in result1:
            execution2_data = {
                "parameters": {"input_from_tool1": str(result1["result"])[:100]},  # Truncate if too long
                "context": {
                    "workflow_id": execution1_data["context"]["workflow_id"],
                    "step": 2,
                    "previous_execution_id": result1["execution_id"]
                }
            }

            execute2_response = await client.post(
                f"/tools/{tool2['id']}/execute",
                headers=auth_headers,
                json=execution2_data
            )

            if execute2_response.status_code in [200, 202]:
                result2 = execute2_response.json()

                # Verify workflow context is maintained
                if "context" in result2:
                    assert result2["context"]["workflow_id"] == execution1_data["context"]["workflow_id"]

    @pytest.mark.asyncio
    async def test_tool_error_handling_and_recovery(self, client: AsyncClient, auth_headers: dict):
        """Test tool error handling and recovery mechanisms."""

        # Get available tools
        tools_response = await client.get("/tools", headers=auth_headers)
        if tools_response.status_code != 200:
            pytest.skip("Tools endpoint not implemented yet")

        tools_data = tools_response.json()
        available_tools = tools_data["data"]

        if not available_tools:
            pytest.skip("No tools available for testing")

        test_tool = available_tools[0]

        # Test 1: Invalid Parameters
        invalid_execution_data = {
            "parameters": {
                "invalid_param": "invalid_value",
                "another_invalid": 999999
            }
        }

        error_response = await client.post(
            f"/tools/{test_tool['id']}/execute",
            headers=auth_headers,
            json=invalid_execution_data
        )

        # Should handle invalid parameters gracefully
        assert error_response.status_code in [400, 422]

        if error_response.status_code in [400, 422]:
            error_data = error_response.json()
            assert "detail" in error_data or "message" in error_data

        # Test 2: Missing Required Parameters
        empty_execution_data = {"parameters": {}}

        empty_response = await client.post(
            f"/tools/{test_tool['id']}/execute",
            headers=auth_headers,
            json=empty_execution_data
        )

        assert empty_response.status_code in [400, 422]

        # Test 3: Tool Timeout Handling
        timeout_execution_data = {
            "parameters": {"test": "timeout_test"},
            "timeout": 1  # Very short timeout
        }

        timeout_response = await client.post(
            f"/tools/{test_tool['id']}/execute",
            headers=auth_headers,
            json=timeout_execution_data
        )

        # Should handle timeout gracefully (might succeed quickly or timeout)
        assert timeout_response.status_code in [200, 202, 408, 422]

    @pytest.mark.asyncio
    async def test_tool_concurrent_execution(self, client: AsyncClient, auth_headers: dict):
        """Test concurrent tool execution and resource management."""

        # Get available tools
        tools_response = await client.get("/tools", headers=auth_headers)
        if tools_response.status_code != 200:
            pytest.skip("Tools endpoint not implemented yet")

        tools_data = tools_response.json()
        available_tools = tools_data["data"]

        if not available_tools:
            pytest.skip("No tools available for testing")

        test_tool = available_tools[0]

        # Execute multiple tool instances concurrently
        async def execute_tool_instance(instance_id: int):
            execution_data = {
                "parameters": {"instance_id": instance_id, "test": f"concurrent_test_{instance_id}"},
                "context": {"concurrent_test": True}
            }

            response = await client.post(
                f"/tools/{test_tool['id']}/execute",
                headers=auth_headers,
                json=execution_data
            )

            return response.status_code, instance_id

        # Run 3 concurrent executions
        concurrent_tasks = [
            execute_tool_instance(i) for i in range(1, 4)
        ]

        results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)

        # At least some executions should succeed
        successful_executions = [
            r for r in results
            if not isinstance(r, Exception) and r[0] in [200, 202]
        ]

        assert len(successful_executions) > 0

    @pytest.mark.asyncio
    async def test_tool_memory_integration(self, client: AsyncClient, auth_headers: dict):
        """Test tool integration with memory system."""

        # Create conversation with memory-enabled tool usage
        conversation_data = {
            "title": "Tool Memory Integration Test",
            "system_prompt": "You are an assistant that remembers tool usage patterns and results."
        }

        conv_response = await client.post("/conversations", headers=auth_headers, json=conversation_data)
        if conv_response.status_code != 201:
            pytest.skip("Conversations endpoint not implemented yet")

        conversation_id = conv_response.json()["id"]

        # Use tools in conversation that should create memories
        tool_message = {
            "content": "I frequently need to search for information about machine learning. Can you help me search for 'machine learning algorithms'?",
            "role": "user",
            "enable_tools": True,
            "create_memories": True
        }

        msg_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json=tool_message
        )

        if msg_response.status_code in [200, 201]:
            # Check if memories were created about tool usage
            memory_response = await client.get("/memory", headers=auth_headers)
            if memory_response.status_code == 200:
                memory_data = memory_response.json()

                # Look for memories related to tool usage patterns
                tool_memories = [
                    m for m in memory_data["data"]
                    if "tool" in m.get("content", "").lower() or
                       "search" in m.get("content", "").lower()
                ]

                # This is implementation-dependent, so we don't assert specific memories exist

        # Follow up with another tool request to test pattern recognition
        followup_message = {
            "content": "Can you search for 'neural networks' now?",
            "role": "user",
            "enable_tools": True
        }

        followup_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json=followup_message
        )

        if followup_response.status_code in [200, 201]:
            followup_data = followup_response.json()
            # Assistant might reference previous searches based on memory
            assert len(followup_data["assistant_message"]["content"]) > 0

    @pytest.mark.asyncio
    async def test_tool_permission_and_security(self, client: AsyncClient, auth_headers: dict):
        """Test tool permission system and security constraints."""

        # Try to access tools without authentication
        no_auth_response = await client.get("/tools")
        assert no_auth_response.status_code == 401

        # Try to execute tool without authentication
        execution_data = {"parameters": {"test": "unauthorized"}}
        no_auth_execute = await client.post("/tools/web_search/execute", json=execution_data)
        assert no_auth_execute.status_code == 401

        # With authentication, get available tools
        tools_response = await client.get("/tools", headers=auth_headers)
        if tools_response.status_code != 200:
            pytest.skip("Tools endpoint not implemented yet")

        tools_data = tools_response.json()

        # Verify all tools have proper security metadata
        for tool in tools_data["data"]:
            assert "enabled" in tool
            assert isinstance(tool["enabled"], bool)

            # Disabled tools should not be executable
            if not tool["enabled"]:
                disabled_execute = await client.post(
                    f"/tools/{tool['id']}/execute",
                    headers=auth_headers,
                    json={"parameters": {}}
                )
                assert disabled_execute.status_code in [403, 404]

        # Test execution with insufficient permissions (if applicable)
        # This would be implementation-specific based on role-based access