"""WebSocket client for signal-cli-rest-api communication."""

import asyncio
from typing import AsyncIterator, Optional

import structlog
import websockets
from websockets.asyncio.client import ClientConnection

from .rate_limiter import RateLimiter

logger = structlog.get_logger(__name__)


class SignalClient:
    """WebSocket client for Signal API bidirectional messaging."""

    def __init__(self, api_url: str = "ws://localhost:8080") -> None:
        """Initialize Signal client.

        Args:
            api_url: WebSocket URL for signal-cli-rest-api (default: ws://localhost:8080)
        """
        self.api_url = api_url
        self._connection: Optional[ClientConnection] = None
        self._connected: bool = False
        self._rate_limiter = RateLimiter()

    async def connect(self) -> None:
        """Establish WebSocket connection to Signal API.

        Raises:
            ConnectionError: If connection to Signal API fails
        """
        try:
            self._connection = await websockets.connect(self.api_url)
            self._connected = True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect to Signal API at {self.api_url}: {e}")

    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""
        if self._connection:
            await self._connection.close()
            self._connected = False
            self._connection = None

    async def send_message(self, recipient: str, text: str) -> None:
        """Send a text message to a Signal recipient.

        Args:
            recipient: Phone number in E.164 format (e.g., +12345678900)
            text: Message text to send

        Raises:
            RuntimeError: If not connected to Signal API
            ValueError: If recipient or text is empty

        Note:
            Rate limiting is automatically applied to prevent Signal API rate limit errors.
            May introduce delays if sending messages rapidly.
        """
        if not self._connected or not self._connection:
            raise RuntimeError("Not connected to Signal API. Call connect() first.")

        if not recipient or not text:
            raise ValueError("Recipient and text must not be empty")

        # Apply rate limiting before sending
        delay = await self._rate_limiter.acquire()
        if delay > 0:
            logger.info(
                "rate_limit_delay_applied",
                delay_seconds=delay,
                recipient=recipient
            )
        elif self._rate_limiter.current_backoff_level > 0:
            logger.warning(
                "rate_limit_backoff_active",
                backoff_level=self._rate_limiter.current_backoff_level,
                recipient=recipient
            )

        # Send message via WebSocket (format depends on signal-cli-rest-api protocol)
        # This is a basic implementation - actual protocol may vary
        message_payload = {
            "jsonrpc": "2.0",
            "method": "send",
            "params": {
                "recipient": recipient,
                "message": text
            },
            "id": 1
        }

        try:
            await self._connection.send(str(message_payload))
            logger.debug(
                "message_sent",
                recipient=recipient,
                text_length=len(text)
            )
        except Exception as e:
            raise RuntimeError(f"Failed to send message: {e}")

    async def receive_messages(self) -> AsyncIterator[dict]:
        """Receive incoming messages from Signal API.

        Yields:
            dict: Incoming message data from Signal

        Raises:
            RuntimeError: If not connected to Signal API
        """
        if not self._connected or not self._connection:
            raise RuntimeError("Not connected to Signal API. Call connect() first.")

        try:
            async for message in self._connection:
                # Parse incoming message (format depends on signal-cli-rest-api protocol)
                # This is a placeholder - actual parsing logic will be refined
                yield {"raw": message}
        except websockets.exceptions.ConnectionClosed:
            self._connected = False
            raise RuntimeError("WebSocket connection closed")

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to Signal API.

        Returns:
            bool: True if connected, False otherwise
        """
        return self._connected
