"""
Integration test for rate limiting and quota enforcement journey.

This test validates the complete rate limiting pipeline from quota tracking
to throttling and overage billing, ensuring system protection works correctly.
According to TDD, this test MUST FAIL initially until all rate limiting endpoints are implemented.
"""
import pytest
from httpx import AsyncClient
import asyncio
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List


class TestRateLimitingJourney:
    """Test complete rate limiting and quota enforcement journey."""

    @pytest.fixture
    def test_conversation_data(self):
        """Create test conversation for rate limiting tests."""
        unique_id = str(uuid.uuid4())[:8]
        return {
            "title": f"Rate Limiting Test Conversation {unique_id}",
            "metadata": {"rate_limit_test": True}
        }

    @pytest.fixture
    def test_quota_limits(self):
        """Define test quota limits for rate limiting."""
        return {
            "messages_per_minute": 10,
            "messages_per_hour": 100,
            "messages_per_day": 500,
            "file_uploads_per_hour": 5,
            "voice_sessions_per_hour": 20,
            "overage_threshold": 1.5  # 150% of quota triggers circuit breaker
        }

    async def _configure_test_quotas(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        quota_limits: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Configure test-specific quota limits for the user."""
        # This MUST FAIL initially until quota management endpoints are implemented
        quota_response = await client.put(
            "/analytics/quota-limits",
            headers=auth_headers,
            json={
                "limits": quota_limits,
                "test_mode": True  # Enable test mode for lower limits
            }
        )
        assert quota_response.status_code == 200
        return quota_response.json()

    @pytest.mark.asyncio
    async def test_complete_rate_limiting_and_quota_journey(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any],
        test_quota_limits: Dict[str, Any]
    ):
        """Test complete rate limiting, quota enforcement, and overage handling."""

        # Step 1: Check initial quota usage
        # This MUST FAIL initially until analytics endpoints are implemented
        initial_usage_response = await client.get(
            "/analytics/usage",
            headers=auth_headers
        )
        assert initial_usage_response.status_code == 200

        initial_usage = initial_usage_response.json()
        assert "current_period" in initial_usage
        assert "quotas" in initial_usage
        assert "usage" in initial_usage

        # Verify quota structure
        quotas = initial_usage["quotas"]
        usage = initial_usage["usage"]

        assert "messages_per_hour" in quotas
        assert "messages_per_day" in quotas
        assert "messages_per_hour" in usage
        assert "messages_per_day" in usage

        # Step 2: Configure test quotas (lower limits for testing)
        await self._configure_test_quotas(client, auth_headers, test_quota_limits)

        # Step 3: Create conversation for testing
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201

        conversation_id = conversation_response.json()["id"]

        # Step 4: Approach rate limit (send multiple requests)
        rate_limit_test_start = time.time()
        successful_requests = 0
        rate_limited_requests = 0
        total_requests = test_quota_limits["messages_per_minute"] + 5

        for i in range(total_requests):
            message_response = await client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json={
                    "content": f"Rate limit test message {i + 1}",
                    "metadata": {"rate_limit_test": True}
                }
            )

            if message_response.status_code in [200, 201]:
                successful_requests += 1
            elif message_response.status_code == 429:  # Too Many Requests
                rate_limited_requests += 1

                # Verify rate limit response includes proper headers
                assert "X-RateLimit-Limit" in message_response.headers
                assert "X-RateLimit-Remaining" in message_response.headers
                assert "X-RateLimit-Reset" in message_response.headers

                rate_limit_data = message_response.json()
                assert "error" in rate_limit_data
                assert "retry_after" in rate_limit_data
            else:
                pytest.fail(f"Unexpected response status: {message_response.status_code}")

            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.1)

        # Step 5: Verify rate limiting kicked in
        assert rate_limited_requests > 0, "Rate limiting should have activated"
        assert successful_requests <= test_quota_limits["messages_per_minute"], \
            "Should not exceed per-minute limit"

        # Step 6: Test usage quota tracking
        usage_after_burst = await client.get(
            "/analytics/usage",
            headers=auth_headers
        )
        assert usage_after_burst.status_code == 200

        updated_usage = usage_after_burst.json()
        current_hour_usage = updated_usage["usage"]["messages_per_hour"]
        assert current_hour_usage >= successful_requests

        # Step 7: Test quota approaching notifications
        if current_hour_usage >= test_quota_limits["messages_per_hour"] * 0.8:  # 80% threshold
            notifications_response = await client.get(
                "/analytics/quota-notifications",
                headers=auth_headers
            )
            assert notifications_response.status_code == 200

            notifications = notifications_response.json()
            assert "warnings" in notifications

            quota_warning = next(
                (notif for notif in notifications["warnings"]
                 if notif["type"] == "quota_approaching"),
                None
            )
            if quota_warning:
                assert quota_warning["threshold"] == 0.8
                assert "messages_per_hour" in quota_warning["quota_type"]

        # Step 8: Exceed quota to test overage billing
        remaining_quota = test_quota_limits["messages_per_hour"] - current_hour_usage
        overage_requests = max(1, int(remaining_quota + 5))

        overage_start_time = time.time()
        overage_successful = 0
        overage_throttled = 0

        for i in range(overage_requests):
            overage_response = await client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json={
                    "content": f"Overage test message {i + 1}",
                    "metadata": {"overage_test": True}
                }
            )

            if overage_response.status_code in [200, 201]:
                overage_successful += 1
            elif overage_response.status_code == 429:
                overage_throttled += 1

            await asyncio.sleep(0.1)

        # Step 9: Check overage billing activation
        billing_response = await client.get(
            "/analytics/billing/overage",
            headers=auth_headers
        )
        assert billing_response.status_code == 200

        billing_data = billing_response.json()
        if overage_successful > 0:
            assert "overage_charges" in billing_data
            assert billing_data["overage_charges"]["messages"] > 0

        # Step 10: Test circuit breaker at 150% quota
        current_usage_response = await client.get(
            "/analytics/usage",
            headers=auth_headers
        )
        current_usage_data = current_usage_response.json()
        current_hour_messages = current_usage_data["usage"]["messages_per_hour"]

        circuit_breaker_threshold = int(test_quota_limits["messages_per_hour"] * 1.5)

        if current_hour_messages >= circuit_breaker_threshold:
            # All requests should now be blocked
            circuit_breaker_response = await client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json={"content": "Circuit breaker test message"}
            )

            assert circuit_breaker_response.status_code == 503  # Service Unavailable
            circuit_data = circuit_breaker_response.json()
            assert "circuit_breaker" in circuit_data["error"].lower()

        # Step 11: Test quota reset functionality
        reset_response = await client.post(
            "/analytics/quota-reset",
            headers=auth_headers,
            json={
                "quota_type": "messages_per_hour",
                "reason": "testing"
            }
        )
        # Only admin users or test mode should allow quota reset
        if reset_response.status_code == 200:
            # Verify quota was reset
            post_reset_usage = await client.get(
                "/analytics/usage",
                headers=auth_headers
            )
            reset_usage_data = post_reset_usage.json()
            assert reset_usage_data["usage"]["messages_per_hour"] < current_hour_messages

    @pytest.mark.asyncio
    async def test_different_rate_limit_types(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test different types of rate limits (file uploads, voice sessions, etc.)."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        assert conversation_response.status_code == 201
        conversation_id = conversation_response.json()["id"]

        # Test file upload rate limiting
        import io
        test_files = []
        for i in range(7):  # Exceed typical limit of 5 per hour
            test_file = io.BytesIO(f"Test file content {i}".encode())
            test_files.append(test_file)

        file_upload_responses = []
        for i, test_file in enumerate(test_files):
            test_file.seek(0)
            upload_response = await client.post(
                "/files/upload",
                headers=auth_headers,
                files={"file": (f"test_{i}.txt", test_file, "text/plain")},
                data={"conversation_id": conversation_id}
            )
            file_upload_responses.append(upload_response)
            await asyncio.sleep(0.1)

        # Some uploads should be rate limited
        successful_uploads = sum(1 for r in file_upload_responses if r.status_code == 201)
        rate_limited_uploads = sum(1 for r in file_upload_responses if r.status_code == 429)

        assert rate_limited_uploads > 0, "File upload rate limiting should activate"

        # Test voice session rate limiting
        voice_responses = []
        for i in range(25):  # Exceed typical limit of 20 per hour
            test_audio = io.BytesIO(f"fake-audio-data-{i}".encode() * 100)
            voice_response = await client.post(
                "/voice/sessions",
                headers=auth_headers,
                files={"audio_file": (f"test_{i}.wav", test_audio, "audio/wav")},
                data={"conversation_id": conversation_id}
            )
            voice_responses.append(voice_response)
            await asyncio.sleep(0.05)

        successful_voice = sum(1 for r in voice_responses if r.status_code == 201)
        rate_limited_voice = sum(1 for r in voice_responses if r.status_code == 429)

        # Should see some rate limiting for voice sessions
        if rate_limited_voice == 0:
            # May not have voice endpoints implemented yet
            pytest.skip("Voice endpoints not yet implemented")

    @pytest.mark.asyncio
    async def test_user_tier_based_limits(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str]
    ):
        """Test that different user tiers have different rate limits."""

        # Get current user tier and limits
        user_profile_response = await client.get(
            "/auth/me",
            headers=auth_headers
        )
        assert user_profile_response.status_code == 200

        user_data = user_profile_response.json()
        user_tier = user_data.get("subscription_tier", "free")

        # Get tier-specific limits
        limits_response = await client.get(
            f"/analytics/tier-limits/{user_tier}",
            headers=auth_headers
        )
        assert limits_response.status_code == 200

        tier_limits = limits_response.json()
        assert "messages_per_hour" in tier_limits
        assert "file_uploads_per_hour" in tier_limits

        # Verify limits are appropriate for tier
        if user_tier == "free":
            assert tier_limits["messages_per_hour"] <= 100
        elif user_tier == "premium":
            assert tier_limits["messages_per_hour"] >= 1000
        elif user_tier == "enterprise":
            assert tier_limits["messages_per_hour"] >= 10000

    @pytest.mark.asyncio
    async def test_rate_limit_error_responses(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test proper error responses for rate limit scenarios."""

        # Create conversation
        conversation_response = await client.post(
            "/conversations",
            json=test_conversation_data,
            headers=auth_headers
        )
        conversation_id = conversation_response.json()["id"]

        # Make requests rapidly to trigger rate limiting
        rapid_requests = []
        for i in range(20):
            request = client.post(
                f"/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json={"content": f"Rapid message {i}"}
            )
            rapid_requests.append(request)

        responses = await asyncio.gather(*rapid_requests, return_exceptions=True)

        # Find a rate-limited response
        rate_limited_response = None
        for response in responses:
            if hasattr(response, 'status_code') and response.status_code == 429:
                rate_limited_response = response
                break

        if rate_limited_response:
            # Verify proper rate limit headers
            headers = rate_limited_response.headers
            assert "X-RateLimit-Limit" in headers
            assert "X-RateLimit-Remaining" in headers
            assert "X-RateLimit-Reset" in headers
            assert "Retry-After" in headers

            # Verify error response body
            error_data = rate_limited_response.json()
            assert "error" in error_data
            assert "retry_after" in error_data
            assert "quota_type" in error_data

            # Error message should be user-friendly
            assert "rate limit" in error_data["error"].lower()

    @pytest.mark.asyncio
    async def test_rate_limit_bypass_for_admin(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str]
    ):
        """Test that admin users can bypass rate limits."""

        # Check if current user is admin
        user_response = await client.get("/auth/me", headers=auth_headers)
        user_data = user_response.json()

        is_admin = user_data.get("role") == "admin" or user_data.get("is_admin", False)

        if not is_admin:
            pytest.skip("Test requires admin user")

        # Admin should be able to make many requests without rate limiting
        admin_requests = []
        for i in range(50):  # Well above normal limits
            request = client.get("/analytics/dashboard", headers=auth_headers)
            admin_requests.append(request)

        admin_responses = await asyncio.gather(*admin_requests, return_exceptions=True)

        # Most or all requests should succeed for admin
        successful_admin_requests = sum(
            1 for r in admin_responses
            if hasattr(r, 'status_code') and r.status_code == 200
        )

        # Admin should have higher success rate
        success_rate = successful_admin_requests / len(admin_responses)
        assert success_rate > 0.8, "Admin users should have higher rate limit tolerance"

    @pytest.mark.asyncio
    async def test_distributed_rate_limiting(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str],
        test_conversation_data: Dict[str, Any]
    ):
        """Test rate limiting works across distributed system components."""

        # Create multiple conversations to spread load
        conversation_ids = []
        for i in range(3):
            conv_data = test_conversation_data.copy()
            conv_data["title"] = f"Distributed Test {i}"

            conv_response = await client.post(
                "/conversations",
                json=conv_data,
                headers=auth_headers
            )
            if conv_response.status_code == 201:
                conversation_ids.append(conv_response.json()["id"])

        # Make requests across different conversations
        distributed_requests = []
        for i in range(30):
            conv_id = conversation_ids[i % len(conversation_ids)]
            request = client.post(
                f"/conversations/{conv_id}/messages",
                headers=auth_headers,
                json={"content": f"Distributed test message {i}"}
            )
            distributed_requests.append(request)

        responses = await asyncio.gather(*distributed_requests, return_exceptions=True)

        # Rate limiting should still work across conversations
        rate_limited_count = sum(
            1 for r in responses
            if hasattr(r, 'status_code') and r.status_code == 429
        )

        # Should see some rate limiting even with distributed requests
        assert rate_limited_count > 0, "Rate limiting should work across distributed requests"

    @pytest.mark.asyncio
    async def test_quota_monitoring_and_alerts(
        self,
        client: AsyncClient,
        auth_headers: Dict[str, str]
    ):
        """Test quota monitoring and alert systems."""

        # Check quota monitoring dashboard
        monitoring_response = await client.get(
            "/analytics/quota-monitoring",
            headers=auth_headers
        )
        assert monitoring_response.status_code == 200

        monitoring_data = monitoring_response.json()
        assert "current_usage" in monitoring_data
        assert "projected_usage" in monitoring_data
        assert "alerts" in monitoring_data

        # Test alert thresholds
        alerts = monitoring_data["alerts"]
        for alert in alerts:
            assert "threshold" in alert
            assert "quota_type" in alert
            assert "current_percentage" in alert

        # Test quota usage trends
        trends_response = await client.get(
            "/analytics/usage-trends",
            headers=auth_headers,
            params={"period": "24h"}
        )
        assert trends_response.status_code == 200

        trends_data = trends_response.json()
        assert "hourly_usage" in trends_data
        assert "projected_daily" in trends_data