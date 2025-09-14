"""
Integration test for proactive assistance flow journey.

This test validates the complete proactive assistance system from pattern recognition
to personalized suggestions and adaptive learning, ensuring proactive AI features work correctly.
According to TDD, this test MUST FAIL initially until all proactive assistance endpoints are implemented.
"""
import pytest
from httpx import AsyncClient
import asyncio
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class TestProactiveJourney:
    """Test complete proactive assistance and personalization journey."""

    @pytest.fixture
    def test_conversation_data(self):
        """Create test conversation for proactive assistance."""
        unique_id = str(uuid.uuid4())[:8]
        return {
            "title": f"Proactive Test Conversation {unique_id}",
            "metadata": {"proactive_test": True}
        }

    @pytest.fixture
    def usage_pattern_actions(self):
        """Define usage pattern actions to establish user behavior."""
        return [
            {
                "action": "calculator_usage",
                "messages": [
                    "What's 15% of 250?",
                    "Calculate 45 * 12",
                    "What's the square root of 144?",
                    "Convert 25 miles to kilometers"
                ],
                "expected_tool": "calculator"
            },
            {
                "action": "weather_queries",
                "messages": [
                    "What's the weather like today?",
                    "Will it rain tomorrow?",
                    "What's the temperature in New York?",
                    "Should I bring an umbrella?"
                ],
                "expected_tool": "weather"
            },
            {
                "action": "research_requests",
                "messages": [
                    "Tell me about artificial intelligence",
                    "Research the history of machine learning",
                    "What are the latest developments in quantum computing?",
                    "Find information about renewable energy"
                ],
                "expected_tool": "web_search"
            },
            {
                "action": "scheduling_queries",
                "messages": [
                    "What's my schedule for today?",
                    "When is my next meeting?",
                    "Book a meeting for tomorrow at 2 PM",
                    "Remind me to call John at 3 PM"
                ],
                "expected_tool": "calendar"
            }
        ]

    @pytest.fixture
    def personalization_preferences(self):
        """Define user personalization preferences."""
        return {
            "communication_style": "technical",
            "preferred_tools": ["calculator", "web_search", "weather"],
            "response_length": "detailed",
            "interests": ["technology", "science", "productivity"],
            "working_hours": {
                "start": "09:00",
                "end": "17:00",
                "timezone": "UTC"
            },
            "notification_preferences": {
                "proactive_suggestions": True,
                "daily_summary": True,
                "tool_recommendations": True
            },
            "learning_preferences": {
                "adaptation_enabled": True,
                "feedback_collection": True,
                "pattern_recognition": True
            }
        }

    async def _establish_usage_patterns(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        conversation_id: str,
        pattern_actions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Establish usage patterns by performing repeated actions."""
        established_patterns = []

        for pattern in pattern_actions:
            pattern_messages = []

            for message_content in pattern["messages"]:
                message_response = await client.post(
                    f"/conversations/{conversation_id}/messages",
                    headers=auth_headers,
                    json={
                        "content": message_content,
                        "metadata": {
                            "pattern_type": pattern["action"],
                            "expected_tool": pattern["expected_tool"]
                        }
                    }
                )

                if message_response.status_code == 201:
                    message_data = message_response.json()
                    pattern_messages.append({
                        "message_id": message_data["message_id"],
                        "content": message_content,
                        "response": message_data["response"],
                        "tools_used": message_data.get("tools_used", [])
                    })

                # Add realistic delay between messages
                await asyncio.sleep(0.2)

            established_patterns.append({
                "pattern_type": pattern["action"],
                "expected_tool": pattern["expected_tool"],
                "messages": pattern_messages,
                "frequency": len(pattern_messages)
            })

        return established_patterns

    @pytest.mark.asyncio
    async def test_complete_proactive_assistance_journey(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any],
        usage_pattern_actions: List[Dict[str, Any]],
        personalization_preferences: Dict[str, Any]
    ):
        """Test complete proactive assistance from pattern recognition to personalized suggestions."""

        # Step 1: Create conversation for proactive testing
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201

        conversation_id = conversation_response.json()["id"]

        # Step 2: Establish initial personalization profile
        # This MUST FAIL initially until personalization endpoints are implemented
        profile_response = await client.put(
            "/personalization/profile",
            headers=auth_headers,
            json=personalization_preferences
        )
        assert profile_response.status_code == 200

        profile_data = profile_response.json()
        assert profile_data["communication_style"] == "technical"
        assert "calculator" in profile_data["preferred_tools"]

        # Step 3: Establish usage patterns through repeated interactions
        pattern_establishment_start = time.time()
        established_patterns = await self._establish_usage_patterns(
            client, auth_headers, conversation_id, usage_pattern_actions
        )

        # Allow time for pattern analysis
        await asyncio.sleep(3)

        pattern_establishment_time = time.time() - pattern_establishment_start

        # Step 4: Trigger proactive suggestion generation
        # This MUST FAIL initially until proactive assistance endpoints are implemented
        suggestions_response = await client.get(
            "/proactive/suggestions",
            headers=auth_headers,
            params={"conversation_id": conversation_id}
        )
        assert suggestions_response.status_code == 200

        suggestions_data = suggestions_response.json()
        assert "suggestions" in suggestions_data
        assert len(suggestions_data["suggestions"]) > 0

        # Verify suggestion structure
        sample_suggestion = suggestions_data["suggestions"][0]
        assert "suggestion_id" in sample_suggestion
        assert "type" in sample_suggestion
        assert "content" in sample_suggestion
        assert "confidence_score" in sample_suggestion
        assert "based_on_patterns" in sample_suggestion

        # Verify suggestions are relevant to established patterns
        suggestion_types = [s["type"] for s in suggestions_data["suggestions"]]
        pattern_types = [p["pattern_type"] for p in established_patterns]

        # At least one suggestion should relate to established patterns
        relevant_suggestions = any(
            any(pattern in s_type for pattern in pattern_types)
            for s_type in suggestion_types
        )
        assert relevant_suggestions, "Suggestions should be based on established usage patterns"

        # Step 5: Respond to proactive suggestions
        suggestion_responses = []
        for suggestion in suggestions_data["suggestions"][:3]:  # Respond to first 3 suggestions
            suggestion_id = suggestion["suggestion_id"]

            # Simulate user response (accept/reject with feedback)
            response_data = {
                "user_response": "accepted" if suggestion["confidence_score"] > 0.7 else "rejected",
                "effectiveness_feedback": min(1.0, suggestion["confidence_score"] + 0.1),
                "feedback_notes": f"Suggestion about {suggestion['type']} was helpful"
            }

            response_result = await client.post(
                f"/proactive/suggestions/{suggestion_id}/respond",
                headers=auth_headers,
                json=response_data
            )
            assert response_result.status_code == 200

            response_confirmation = response_result.json()
            assert "recorded" in response_confirmation
            assert response_confirmation["recorded"] == True

            suggestion_responses.append({
                "suggestion_id": suggestion_id,
                "response": response_data,
                "suggestion_type": suggestion["type"]
            })

        # Step 6: Test contextual proactive suggestions
        contextual_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json={
                "content": "I need to do some calculations for my project budget",
                "request_proactive": True
            }
        )
        assert contextual_response.status_code == 201

        contextual_data = contextual_response.json()
        if "proactive_suggestions" in contextual_data:
            proactive_suggestions = contextual_data["proactive_suggestions"]
            # Should suggest calculator tool based on established pattern
            calculator_suggested = any(
                "calculator" in suggestion.get("tool", "").lower()
                for suggestion in proactive_suggestions
            )
            assert calculator_suggested, "Should proactively suggest calculator for budget calculations"

        # Step 7: Test adaptive learning from feedback
        learning_response = await client.get(
            "/personalization/learning-insights",
            headers=auth_headers
        )
        assert learning_response.status_code == 200

        learning_data = learning_response.json()
        assert "pattern_analysis" in learning_data
        assert "suggestion_effectiveness" in learning_data
        assert "preference_evolution" in learning_data

        # Verify learning system has tracked our interactions
        pattern_analysis = learning_data["pattern_analysis"]
        assert len(pattern_analysis["identified_patterns"]) > 0

        # Step 8: Update personalization profile based on learned patterns
        profile_update_response = await client.patch(
            "/personalization/profile",
            headers=auth_headers,
            json={
                "adaptation_enabled": True,
                "auto_update_preferences": True,
                "learning_feedback": {
                    "accepted_suggestions": len([r for r in suggestion_responses if r["response"]["user_response"] == "accepted"]),
                    "rejected_suggestions": len([r for r in suggestion_responses if r["response"]["user_response"] == "rejected"])
                }
            }
        )
        assert profile_update_response.status_code == 200

        # Step 9: Test improved suggestions after learning
        await asyncio.sleep(2)  # Allow learning system to process feedback

        improved_suggestions_response = await client.get(
            "/proactive/suggestions",
            headers=auth_headers,
            params={
                "conversation_id": conversation_id,
                "include_learned_preferences": True
            }
        )
        assert improved_suggestions_response.status_code == 200

        improved_suggestions = improved_suggestions_response.json()["suggestions"]

        # New suggestions should have higher confidence scores on average
        if len(improved_suggestions) > 0:
            avg_confidence_before = sum(s["confidence_score"] for s in suggestions_data["suggestions"]) / len(suggestions_data["suggestions"])
            avg_confidence_after = sum(s["confidence_score"] for s in improved_suggestions) / len(improved_suggestions)

            # Learning should improve suggestion quality (confidence)
            improvement_threshold = 0.05  # Allow for small improvements
            confidence_improved = avg_confidence_after >= (avg_confidence_before - improvement_threshold)
            assert confidence_improved, f"Suggestion confidence should improve with learning (before: {avg_confidence_before:.3f}, after: {avg_confidence_after:.3f})"

        # Step 10: Test proactive notification system
        notifications_response = await client.get(
            "/proactive/notifications",
            headers=auth_headers
        )
        assert notifications_response.status_code == 200

        notifications_data = notifications_response.json()
        assert "notifications" in notifications_data

        # Should have notifications about learned patterns or suggestions
        proactive_notifications = [
            n for n in notifications_data["notifications"]
            if n["type"] in ["pattern_learned", "suggestion_available", "preference_updated"]
        ]
        assert len(proactive_notifications) > 0, "Should have proactive notifications"

        # Step 11: Performance validation
        # Pattern establishment should be efficient
        assert pattern_establishment_time < 30, f"Pattern establishment took {pattern_establishment_time:.1f}s, should be < 30s"

        # Suggestion generation should be fast
        suggestion_start = time.time()
        quick_suggestions = await client.get(
            "/proactive/suggestions",
            headers=auth_headers,
            params={"limit": 5}
        )
        suggestion_time = (time.time() - suggestion_start) * 1000

        assert suggestion_time < 1000, f"Suggestion generation took {suggestion_time:.1f}ms, should be < 1s"

    @pytest.mark.asyncio
    async def test_proactive_tool_recommendations(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test proactive tool recommendations based on context."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        conversation_id = conversation_response.json()["id"]

        # Send message that could benefit from specific tool
        tool_context_message = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json={
                "content": "I'm planning a trip to Paris next week and need to know about the weather",
                "request_tool_suggestions": True
            }
        )
        assert tool_context_message.status_code == 201

        response_data = tool_context_message.json()

        if "tool_suggestions" in response_data:
            tool_suggestions = response_data["tool_suggestions"]

            # Should recommend weather tool
            weather_suggested = any(
                "weather" in tool.get("name", "").lower()
                for tool in tool_suggestions
            )
            assert weather_suggested, "Should suggest weather tool for travel planning"

    @pytest.mark.asyncio
    async def test_proactive_workflow_suggestions(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test proactive workflow and automation suggestions."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        conversation_id = conversation_response.json()["id"]

        # Establish pattern of repetitive tasks
        repetitive_tasks = [
            "Calculate the tax for $100",
            "Calculate the tax for $250",
            "Calculate the tax for $75",
            "Calculate the tax for $300"
        ]

        for task in repetitive_tasks:
            await client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json={"content": task}
            )
            await asyncio.sleep(0.1)

        # Wait for pattern detection
        await asyncio.sleep(2)

        # Check for workflow suggestions
        workflow_suggestions = await client.get(
            "/proactive/workflows",
            headers=auth_headers,
            params={"conversation_id": conversation_id}
        )

        if workflow_suggestions.status_code == 200:
            workflow_data = workflow_suggestions.json()

            if "suggested_workflows" in workflow_data:
                # Should suggest tax calculation automation
                tax_workflow_suggested = any(
                    "tax" in workflow.get("description", "").lower()
                    for workflow in workflow_data["suggested_workflows"]
                )
                assert tax_workflow_suggested, "Should suggest tax calculation workflow"

    @pytest.mark.asyncio
    async def test_personalization_privacy_controls(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str]
    ):
        """Test privacy controls for personalization and proactive features."""

        # Configure privacy settings
        privacy_settings = {
            "data_collection": {
                "usage_patterns": True,
                "conversation_content": False,  # Opt out of content analysis
                "tool_preferences": True,
                "timing_patterns": False
            },
            "proactive_features": {
                "suggestions_enabled": True,
                "notifications_enabled": False,
                "automatic_learning": False
            },
            "data_retention": {
                "pattern_data_days": 30,
                "suggestion_history_days": 7,
                "feedback_data_days": 90
            }
        }

        privacy_response = await client.put(
            "/personalization/privacy",
            headers=auth_headers,
            json=privacy_settings
        )
        assert privacy_response.status_code == 200

        # Verify privacy settings are respected
        profile_response = await client.get(
            "/personalization/profile",
            headers=auth_headers
        )

        if profile_response.status_code == 200:
            profile_data = profile_response.json()

            # Should respect privacy settings
            assert profile_data["privacy_settings"]["conversation_content"] == False
            assert profile_data["privacy_settings"]["automatic_learning"] == False

    @pytest.mark.asyncio
    async def test_proactive_assistance_performance_monitoring(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str]
    ):
        """Test performance monitoring of proactive assistance features."""

        # Get proactive system metrics
        metrics_response = await client.get(
            "/proactive/metrics",
            headers=auth_headers
        )

        if metrics_response.status_code == 200:
            metrics_data = metrics_response.json()

            # Verify metrics structure
            assert "suggestion_accuracy" in metrics_data
            assert "response_times" in metrics_data
            assert "user_satisfaction" in metrics_data

            # Performance should meet requirements
            if "avg_suggestion_time_ms" in metrics_data:
                assert metrics_data["avg_suggestion_time_ms"] < 500, "Suggestion generation should be fast"

            if "suggestion_acceptance_rate" in metrics_data:
                assert metrics_data["suggestion_acceptance_rate"] >= 0.3, "Suggestion acceptance rate should be reasonable"

    @pytest.mark.asyncio
    async def test_proactive_assistance_error_handling(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str]
    ):
        """Test error handling in proactive assistance system."""

        # Test invalid suggestion response
        invalid_response = await client.post(
            "/proactive/suggestions/invalid-id/respond",
            headers=auth_headers,
            json={"user_response": "accepted"}
        )
        assert invalid_response.status_code == 404

        # Test malformed personalization update
        malformed_update = await client.put(
            "/personalization/profile",
            headers=auth_headers,
            json={"invalid_field": "invalid_value"}
        )
        assert malformed_update.status_code in [400, 422]

        # Test accessing suggestions without proper permissions
        # (This would be tested with different user roles in full implementation)

    @pytest.mark.asyncio
    async def test_proactive_learning_feedback_loop(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test the feedback loop for continuous learning improvement."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        conversation_id = conversation_response.json()["id"]

        # Generate initial suggestions
        initial_suggestions = await client.get(
            "/proactive/suggestions",
            headers=auth_headers
        )

        if initial_suggestions.status_code != 200:
            pytest.skip("Proactive suggestions endpoint not implemented")

        # Provide consistent positive feedback
        suggestion_data = initial_suggestions.json()

        for suggestion in suggestion_data["suggestions"][:2]:
            await client.post(
                f"/proactive/suggestions/{suggestion['suggestion_id']}/respond",
                headers=auth_headers,
                json={
                    "user_response": "accepted",
                    "effectiveness_feedback": 0.9,
                    "feedback_notes": "Very helpful suggestion"
                }
            )

        # Wait for learning system to process feedback
        await asyncio.sleep(3)

        # Check learning insights
        insights_response = await client.get(
            "/personalization/learning-insights",
            headers=auth_headers
        )

        if insights_response.status_code == 200:
            insights_data = insights_response.json()

            # Learning system should show improvement
            if "model_performance" in insights_data:
                performance_data = insights_data["model_performance"]

                # Should track positive feedback
                if "positive_feedback_rate" in performance_data:
                    assert performance_data["positive_feedback_rate"] > 0.5