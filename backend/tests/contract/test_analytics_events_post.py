"""
Contract test for POST /analytics/events endpoint.

This test validates the API contract for logging analytics events.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient
import uuid
from datetime import datetime


class TestAnalyticsEventsPostContract:
    """Test contract compliance for analytics events logging endpoint."""

    @pytest.fixture
    def sample_event_data(self):
        """Sample event data for testing."""
        return {
            "event_type": "conversation_started",
            "session_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "conversation_id": str(uuid.uuid4()),
                "model": "gpt-4",
                "source": "web_interface"
            }
        }

    @pytest.fixture
    def sample_message_event_data(self):
        """Sample message event data for testing."""
        return {
            "event_type": "message_sent",
            "session_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {
                "conversation_id": str(uuid.uuid4()),
                "message_id": str(uuid.uuid4()),
                "token_count": 150,
                "processing_time_ms": 1250,
                "model": "gpt-4",
                "role": "user"
            }
        }

    @pytest.mark.asyncio
    async def test_event_logging_success(self, client: AsyncClient, auth_headers: dict, sample_event_data: dict):
        """Test successful event logging returns 201."""
        # Act
        response = await client.post("/analytics/events", json=sample_event_data, headers=auth_headers)

        # Assert - This MUST FAIL initially (endpoint doesn't exist yet)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"

        # Validate response structure
        response_data = response.json()
        required_fields = ["event_id", "status", "timestamp", "message"]
        for field in required_fields:
            assert field in response_data, f"Missing required field: {field}"

        # Validate data types
        assert isinstance(response_data["event_id"], str)
        assert isinstance(response_data["status"], str)
        assert isinstance(response_data["timestamp"], str)
        assert isinstance(response_data["message"], str)

        # Validate status
        assert response_data["status"] == "logged"

        # Validate event_id is a valid UUID
        uuid.UUID(response_data["event_id"])

        # Validate timestamp format
        datetime.fromisoformat(response_data["timestamp"].replace('Z', '+00:00'))

    @pytest.mark.asyncio
    async def test_event_type_validation_valid_types(self, client: AsyncClient, auth_headers: dict):
        """Test that valid event types are accepted."""
        valid_event_types = [
            "conversation_started",
            "conversation_ended",
            "message_sent",
            "message_received",
            "tool_executed",
            "user_login",
            "user_logout",
            "error_occurred",
            "api_request",
            "export_generated"
        ]

        for event_type in valid_event_types:
            event_data = {
                "event_type": event_type,
                "session_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metadata": {}
            }

            # Act
            response = await client.post("/analytics/events", json=event_data, headers=auth_headers)

            # Assert
            assert response.status_code == 201, f"Event type '{event_type}' should be valid"

    @pytest.mark.asyncio
    async def test_event_type_validation_invalid_types(self, client: AsyncClient, auth_headers: dict):
        """Test that invalid event types are rejected."""
        invalid_event_types = [
            "invalid_event",
            "random_type",
            "",
            None,
            123,
            []
        ]

        for event_type in invalid_event_types:
            event_data = {
                "event_type": event_type,
                "session_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metadata": {}
            }

            # Act
            response = await client.post("/analytics/events", json=event_data, headers=auth_headers)

            # Assert
            assert response.status_code == 400, f"Event type '{event_type}' should be invalid"

            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response

    @pytest.mark.asyncio
    async def test_session_tracking(self, client: AsyncClient, auth_headers: dict):
        """Test that session_id is properly tracked and validated."""
        session_id = str(uuid.uuid4())

        # Create multiple events with same session_id
        events = [
            {
                "event_type": "conversation_started",
                "session_id": session_id,
                "user_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metadata": {}
            },
            {
                "event_type": "message_sent",
                "session_id": session_id,
                "user_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metadata": {"token_count": 50}
            }
        ]

        for event_data in events:
            # Act
            response = await client.post("/analytics/events", json=event_data, headers=auth_headers)

            # Assert
            assert response.status_code == 201
            response_data = response.json()
            assert response_data["status"] == "logged"

    @pytest.mark.asyncio
    async def test_token_count_and_processing_time(self, client: AsyncClient, auth_headers: dict, sample_message_event_data: dict):
        """Test that token count and processing time are properly logged."""
        # Act
        response = await client.post("/analytics/events", json=sample_message_event_data, headers=auth_headers)

        # Assert
        assert response.status_code == 201

        # Validate that metadata was accepted
        response_data = response.json()
        assert response_data["status"] == "logged"

        # Test with various token counts and processing times
        test_cases = [
            {"token_count": 1, "processing_time_ms": 100},
            {"token_count": 1000, "processing_time_ms": 5000},
            {"token_count": 0, "processing_time_ms": 0},
        ]

        for case in test_cases:
            event_data = sample_message_event_data.copy()
            event_data["metadata"].update(case)

            response = await client.post("/analytics/events", json=event_data, headers=auth_headers)
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_event_without_auth_unauthorized(self, client: AsyncClient, sample_event_data: dict):
        """Test event logging without authentication returns 401."""
        # Act
        response = await client.post("/analytics/events", json=sample_event_data)

        # Assert
        assert response.status_code == 401
        error_response = response.json()
        assert "error" in error_response
        assert error_response["error"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_event_invalid_token_unauthorized(self, client: AsyncClient, sample_event_data: dict):
        """Test event logging with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.post("/analytics/events", json=sample_event_data, headers=invalid_headers)

        # Assert
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_event_validation_errors(self, client: AsyncClient, auth_headers: dict):
        """Test validation error responses for malformed events."""
        validation_test_cases = [
            # Missing required fields
            {
                "data": {"event_type": "test_event"},
                "description": "missing session_id and user_id"
            },
            {
                "data": {
                    "event_type": "test_event",
                    "session_id": str(uuid.uuid4())
                },
                "description": "missing user_id"
            },
            {
                "data": {
                    "event_type": "test_event",
                    "user_id": str(uuid.uuid4())
                },
                "description": "missing session_id"
            },
            # Invalid UUIDs
            {
                "data": {
                    "event_type": "test_event",
                    "session_id": "invalid-uuid",
                    "user_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "metadata": {}
                },
                "description": "invalid session_id format"
            },
            {
                "data": {
                    "event_type": "test_event",
                    "session_id": str(uuid.uuid4()),
                    "user_id": "invalid-uuid",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "metadata": {}
                },
                "description": "invalid user_id format"
            },
            # Invalid timestamp
            {
                "data": {
                    "event_type": "test_event",
                    "session_id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                    "timestamp": "invalid-timestamp",
                    "metadata": {}
                },
                "description": "invalid timestamp format"
            },
            # Invalid metadata
            {
                "data": {
                    "event_type": "test_event",
                    "session_id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "metadata": "not-an-object"
                },
                "description": "metadata should be an object"
            }
        ]

        for test_case in validation_test_cases:
            # Act
            response = await client.post("/analytics/events", json=test_case["data"], headers=auth_headers)

            # Assert
            assert response.status_code == 400, f"Expected 400 for {test_case['description']}, got {response.status_code}"

            error_response = response.json()
            assert "error" in error_response
            assert "message" in error_response

    @pytest.mark.asyncio
    async def test_event_empty_request_body(self, client: AsyncClient, auth_headers: dict):
        """Test empty request body returns validation error."""
        # Act
        response = await client.post("/analytics/events", json={}, headers=auth_headers)

        # Assert
        assert response.status_code == 400
        error_response = response.json()
        assert "error" in error_response

    @pytest.mark.asyncio
    async def test_event_batch_logging(self, client: AsyncClient, auth_headers: dict):
        """Test batch event logging (if supported)."""
        # Arrange
        batch_events = [
            {
                "event_type": "conversation_started",
                "session_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metadata": {}
            },
            {
                "event_type": "message_sent",
                "session_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metadata": {"token_count": 100}
            }
        ]

        # Act - Try batch endpoint if it exists
        response = await client.post("/analytics/events/batch", json={"events": batch_events}, headers=auth_headers)

        # Assert - Either batch endpoint exists or individual events work
        assert response.status_code in [201, 404]  # 404 if batch endpoint doesn't exist

        if response.status_code == 201:
            response_data = response.json()
            assert "events_logged" in response_data
            assert response_data["events_logged"] == len(batch_events)

    @pytest.mark.asyncio
    async def test_event_response_headers(self, client: AsyncClient, auth_headers: dict, sample_event_data: dict):
        """Test event logging response includes correct headers."""
        # Act
        response = await client.post("/analytics/events", json=sample_event_data, headers=auth_headers)

        # Assert
        assert response.status_code == 201
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_event_metadata_flexibility(self, client: AsyncClient, auth_headers: dict):
        """Test that metadata accepts flexible structure."""
        # Test with various metadata structures
        metadata_test_cases = [
            {},  # Empty metadata
            {"simple": "value"},  # Simple key-value
            {"nested": {"key": "value", "number": 123}},  # Nested object
            {"array": [1, 2, 3]},  # Array value
            {"mixed": {"string": "value", "number": 42, "boolean": True}},  # Mixed types
        ]

        for metadata in metadata_test_cases:
            event_data = {
                "event_type": "test_event",
                "session_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metadata": metadata
            }

            # Act
            response = await client.post("/analytics/events", json=event_data, headers=auth_headers)

            # Assert
            assert response.status_code == 201, f"Failed for metadata: {metadata}"

    @pytest.mark.asyncio
    async def test_event_timestamp_default(self, client: AsyncClient, auth_headers: dict):
        """Test that timestamp is auto-generated if not provided."""
        # Arrange - Event without timestamp
        event_data = {
            "event_type": "test_event",
            "session_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "metadata": {}
        }

        # Act
        response = await client.post("/analytics/events", json=event_data, headers=auth_headers)

        # Assert
        assert response.status_code == 201
        response_data = response.json()

        # Timestamp should be included in response
        assert "timestamp" in response_data
        datetime.fromisoformat(response_data["timestamp"].replace('Z', '+00:00'))

    @pytest.mark.asyncio
    async def test_event_duplicate_handling(self, client: AsyncClient, auth_headers: dict, sample_event_data: dict):
        """Test handling of duplicate events."""
        # Act - Send same event twice
        response1 = await client.post("/analytics/events", json=sample_event_data, headers=auth_headers)
        response2 = await client.post("/analytics/events", json=sample_event_data, headers=auth_headers)

        # Assert - Both should succeed (or implement deduplication)
        assert response1.status_code == 201
        assert response2.status_code in [201, 409]  # 201 if allowed, 409 if duplicate detected

        if response2.status_code == 201:
            # Different event IDs for separate logging
            assert response1.json()["event_id"] != response2.json()["event_id"]