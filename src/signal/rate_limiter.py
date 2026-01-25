"""Rate limiter with token bucket and exponential backoff."""

import asyncio
import time
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter with exponential backoff.

    Prevents Signal API rate limit errors by:
    - Limiting average send rate (30 messages/minute)
    - Allowing burst traffic (up to 5 instant messages)
    - Applying exponential backoff when rate limits approached
    """

    def __init__(
        self,
        rate_limit: float = 30.0,  # messages per minute
        burst_size: int = 5,  # instant burst allowance
        backoff_base: float = 1.0,  # base delay in seconds
        backoff_max: float = 16.0,  # max backoff delay
        cooldown_period: float = 60.0  # seconds before backoff resets
    ) -> None:
        """Initialize rate limiter.

        Args:
            rate_limit: Maximum messages per minute (default: 30)
            burst_size: Number of messages allowed instantly (default: 5)
            backoff_base: Base exponential backoff delay in seconds (default: 1.0)
            backoff_max: Maximum backoff delay in seconds (default: 16.0)
            cooldown_period: Seconds before backoff resets (default: 60.0)
        """
        self._rate_limit = rate_limit
        self._burst_size = burst_size
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._cooldown_period = cooldown_period

        # Token bucket state
        self._tokens: float = float(burst_size)
        self._last_refill: float = time.monotonic()
        self._tokens_per_second: float = rate_limit / 60.0  # Convert per-minute to per-second

        # Exponential backoff state
        self._backoff_level: int = 0
        self._last_send: Optional[float] = None
        self._consecutive_sends: int = 0

    def _refill_tokens(self) -> None:
        """Refill token bucket based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill

        # Add tokens based on time elapsed
        tokens_to_add = elapsed * self._tokens_per_second
        self._tokens = min(self._burst_size, self._tokens + tokens_to_add)
        self._last_refill = now

    def _calculate_backoff(self) -> float:
        """Calculate current exponential backoff delay.

        Returns:
            float: Delay in seconds (0 if no backoff needed)
        """
        if self._backoff_level == 0:
            return 0.0

        # Exponential backoff: 1s, 2s, 4s, 8s, 16s (max)
        delay = min(
            self._backoff_base * (2 ** (self._backoff_level - 1)),
            self._backoff_max
        )
        return delay

    def can_send(self) -> bool:
        """Check if message can be sent immediately without delay.

        Returns:
            bool: True if tokens available and no backoff active
        """
        self._refill_tokens()
        return self._tokens >= 1.0 and self._backoff_level == 0

    async def acquire(self) -> float:
        """Acquire permission to send message, applying delays if needed.

        Returns:
            float: Delay applied in seconds (0 if sent immediately)

        Note:
            This method will wait (async) for any necessary backoff delays.
            Always call this before sending a message to Signal API.
        """
        self._refill_tokens()

        now = time.monotonic()
        total_delay = 0.0

        # Check if we need to reset backoff after cooldown
        if self._last_send and (now - self._last_send) >= self._cooldown_period:
            if self._backoff_level > 0:
                logger.info(
                    "rate_limiter_backoff_reset",
                    previous_level=self._backoff_level,
                    cooldown_elapsed=now - self._last_send
                )
            self._backoff_level = 0
            self._consecutive_sends = 0

        # Apply exponential backoff if active
        backoff_delay = self._calculate_backoff()
        if backoff_delay > 0:
            logger.info(
                "rate_limiter_backoff_delay",
                delay_seconds=backoff_delay,
                backoff_level=self._backoff_level
            )
            await asyncio.sleep(backoff_delay)
            total_delay += backoff_delay
            self._refill_tokens()  # Refill after backoff delay

        # Wait for token availability if needed
        while self._tokens < 1.0:
            wait_time = (1.0 - self._tokens) / self._tokens_per_second
            logger.info(
                "rate_limiter_token_wait",
                wait_seconds=wait_time,
                current_tokens=self._tokens
            )
            await asyncio.sleep(wait_time)
            total_delay += wait_time
            self._refill_tokens()

        # Consume token
        self._tokens -= 1.0
        self._last_send = time.monotonic()
        self._consecutive_sends += 1

        # Increase backoff level if sending too rapidly
        # Trigger backoff if we've sent burst_size messages without cooldown
        if self._consecutive_sends >= self._burst_size and self._tokens < 1.0:
            self._backoff_level = min(self._backoff_level + 1, 5)  # Max level 5 (16s delay)
            logger.warning(
                "rate_limiter_backoff_increased",
                new_level=self._backoff_level,
                consecutive_sends=self._consecutive_sends,
                next_delay=self._calculate_backoff()
            )

        if total_delay > 0:
            logger.debug(
                "rate_limiter_delay_applied",
                total_delay=total_delay,
                tokens_remaining=self._tokens
            )

        return total_delay

    def reset(self) -> None:
        """Reset rate limiter state (for testing or manual override).

        Note:
            Resets tokens to full burst size and clears backoff state.
        """
        self._tokens = float(self._burst_size)
        self._last_refill = time.monotonic()
        self._backoff_level = 0
        self._consecutive_sends = 0
        self._last_send = None
        logger.info("rate_limiter_reset")

    @property
    def current_backoff_level(self) -> int:
        """Get current exponential backoff level.

        Returns:
            int: Backoff level (0 = no backoff, 5 = max backoff)
        """
        return self._backoff_level

    @property
    def tokens_available(self) -> float:
        """Get current number of tokens available.

        Returns:
            float: Tokens available (may be fractional)
        """
        self._refill_tokens()
        return self._tokens
