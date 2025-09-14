"""
Integration test for complete voice interaction journey.

This test validates the entire voice interaction pipeline from speech input
to audio response, ensuring all voice processing components work together correctly.
According to TDD, this test MUST FAIL initially until all voice endpoints are implemented.
"""
import pytest
from httpx import AsyncClient
import asyncio
import uuid
import io
import time
from typing import Dict, Any


class TestVoiceJourney:
    """Test complete voice interaction journey end-to-end."""

    @pytest.fixture
    def sample_audio_data(self):
        """Generate mock audio data for testing."""
        # Create a minimal WAV file header for testing
        # In real implementation, would use actual audio file
        wav_header = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00'
        wav_header += b'\x01\x00\x01\x00\x22\x56\x00\x00\x44\xAC\x00\x00'
        wav_header += b'\x02\x00\x10\x00data\x00\x08\x00\x00'

        # Add some sample audio data (silence)
        audio_data = wav_header + b'\x00' * 8000  # 1 second of 8kHz silence

        return io.BytesIO(audio_data)

    @pytest.fixture
    def test_conversation_data(self):
        """Create test conversation for voice interaction."""
        unique_id = str(uuid.uuid4())[:8]
        return {
            "title": f"Voice Test Conversation {unique_id}",
            "metadata": {"voice_test": True}
        }

    @pytest.mark.asyncio
    async def test_complete_voice_interaction_journey(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        sample_audio_data: io.BytesIO,
        test_conversation_data: Dict[str, Any]
    ):
        """Test complete voice-to-voice conversation journey."""

        # Step 1: Create a conversation for voice interaction
        # This MUST FAIL initially until conversation endpoints are implemented
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201

        conversation_data = conversation_response.json()
        conversation_id = conversation_data["id"]

        # Step 2: Upload audio file for transcription
        # This MUST FAIL initially until voice endpoints are implemented
        audio_files = {
            "audio_file": ("test_audio.wav", sample_audio_data, "audio/wav")
        }
        audio_form_data = {
            "conversation_id": conversation_id
        }

        voice_session_response = await client.post(
            "/voice/sessions",
            headers=auth_headers,
            files=audio_files,
            data=audio_form_data
        )
        assert voice_session_response.status_code == 201

        voice_session_data = voice_session_response.json()
        session_id = voice_session_data["session_id"]

        # Verify initial session state
        assert voice_session_data["status"] == "processing"
        assert "conversation_id" in voice_session_data
        assert voice_session_data["conversation_id"] == conversation_id

        # Step 3: Poll for transcription completion
        max_wait_time = 10  # seconds
        start_time = time.time()
        transcription_completed = False

        while time.time() - start_time < max_wait_time:
            status_response = await client.get(
                f"/voice/sessions/{session_id}",
                headers=auth_headers
            )
            assert status_response.status_code == 200

            status_data = status_response.json()

            if status_data["status"] == "completed":
                transcription_completed = True

                # Verify transcription results
                assert "transcribed_text" in status_data
                assert len(status_data["transcribed_text"]) > 0
                assert "recognition_accuracy" in status_data
                assert status_data["recognition_accuracy"] >= 0.8  # Minimum accuracy threshold
                assert "processing_time_ms" in status_data

                break
            elif status_data["status"] == "error":
                pytest.fail(f"Voice transcription failed: {status_data.get('error_message', 'Unknown error')}")

            await asyncio.sleep(0.5)  # Wait before polling again

        assert transcription_completed, "Transcription did not complete within timeout"

        # Step 4: Generate AI response based on transcription
        response_generation_start = time.time()

        message_response = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=auth_headers,
            json={
                "content": status_data["transcribed_text"],
                "message_type": "voice",
                "metadata": {
                    "voice_session_id": session_id,
                    "recognition_accuracy": status_data["recognition_accuracy"]
                }
            }
        )
        assert message_response.status_code == 201

        message_data = message_response.json()
        assert "response" in message_data
        response_text = message_data["response"]["content"]

        response_generation_time = (time.time() - response_generation_start) * 1000

        # Step 5: Generate text-to-speech response
        tts_start_time = time.time()

        tts_response = await client.post(
            "/voice/text-to-speech",
            headers=auth_headers,
            json={
                "text": response_text,
                "voice_settings": {
                    "speed": 1.0,
                    "pitch": 0.0,
                    "voice_id": "default"
                },
                "conversation_id": conversation_id
            }
        )
        assert tts_response.status_code == 200

        # Verify audio response
        assert tts_response.headers["content-type"].startswith("audio/")
        audio_content = tts_response.content
        assert len(audio_content) > 0

        tts_generation_time = (time.time() - tts_start_time) * 1000

        # Step 6: Verify end-to-end latency requirements
        # Total time from transcription start to audio response
        total_processing_time = status_data["processing_time_ms"] + response_generation_time + tts_generation_time

        # Performance requirement: < 800ms end-to-end
        assert total_processing_time < 800, f"Voice processing took {total_processing_time}ms, exceeds 800ms limit"

        # Step 7: Verify session is properly tracked in analytics
        analytics_response = await client.get(
            f"/analytics/events?event_type=voice_interaction&conversation_id={conversation_id}",
            headers=auth_headers
        )
        assert analytics_response.status_code == 200

        analytics_data = analytics_response.json()
        assert len(analytics_data["events"]) > 0

        voice_event = next(
            (event for event in analytics_data["events"] if event["event_type"] == "voice_interaction"),
            None
        )
        assert voice_event is not None
        assert voice_event["metadata"]["session_id"] == session_id
        assert "processing_time_ms" in voice_event["metadata"]

    @pytest.mark.asyncio
    async def test_voice_session_error_handling(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str]
    ):
        """Test voice session error handling scenarios."""

        # Test with invalid audio format
        invalid_audio = io.BytesIO(b"not-an-audio-file")
        invalid_files = {
            "audio_file": ("test.txt", invalid_audio, "text/plain")
        }

        response = await client.post(
            "/voice/sessions",
            headers=auth_headers,
            files=invalid_files,
            data={"conversation_id": str(uuid.uuid4())}
        )

        # Should reject invalid audio formats
        assert response.status_code in [400, 422]
        error_data = response.json()
        assert "error" in error_data or "detail" in error_data

    @pytest.mark.asyncio
    async def test_voice_session_without_conversation(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        sample_audio_data: io.BytesIO
    ):
        """Test voice session creation without valid conversation."""

        audio_files = {
            "audio_file": ("test_audio.wav", sample_audio_data, "audio/wav")
        }

        # Test without conversation_id
        response = await client.post(
            "/voice/sessions",
            headers=auth_headers,
            files=audio_files
        )

        # Should require conversation_id
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_text_to_speech_rate_limiting(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str]
    ):
        """Test text-to-speech rate limiting."""

        # Make multiple rapid TTS requests
        requests = []
        for i in range(10):
            request = client.post(
                "/voice/text-to-speech",
                headers=auth_headers,
                json={
                    "text": f"Test message {i}",
                    "voice_settings": {"voice_id": "default"}
                }
            )
            requests.append(request)

        # Execute requests concurrently
        responses = await asyncio.gather(*requests, return_exceptions=True)

        # Some requests should be rate limited
        rate_limited_count = sum(
            1 for response in responses
            if hasattr(response, 'status_code') and response.status_code == 429
        )

        # Expect some rate limiting to kick in
        assert rate_limited_count > 0, "Rate limiting should prevent excessive TTS requests"

    @pytest.mark.asyncio
    async def test_voice_processing_timeout(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test voice processing timeout handling."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201
        conversation_id = conversation_response.json()["id"]

        # Create very large audio file (would timeout in processing)
        large_audio = io.BytesIO(b'RIFF' + b'\x00' * (10 * 1024 * 1024))  # 10MB of data

        audio_files = {
            "audio_file": ("large_audio.wav", large_audio, "audio/wav")
        }

        response = await client.post(
            "/voice/sessions",
            headers=auth_headers,
            files=audio_files,
            data={"conversation_id": conversation_id}
        )

        # Should either reject large files or handle timeout gracefully
        if response.status_code == 201:
            session_id = response.json()["session_id"]

            # Wait and check for timeout status
            await asyncio.sleep(2)

            status_response = await client.get(
                f"/voice/sessions/{session_id}",
                headers=auth_headers
            )

            status_data = status_response.json()
            # Should show error or timeout status
            assert status_data["status"] in ["error", "timeout"]
        else:
            # Should reject large files upfront
            assert response.status_code in [413, 422]  # Payload too large or validation error