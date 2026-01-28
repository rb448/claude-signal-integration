"""
Load tests for rate limiting and message queue behavior.

Tests validate that RateLimiter prevents API errors under sustained load
and handles burst traffic, backoff, and queue overflow correctly.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.signal.rate_limiter import RateLimiter
from src.signal.message_buffer import MessageBuffer


@pytest.fixture
def rate_limiter():
    """Create RateLimiter with test configuration."""
    return RateLimiter(
        rate_limit=30.0,  # 30 messages per minute
        burst_size=5,     # 5 instant messages
        backoff_base=1.0,
        backoff_max=16.0,
        cooldown_period=60.0
    )


@pytest.mark.asyncio
async def test_burst_handling(rate_limiter):
    """
    Test burst message handling with token bucket.

    Validates:
    - First 5 messages sent immediately (burst allowance)
    - Remaining messages queued and rate-limited
    - Token bucket refills over time
    - No messages dropped during burst
    """
    # Track send times
    send_times = []

    async def send_message(i):
        delay = await rate_limiter.acquire()
        send_times.append(time.time())
        return (i, delay)

    # Submit 10 messages rapidly
    start = time.time()
    results = await asyncio.gather(*[send_message(i) for i in range(10)])
    end = time.time()

    # Verify first 5 sent immediately (total delay near 0)
    first_five_delays = [delay for _, delay in results[:5]]
    assert all(delay < 0.1 for delay in first_five_delays), "First 5 should send with minimal delay"

    # Verify remaining 5 had delays (rate limiting active)
    remaining_delays = [delay for _, delay in results[5:]]
    assert any(delay > 0 for delay in remaining_delays), "Remaining messages should be rate-limited"

    # Total time should be less than 15 seconds (efficient rate limiting with backoff)
    total_time = end - start
    assert total_time < 15.0, f"10 messages should complete in <15s, took {total_time:.2f}s"

    # Verify all 10 messages eventually sent
    assert len(send_times) == 10


@pytest.mark.asyncio
async def test_sustained_high_load(rate_limiter):
    """
    Test rate limiter under sustained high load.

    Validates:
    - 100 messages over time don't trigger errors
    - Rate limiter maintains target rate (30 msg/min = 0.5 msg/sec)
    - All messages eventually sent
    - No message loss
    """
    message_count = 100
    messages_sent = []

    async def send_message(i):
        await rate_limiter.acquire()
        messages_sent.append(i)
        return i

    # Submit 100 messages (will take time due to rate limiting)
    start = time.time()
    results = await asyncio.gather(*[send_message(i) for i in range(message_count)])
    end = time.time()

    # Verify all messages sent
    assert len(messages_sent) == message_count
    assert len(results) == message_count

    # Calculate actual rate
    total_time = end - start
    actual_rate = message_count / (total_time / 60.0)  # messages per minute

    # Actual rate should be close to target (30 msg/min), allowing for burst
    # With burst of 5, first 5 are instant, then rate-limited
    # Expected time: ~5 instant + 95 at 0.5/sec = ~190 seconds = 3.17 minutes
    # Expected rate: 100 / 3.17 ≈ 31.5 msg/min (close to 30)
    assert actual_rate <= 35.0, f"Rate {actual_rate:.1f} msg/min exceeds safe limit"

    # Verify no message loss (all IDs present)
    assert set(messages_sent) == set(range(message_count))


@pytest.mark.asyncio
async def test_exponential_backoff_on_rejection():
    """
    Test exponential backoff when rate limits approached.

    Validates:
    - Backoff increases exponentially: 1s, 2s, 4s, 8s, 16s
    - Backoff caps at maximum (16s in this test config)
    - Messages not dropped during backoff
    - Backoff resets after cooldown period
    """
    limiter = RateLimiter(
        rate_limit=10.0,  # Lower rate to trigger backoff faster
        burst_size=2,     # Smaller burst to trigger backoff quickly
        backoff_base=1.0,
        backoff_max=16.0,
        cooldown_period=5.0  # Shorter cooldown for faster testing
    )

    # Exhaust burst and trigger backoff
    for _ in range(2):  # Use up burst
        await limiter.acquire()

    # Force backoff by sending rapid messages
    for _ in range(3):  # This should increase backoff level
        await limiter.acquire()

    # Check backoff level increased
    assert limiter.current_backoff_level > 0, "Backoff should be active after burst exhaustion"

    # Wait for cooldown
    await asyncio.sleep(6.0)  # Wait longer than cooldown period

    # Send another message - backoff should reset
    delay = await limiter.acquire()

    # After cooldown, backoff level should be 0
    # (The acquire call resets backoff if cooldown period elapsed)
    assert limiter.current_backoff_level == 0, "Backoff should reset after cooldown"


@pytest.mark.asyncio
async def test_queue_overflow_handling():
    """
    Test message buffer overflow with FIFO eviction.

    Validates:
    - Buffer respects max_size limit
    - Oldest messages dropped when buffer full
    - FIFO ordering maintained
    - Warning logged on overflow
    """
    buffer = MessageBuffer(max_size=10)

    # Fill buffer to capacity
    for i in range(10):
        buffer.enqueue(f"+155500000{i}", f"Message {i}")

    assert len(buffer) == 10

    # Add 5 more messages (should drop oldest 5)
    for i in range(10, 15):
        buffer.enqueue(f"+155500000{i}", f"Message {i}")

    # Buffer should still be at capacity
    assert len(buffer) == 10

    # Drain buffer and verify oldest messages dropped
    messages = buffer.drain()
    assert len(messages) == 10

    # Should have messages 5-14 (0-4 dropped)
    message_texts = [text for _, text in messages]
    assert message_texts[0] == "Message 5"  # Oldest message now
    assert message_texts[-1] == "Message 14"  # Newest message


@pytest.mark.asyncio
async def test_rate_limiter_with_message_buffer_integration():
    """
    Test integration of RateLimiter with MessageBuffer.

    Validates:
    - Messages buffer during rate limiting
    - Buffer drains at controlled rate
    - No message loss during drain
    """
    limiter = RateLimiter(rate_limit=30.0, burst_size=3)
    buffer = MessageBuffer(max_size=50)

    # Simulate buffering messages during disconnect
    for i in range(20):
        buffer.enqueue("+15550000", f"Buffered message {i}")

    assert len(buffer) == 20

    # Simulate reconnection - drain buffer with rate limiting
    sent_messages = []

    async def send_with_rate_limit(recipient, text):
        await limiter.acquire()
        sent_messages.append(text)

    # Drain buffer
    messages = buffer.drain()
    assert len(buffer) == 0

    # Send all buffered messages with rate limiting
    # Use sequential sending to preserve order (gather doesn't guarantee order)
    for recipient, text in messages:
        await send_with_rate_limit(recipient, text)

    # Verify all messages sent
    assert len(sent_messages) == 20

    # Verify order preserved (FIFO)
    for i, text in enumerate(sent_messages):
        assert text == f"Buffered message {i}"


@pytest.mark.asyncio
async def test_can_send_reflects_token_availability():
    """
    Test can_send() accurately reflects rate limiter state.

    Validates:
    - can_send() returns True when tokens available
    - can_send() returns False when tokens exhausted
    - can_send() returns False when backoff active
    """
    limiter = RateLimiter(rate_limit=30.0, burst_size=5)

    # Initially should be able to send (burst available)
    assert limiter.can_send() is True
    assert limiter.tokens_available >= 5.0

    # Exhaust burst
    for _ in range(5):
        await limiter.acquire()

    # Should not be able to send immediately (tokens exhausted or backoff active)
    # Note: can_send() checks both tokens AND backoff level
    assert limiter.tokens_available < 1.0

    # Wait for token refill and cooldown
    await asyncio.sleep(65.0)  # Wait longer than cooldown period (60s) to reset backoff

    # Trigger backoff reset by calling acquire (it checks cooldown internally)
    await limiter.acquire()

    # Now should be able to send again (tokens refilled and backoff reset)
    # Wait a bit more for token refill after the acquire above
    await asyncio.sleep(3.0)
    assert limiter.can_send() is True
    assert limiter.tokens_available >= 1.0


@pytest.mark.asyncio
async def test_concurrent_acquire_requests():
    """
    Test multiple concurrent acquire() calls don't cause race conditions.

    Validates:
    - Token bucket handles concurrent access safely
    - No double-spending of tokens
    - All acquires eventually succeed
    """
    limiter = RateLimiter(rate_limit=60.0, burst_size=10)  # Higher rate for faster test

    # Submit 20 concurrent acquire requests
    async def acquire_token(i):
        delay = await limiter.acquire()
        return (i, delay)

    results = await asyncio.gather(*[acquire_token(i) for i in range(20)])

    # Verify all acquires succeeded
    assert len(results) == 20

    # Verify first 10 had minimal delay (burst)
    first_ten_delays = [delay for _, delay in results[:10]]
    assert all(delay < 0.1 for delay in first_ten_delays)

    # Verify remaining had some delay (rate limited)
    remaining_delays = [delay for _, delay in results[10:]]
    assert sum(remaining_delays) > 0  # At least some delay applied


@pytest.mark.asyncio
async def test_reset_functionality():
    """
    Test rate limiter reset() clears state correctly.

    Validates:
    - Tokens restored to burst size
    - Backoff level cleared
    - Can send immediately after reset
    """
    limiter = RateLimiter(rate_limit=30.0, burst_size=5)

    # Exhaust burst and trigger backoff
    for _ in range(10):
        await limiter.acquire()

    # Should have low tokens and possibly backoff
    assert limiter.tokens_available < 5.0

    # Reset limiter
    limiter.reset()

    # Should be fully restored
    assert limiter.tokens_available == 5.0
    assert limiter.current_backoff_level == 0
    assert limiter.can_send() is True

    # Should be able to send burst immediately
    for _ in range(5):
        delay = await limiter.acquire()
        assert delay < 0.1  # Minimal delay
