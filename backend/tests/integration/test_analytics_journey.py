"""
Integration test for analytics dashboard journey.

This test validates the complete analytics pipeline from user action tracking
to dashboard visualization and data export, ensuring analytics capabilities work correctly.
According to TDD, this test MUST FAIL initially until all analytics endpoints are implemented.
"""
import pytest
from httpx import AsyncClient
import asyncio
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json


class TestAnalyticsJourney:
    """Test complete analytics dashboard and usage tracking journey."""

    @pytest.fixture
    def test_conversation_data(self):
        """Create test conversation for analytics tracking."""
        unique_id = str(uuid.uuid4())[:8]
        return {
            "title": f"Analytics Test Conversation {unique_id}",
            "metadata": {"analytics_test": True}
        }

    @pytest.fixture
    def sample_analytics_actions(self):
        """Define sample user actions for analytics testing."""
        return [
            {"action": "conversation_start", "metadata": {"source": "web"}},
            {"action": "message_sent", "metadata": {"message_length": 50, "has_attachment": False}},
            {"action": "tool_used", "metadata": {"tool_name": "calculator", "success": True}},
            {"action": "file_uploaded", "metadata": {"file_type": "pdf", "file_size": 1024000}},
            {"action": "voice_interaction", "metadata": {"duration_ms": 3000, "accuracy": 0.95}},
        ]

    async def _perform_tracked_actions(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        conversation_id: str,
        actions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Perform various user actions that should be tracked by analytics."""
        performed_actions = []

        for action_data in actions:
            action_type = action_data["action"]
            metadata = action_data["metadata"]

            if action_type == "conversation_start":
                # This action was already performed when creating the conversation
                performed_actions.append({
                    "action": action_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "metadata": metadata
                })

            elif action_type == "message_sent":
                # Send a message
                message_response = await client.post(
                    f"/conversations/{conversation_id}/messages",
                    headers=auth_headers,
                    json={
                        "content": "Test message for analytics tracking",
                        "metadata": metadata
                    }
                )
                if message_response.status_code == 201:
                    performed_actions.append({
                        "action": action_type,
                        "timestamp": datetime.utcnow().isoformat(),
                        "metadata": metadata
                    })

            elif action_type == "tool_used":
                # Simulate tool usage by sending a calculation request
                tool_response = await client.post(
                    f"/conversations/{conversation_id}/messages",
                    headers=auth_headers,
                    json={
                        "content": "What is 25 * 4?",
                        "metadata": {"expects_tool_use": True}
                    }
                )
                if tool_response.status_code == 201:
                    performed_actions.append({
                        "action": action_type,
                        "timestamp": datetime.utcnow().isoformat(),
                        "metadata": metadata
                    })

            elif action_type == "file_uploaded":
                # Simulate file upload
                import io
                test_file = io.BytesIO(b"Test file content for analytics")
                upload_response = await client.post(
                    "/files/upload",
                    headers=auth_headers,
                    files={"file": ("test.txt", test_file, "text/plain")},
                    data={"conversation_id": conversation_id}
                )
                if upload_response.status_code == 201:
                    performed_actions.append({
                        "action": action_type,
                        "timestamp": datetime.utcnow().isoformat(),
                        "metadata": metadata
                    })

            elif action_type == "voice_interaction":
                # Simulate voice session
                import io
                test_audio = io.BytesIO(b"fake-audio-data" * 100)
                voice_response = await client.post(
                    "/voice/sessions",
                    headers=auth_headers,
                    files={"audio_file": ("test.wav", test_audio, "audio/wav")},
                    data={"conversation_id": conversation_id}
                )
                if voice_response.status_code == 201:
                    performed_actions.append({
                        "action": action_type,
                        "timestamp": datetime.utcnow().isoformat(),
                        "metadata": metadata
                    })

            # Add delay between actions for realistic timestamps
            await asyncio.sleep(0.1)

        return performed_actions

    @pytest.mark.asyncio
    async def test_complete_analytics_dashboard_journey(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any],
        sample_analytics_actions: List[Dict[str, Any]]
    ):
        """Test complete analytics tracking, dashboard viewing, and export journey."""

        # Step 1: Create conversation to track analytics
        # This MUST FAIL initially until conversation endpoints are implemented
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201

        conversation_data = conversation_response.json()
        conversation_id = conversation_data["id"]

        # Step 2: Perform various user actions that should be tracked
        dashboard_start_time = time.time()
        performed_actions = await self._perform_tracked_actions(
            client, auth_headers, conversation_id, sample_analytics_actions
        )

        # Allow some time for analytics events to be processed
        await asyncio.sleep(2)

        # Step 3: View analytics dashboard
        # This MUST FAIL initially until analytics endpoints are implemented
        dashboard_response = await client.get(
            "/analytics/dashboard",
            headers=auth_headers,
            params={"time_range": "day"}
        )
        assert dashboard_response.status_code == 200

        dashboard_data = dashboard_response.json()
        dashboard_load_time = (time.time() - dashboard_start_time) * 1000

        # Verify dashboard structure
        assert "metrics" in dashboard_data
        assert "time_series" in dashboard_data
        assert "user_activity" in dashboard_data

        metrics = dashboard_data["metrics"]
        assert "total_conversations" in metrics
        assert "total_messages" in metrics
        assert "tool_usage_count" in metrics
        assert "file_uploads_count" in metrics

        # Verify metrics reflect our test activity
        assert metrics["total_conversations"] >= 1
        assert metrics["total_messages"] >= 1

        # Step 4: Query specific event types
        events_response = await client.get(
            "/analytics/events",
            headers=auth_headers,
            params={
                "event_type": "message_sent",
                "time_range": "day",
                "limit": 50
            }
        )
        assert events_response.status_code == 200

        events_data = events_response.json()
        assert "events" in events_data
        assert len(events_data["events"]) > 0

        # Verify event structure
        sample_event = events_data["events"][0]
        assert "event_id" in sample_event
        assert "event_type" in sample_event
        assert "timestamp" in sample_event
        assert "user_id" in sample_event
        assert "metadata" in sample_event

        # Step 5: Test conversation-specific analytics
        conversation_analytics_response = await client.get(
            f"/analytics/conversations/{conversation_id}",
            headers=auth_headers
        )
        assert conversation_analytics_response.status_code == 200

        conversation_analytics = conversation_analytics_response.json()
        assert "conversation_id" in conversation_analytics
        assert "message_count" in conversation_analytics
        assert "duration_minutes" in conversation_analytics
        assert "tools_used" in conversation_analytics

        # Step 6: Export usage data
        export_start_time = time.time()

        export_response = await client.post(
            "/analytics/export",
            headers=auth_headers,
            json={
                "format": "csv",
                "data_type": "events",
                "start_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                "end_date": datetime.utcnow().isoformat(),
                "filters": {
                    "event_types": ["message_sent", "conversation_start", "tool_used"]
                }
            }
        )
        assert export_response.status_code == 200

        export_processing_time = (time.time() - export_start_time) * 1000

        # Verify export response
        assert export_response.headers["content-type"] == "text/csv"
        export_content = export_response.content.decode('utf-8')
        assert len(export_content) > 0
        assert "event_id" in export_content  # CSV header
        assert "event_type" in export_content
        assert "timestamp" in export_content

        # Step 7: Test time-series analytics
        time_series_response = await client.get(
            "/analytics/time-series",
            headers=auth_headers,
            params={
                "metric": "message_count",
                "granularity": "hour",
                "time_range": "day"
            }
        )
        assert time_series_response.status_code == 200

        time_series_data = time_series_response.json()
        assert "data_points" in time_series_data
        assert len(time_series_data["data_points"]) > 0

        data_point = time_series_data["data_points"][0]
        assert "timestamp" in data_point
        assert "value" in data_point

        # Step 8: Verify performance requirements
        # Dashboard should load in < 2 seconds
        assert dashboard_load_time < 2000, f"Dashboard loaded in {dashboard_load_time}ms, should be < 2s"

        # Export should complete quickly for small datasets
        assert export_processing_time < 5000, f"Export took {export_processing_time}ms, should be < 5s"

        # Step 9: Test user activity tracking
        user_activity_response = await client.get(
            "/analytics/user-activity",
            headers=auth_headers,
            params={"time_range": "day"}
        )
        assert user_activity_response.status_code == 200

        user_activity = user_activity_response.json()
        assert "activity_timeline" in user_activity
        assert "peak_hours" in user_activity
        assert "session_count" in user_activity

    @pytest.mark.asyncio
    async def test_analytics_privacy_compliance(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test analytics privacy compliance and data protection."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201
        conversation_id = conversation_response.json()["id"]

        # Send message with sensitive content
        sensitive_message = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json={
                "content": "My credit card number is 4532-1234-5678-9012 and SSN is 123-45-6789",
                "metadata": {"contains_pii": True}
            }
        )
        assert sensitive_message.status_code == 201

        await asyncio.sleep(1)

        # Check that sensitive data is not exposed in analytics
        events_response = await client.get(
            "/analytics/events",
            headers=auth_headers,
            params={"event_type": "message_sent"}
        )
        assert events_response.status_code == 200

        events = events_response.json()["events"]
        for event in events:
            # Verify no sensitive data in metadata
            metadata_str = json.dumps(event.get("metadata", {})).lower()
            assert "4532-1234-5678-9012" not in metadata_str
            assert "123-45-6789" not in metadata_str

    @pytest.mark.asyncio
    async def test_real_time_analytics_updates(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test real-time analytics updates and WebSocket integration."""

        # Get initial dashboard state
        initial_dashboard = await client.get(
            "/analytics/dashboard",
            headers=auth_headers,
            params={"time_range": "hour"}
        )
        assert initial_dashboard.status_code == 200

        initial_metrics = initial_dashboard.json()["metrics"]
        initial_message_count = initial_metrics.get("total_messages", 0)

        # Create conversation and send message
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201
        conversation_id = conversation_response.json()["id"]

        message_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json={"content": "Test message for real-time analytics"}
        )
        assert message_response.status_code == 201

        # Wait for analytics to update
        await asyncio.sleep(2)

        # Check updated dashboard
        updated_dashboard = await client.get(
            "/analytics/dashboard",
            headers=auth_headers,
            params={"time_range": "hour"}
        )
        assert updated_dashboard.status_code == 200

        updated_metrics = updated_dashboard.json()["metrics"]
        updated_message_count = updated_metrics.get("total_messages", 0)

        # Verify metrics updated
        assert updated_message_count > initial_message_count

    @pytest.mark.asyncio
    async def test_analytics_filtering_and_aggregation(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test analytics filtering and aggregation capabilities."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201
        conversation_id = conversation_response.json()["id"]

        # Generate different types of events
        await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json={"content": "Calculator test", "metadata": {"tool_expected": "calculator"}}
        )

        await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json={"content": "Weather test", "metadata": {"tool_expected": "weather"}}
        )

        await asyncio.sleep(1)

        # Test filtering by event type
        tool_events = await client.get(
            "/analytics/events",
            headers=auth_headers,
            params={
                "event_type": "tool_used",
                "time_range": "hour"
            }
        )
        assert tool_events.status_code == 200

        # Test filtering by date range
        today = datetime.utcnow().date()
        date_filtered = await client.get(
            "/analytics/events",
            headers=auth_headers,
            params={
                "start_date": today.isoformat(),
                "end_date": today.isoformat()
            }
        )
        assert date_filtered.status_code == 200

        # Test aggregation by tool type
        tool_aggregation = await client.get(
            "/analytics/aggregation/tools",
            headers=auth_headers,
            params={"time_range": "day"}
        )
        assert tool_aggregation.status_code == 200

        tool_data = tool_aggregation.json()
        assert "tool_usage" in tool_data
        assert isinstance(tool_data["tool_usage"], dict)

    @pytest.mark.asyncio
    async def test_analytics_error_handling(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str]
    ):
        """Test analytics error handling scenarios."""

        # Test invalid time range
        invalid_time_response = await client.get(
            "/analytics/dashboard",
            headers=auth_headers,
            params={"time_range": "invalid"}
        )
        assert invalid_time_response.status_code in [400, 422]

        # Test invalid date format
        invalid_date_response = await client.get(
            "/analytics/events",
            headers=auth_headers,
            params={
                "start_date": "invalid-date",
                "end_date": "2025-01-01"
            }
        )
        assert invalid_date_response.status_code in [400, 422]

        # Test export with invalid format
        invalid_export = await client.post(
            "/analytics/export",
            headers=auth_headers,
            json={
                "format": "invalid_format",
                "data_type": "events"
            }
        )
        assert invalid_export.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_analytics_performance_under_load(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test analytics performance under moderate load."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201
        conversation_id = conversation_response.json()["id"]

        # Generate multiple events rapidly
        tasks = []
        for i in range(20):
            task = client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json={"content": f"Load test message {i}"}
            )
            tasks.append(task)

        # Execute requests concurrently
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Most requests should succeed
        successful_requests = sum(
            1 for response in responses
            if hasattr(response, 'status_code') and response.status_code in [200, 201]
        )
        assert successful_requests >= 15, "Most requests should succeed under moderate load"

        # Wait for analytics processing
        await asyncio.sleep(3)

        # Dashboard should still load quickly
        start_time = time.time()
        dashboard_response = await client.get(
            "/analytics/dashboard",
            headers=auth_headers,
            params={"time_range": "hour"}
        )
        load_time = (time.time() - start_time) * 1000

        assert dashboard_response.status_code == 200
        assert load_time < 3000, f"Dashboard loaded in {load_time}ms under load, should be < 3s"