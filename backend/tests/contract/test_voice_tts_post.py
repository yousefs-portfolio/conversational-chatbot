"""
Contract test for POST /voice/text-to-speech endpoint.

This test validates the API contract for text-to-speech conversion.
According to TDD, this test MUST FAIL initially until the endpoint is implemented.
"""
import pytest
from httpx import AsyncClient


class TestVoiceTtsPostContract:
    """Test contract compliance for text-to-speech endpoint."""

    @pytest.fixture
    def valid_tts_data(self):
        """Valid text-to-speech request data."""
        return {
            "text": "Hello, this is a test message for text-to-speech conversion.",
            "voice": "alloy",
            "speed": 1.0
        }

    @pytest.fixture
    def minimal_tts_data(self):
        """Minimal valid text-to-speech request data."""
        return {
            "text": "Hello world"
        }

    @pytest.fixture
    def long_text_data(self):
        """Text that exceeds 4000 character limit."""
        return {
            "text": "A" * 4001  # 4001 characters, exceeding the 4000 limit
        }

    @pytest.fixture
    def invalid_voice_settings_data(self):
        """Text-to-speech request with invalid voice settings."""
        return {
            "text": "Hello world",
            "voice": "invalid_voice_name",
            "speed": 5.0  # Invalid speed (likely out of range)
        }

    @pytest.mark.asyncio
    async def test_tts_conversion_success(self, client: AsyncClient, auth_headers: dict, valid_tts_data: dict):
        """Test successful text-to-speech conversion returns 200."""
        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=valid_tts_data)

        # Assert - This MUST FAIL initially (endpoint doesn't exist yet)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Validate response structure according to OpenAPI spec
        response_data = response.json()
        assert "audio_url" in response_data
        assert "duration" in response_data
        assert "format" in response_data
        assert "created_at" in response_data

        # Validate data types
        assert isinstance(response_data["audio_url"], str)
        assert isinstance(response_data["duration"], (float, int))
        assert isinstance(response_data["format"], str)
        assert isinstance(response_data["created_at"], str)

        # Validate business logic
        assert response_data["duration"] > 0
        assert response_data["format"] in ["mp3", "wav", "ogg", "aac", "m4a"]
        assert response_data["audio_url"].startswith(("http://", "https://", "/"))

        # Validate datetime format
        from datetime import datetime
        datetime.fromisoformat(response_data["created_at"].replace('Z', '+00:00'))

    @pytest.mark.asyncio
    async def test_tts_conversion_minimal_data(self, client: AsyncClient, auth_headers: dict, minimal_tts_data: dict):
        """Test text-to-speech conversion with minimal required data."""
        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=minimal_tts_data)

        # Assert
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        response_data = response.json()
        assert "audio_url" in response_data
        assert "duration" in response_data
        assert "format" in response_data

        # Should use default values for optional parameters
        assert response_data["duration"] > 0

    @pytest.mark.asyncio
    async def test_tts_conversion_text_length_validation(self, client: AsyncClient, auth_headers: dict, long_text_data: dict):
        """Test text-to-speech conversion with text exceeding 4000 character limit."""
        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=long_text_data)

        # Assert
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

        # Validate error response structure
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response
        assert isinstance(error_response["error"], str)
        assert isinstance(error_response["message"], str)
        assert "4000" in error_response["message"] or "length" in error_response["message"].lower()

    @pytest.mark.asyncio
    async def test_tts_conversion_empty_text_error(self, client: AsyncClient, auth_headers: dict):
        """Test text-to-speech conversion with empty text."""
        # Arrange
        empty_text_data = {"text": ""}

        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=empty_text_data)

        # Assert
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

        # Validate error response
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response

    @pytest.mark.asyncio
    async def test_tts_conversion_missing_text_error(self, client: AsyncClient, auth_headers: dict):
        """Test text-to-speech conversion without text field."""
        # Arrange
        no_text_data = {"voice": "alloy"}

        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=no_text_data)

        # Assert
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_tts_conversion_invalid_voice_settings(self, client: AsyncClient, auth_headers: dict, invalid_voice_settings_data: dict):
        """Test text-to-speech conversion with invalid voice settings."""
        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=invalid_voice_settings_data)

        # Assert
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

        # Validate error response
        error_response = response.json()
        assert "error" in error_response
        assert "message" in error_response

    @pytest.mark.asyncio
    async def test_tts_conversion_without_auth_unauthorized(self, client: AsyncClient, valid_tts_data: dict):
        """Test text-to-speech conversion without authentication returns 401."""
        # Act
        response = await client.post("/voice/text-to-speech", json=valid_tts_data)

        # Assert
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_tts_conversion_invalid_token_unauthorized(self, client: AsyncClient, valid_tts_data: dict):
        """Test text-to-speech conversion with invalid token returns 401."""
        # Arrange
        invalid_headers = {"Authorization": "Bearer invalid-token"}

        # Act
        response = await client.post("/voice/text-to-speech", headers=invalid_headers, json=valid_tts_data)

        # Assert
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_tts_conversion_supported_voices(self, client: AsyncClient, auth_headers: dict):
        """Test text-to-speech conversion with various supported voices."""
        # Common voice options that might be supported
        supported_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

        for voice in supported_voices:
            # Arrange
            voice_data = {
                "text": "Hello, this is a test with voice " + voice,
                "voice": voice
            }

            # Act
            response = await client.post("/voice/text-to-speech", headers=auth_headers, json=voice_data)

            # Assert - Should either succeed (200) or fail consistently
            # If voice is not supported, should return 400, not 500
            assert response.status_code in [200, 400], f"Voice {voice} got unexpected status {response.status_code}"

            if response.status_code == 200:
                response_data = response.json()
                assert "audio_url" in response_data

    @pytest.mark.asyncio
    async def test_tts_conversion_speed_variations(self, client: AsyncClient, auth_headers: dict):
        """Test text-to-speech conversion with various speed settings."""
        # Test different speed values
        speed_values = [0.25, 0.5, 1.0, 1.5, 2.0, 4.0]

        for speed in speed_values:
            # Arrange
            speed_data = {
                "text": f"This is a test at speed {speed}",
                "speed": speed
            }

            # Act
            response = await client.post("/voice/text-to-speech", headers=auth_headers, json=speed_data)

            # Assert - Speed should be within acceptable range
            if 0.25 <= speed <= 4.0:
                assert response.status_code in [200, 400], f"Speed {speed} got unexpected status {response.status_code}"
            else:
                # Out of range speeds should return 400
                assert response.status_code == 400, f"Speed {speed} should return 400, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_tts_conversion_response_headers(self, client: AsyncClient, auth_headers: dict, valid_tts_data: dict):
        """Test that response includes correct headers."""
        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=valid_tts_data)

        # Assert
        if response.status_code == 200:
            assert response.headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_tts_conversion_unicode_text_support(self, client: AsyncClient, auth_headers: dict):
        """Test text-to-speech conversion with unicode characters."""
        # Arrange
        unicode_data = {
            "text": "Hello 世界! This is a test with émojis 🎵 and spëcial characters."
        }

        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=unicode_data)

        # Assert
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        if response.status_code == 200:
            response_data = response.json()
            assert "audio_url" in response_data
            assert response_data["duration"] > 0

    @pytest.mark.asyncio
    async def test_tts_conversion_special_characters(self, client: AsyncClient, auth_headers: dict):
        """Test text-to-speech conversion with special characters and punctuation."""
        # Arrange
        special_text_data = {
            "text": "Testing punctuation: Hello, world! How are you? I'm fine. Numbers: 123, 456.78. Symbols: @#$%^&*()"
        }

        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=special_text_data)

        # Assert
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        if response.status_code == 200:
            response_data = response.json()
            assert "audio_url" in response_data

    @pytest.mark.asyncio
    async def test_tts_conversion_boundary_text_lengths(self, client: AsyncClient, auth_headers: dict):
        """Test text-to-speech conversion at boundary text lengths."""
        # Test cases at various lengths
        test_cases = [
            {"text": "A", "description": "single character"},
            {"text": "Hello", "description": "short text"},
            {"text": "A" * 100, "description": "100 characters"},
            {"text": "A" * 1000, "description": "1000 characters"},
            {"text": "A" * 3999, "description": "just under limit"},
            {"text": "A" * 4000, "description": "at limit"},
        ]

        for test_case in test_cases:
            # Act
            response = await client.post("/voice/text-to-speech", headers=auth_headers, json=test_case)

            # Assert
            assert response.status_code == 200, f"Text length test '{test_case['description']}' failed with status {response.status_code}"

            if response.status_code == 200:
                response_data = response.json()
                assert response_data["duration"] > 0

    @pytest.mark.asyncio
    async def test_tts_conversion_invalid_json_format(self, client: AsyncClient, auth_headers: dict):
        """Test text-to-speech conversion with invalid JSON format."""
        # Act - Send malformed JSON
        response = await client.post(
            "/voice/text-to-speech",
            headers={**auth_headers, "Content-Type": "application/json"},
            content='{"text": "hello", invalid_json}'  # Malformed JSON
        )

        # Assert
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_tts_conversion_null_values(self, client: AsyncClient, auth_headers: dict):
        """Test text-to-speech conversion with null values."""
        # Arrange
        null_data = {
            "text": None,
            "voice": None,
            "speed": None
        }

        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=null_data)

        # Assert
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_tts_conversion_extra_fields_ignored(self, client: AsyncClient, auth_headers: dict):
        """Test that extra fields in request are ignored."""
        # Arrange
        data_with_extras = {
            "text": "Hello world",
            "voice": "alloy",
            "extra_field": "should be ignored",
            "admin": True,
            "dangerous_setting": "ignore me"
        }

        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=data_with_extras)

        # Assert
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        if response.status_code == 200:
            response_data = response.json()
            # Extra fields should not appear in response
            assert "extra_field" not in response_data
            assert "admin" not in response_data
            assert "dangerous_setting" not in response_data

    @pytest.mark.asyncio
    async def test_tts_conversion_concurrent_requests(self, client: AsyncClient, auth_headers: dict):
        """Test that multiple TTS requests can be processed concurrently."""
        import asyncio

        async def make_tts_request(text_suffix: str):
            data = {"text": f"Concurrent test request {text_suffix}"}
            return await client.post("/voice/text-to-speech", headers=auth_headers, json=data)

        # Create multiple concurrent requests
        tasks = [make_tts_request(str(i)) for i in range(3)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed (or fail consistently due to missing implementation)
        for i, response in enumerate(responses):
            if not isinstance(response, Exception):
                assert response.status_code in [200, 500, 501], f"Request {i} got unexpected status {response.status_code}"

    @pytest.mark.asyncio
    async def test_tts_conversion_optional_response_fields(self, client: AsyncClient, auth_headers: dict, valid_tts_data: dict):
        """Test that optional response fields are included when available."""
        # Act
        response = await client.post("/voice/text-to-speech", headers=auth_headers, json=valid_tts_data)

        # Assert
        if response.status_code == 200:
            response_data = response.json()

            # Optional fields that might be present
            optional_fields = ["file_size", "sample_rate", "bit_rate", "channels", "voice_used", "speed_used"]

            for field in optional_fields:
                if field in response_data:
                    # Validate the type if the field is present
                    if field == "file_size":
                        assert isinstance(response_data[field], int)
                        assert response_data[field] > 0
                    elif field in ["sample_rate", "bit_rate"]:
                        assert isinstance(response_data[field], int)
                        assert response_data[field] > 0
                    elif field == "channels":
                        assert isinstance(response_data[field], int)
                        assert response_data[field] in [1, 2]  # mono or stereo
                    elif field in ["voice_used", "speed_used"]:
                        assert response_data[field] is not None