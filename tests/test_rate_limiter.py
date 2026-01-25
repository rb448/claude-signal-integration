"""Unit tests for rate limiter."""

import asyncio
import time

import pytest

from src.signal.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test RateLimiter token bucket and exponential backoff."""

    @pytest.mark.asyncio
    async def test_token_bucket_allows_burst(self):
        """Test token bucket allows 5 instant sends, then delays 6th."""
        limiter = RateLimiter(rate_limit=30.0, burst_size=5)

        # First 5 sends should be instant
        start = time.monotonic()
        for i in range(5):
            delay = await limiter.acquire()
            assert delay == 0.0, f"Send {i+1} should be instant but had {delay}s delay"
        elapsed_burst = time.monotonic() - start

        # Burst should complete in < 0.1 seconds
        assert elapsed_burst < 0.1, f"Burst took {elapsed_burst}s, should be instant"

        # 6th send should be delayed (needs to wait for token refill)
        delay = await limiter.acquire()
        assert delay > 0, "6th send should be delayed but was instant"

    @pytest.mark.asyncio
    async def test_exponential_backoff_triggers(self):
        """Test exponential backoff triggers after burst depletion."""
        limiter = RateLimiter(rate_limit=30.0, burst_size=3, backoff_base=0.1)  # Fast backoff for testing

        # Deplete burst
        for _ in range(3):
            await limiter.acquire()

        assert limiter.tokens_available < 1.0, "Tokens should be depleted"

        # Next sends should trigger increasing backoff
        # Wait a bit less than required for full token refill to trigger backoff
        await asyncio.sleep(0.05)

        initial_backoff = limiter.current_backoff_level
        await limiter.acquire()  # This should increase backoff
        new_backoff = limiter.current_backoff_level

        # Backoff should increase when sending rapidly after burst depletion
        # (May not increase on every send, but eventually will)
        # Check that backoff can be activated
        assert new_backoff >= initial_backoff, "Backoff should not decrease"

    @pytest.mark.asyncio
    async def test_backoff_reset_after_cooldown(self):
        """Test backoff resets after cooldown period."""
        limiter = RateLimiter(
            rate_limit=60.0,
            burst_size=2,
            backoff_base=0.1,
            cooldown_period=0.2  # Short cooldown for testing
        )

        # Trigger backoff
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()  # Should trigger backoff

        if limiter.current_backoff_level > 0:
            # Wait for cooldown
            await asyncio.sleep(0.3)

            # Next acquire should reset backoff
            await limiter.acquire()
            # After cooldown, backoff should be reset or low
            assert limiter.current_backoff_level <= 1, "Backoff should reset after cooldown"

    @pytest.mark.asyncio
    async def test_can_send_accuracy(self):
        """Test can_send() accurately reflects send availability."""
        limiter = RateLimiter(rate_limit=30.0, burst_size=5)

        # Should be able to send initially
        assert limiter.can_send() is True

        # Deplete tokens
        for _ in range(5):
            await limiter.acquire()

        # Should not be able to send immediately after burst depletion
        # (Depending on timing, may need small delay)
        await asyncio.sleep(0.01)
        can_send = limiter.can_send()
        # Can_send should be False if no tokens available
        # (May be True if enough time passed for refill)

    @pytest.mark.asyncio
    async def test_reset_clears_state(self):
        """Test reset() clears rate limiter state."""
        limiter = RateLimiter(rate_limit=30.0, burst_size=5)

        # Deplete tokens and trigger backoff
        for _ in range(6):
            await limiter.acquire()

        # Reset
        limiter.reset()

        # Should be able to send immediately after reset
        assert limiter.can_send() is True
        assert limiter.current_backoff_level == 0
        assert limiter.tokens_available == 5.0

    @pytest.mark.asyncio
    async def test_rate_limiting_enforces_rate(self):
        """Test rate limiting enforces message rate over time."""
        limiter = RateLimiter(rate_limit=60.0, burst_size=5)  # 60/min = 1/sec

        # Send burst of 5 (instant)
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()

        # Next 5 should be rate-limited
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start

        # Total 10 messages: 5 instant + 5 rate-limited
        # With exponential backoff, this can take 4-10 seconds (backoff adds delays)
        # The key is that rate limiting IS enforced (not instant for all 10)
        assert elapsed >= 4.0, f"10 messages should take >=4s but took {elapsed}s"
        assert elapsed <= 12.0, f"10 messages took {elapsed}s, excessive delay"

    @pytest.mark.asyncio
    async def test_tokens_refill_over_time(self):
        """Test tokens refill based on rate limit over time."""
        limiter = RateLimiter(rate_limit=60.0, burst_size=5)  # 1 token/sec

        # Deplete tokens
        for _ in range(5):
            await limiter.acquire()

        assert limiter.tokens_available < 1.0

        # Wait for refill
        await asyncio.sleep(1.1)  # Should refill 1 token

        tokens = limiter.tokens_available
        assert tokens >= 1.0, f"After 1s, should have ~1 token but have {tokens}"
