"""HTTP client for signal-cli-rest-api communication (MODE=normal)."""

import asyncio
import json
from typing import AsyncIterator, Optional

import aiohttp
import structlog

from .rate_limiter import RateLimiter
from .reconnection import ReconnectionManager, ConnectionState
from .message_buffer import MessageBuffer
from ..session.sync import SessionSynchronizer

logger = structlog.get_logger(__name__)


class SignalClient:
    """HTTP client for Signal API using long-polling for message receipt."""

    def __init__(
        self,
        api_url: str = "http://localhost:8080",
        phone_number: str = "+19735258994"
    ) -> None:
        """Initialize Signal client.

        Args:
            api_url: HTTP URL for signal-cli-rest-api (default: http://localhost:8080)
            phone_number: Bot's registered Signal phone number in E.164 format
        """
        self.api_url = api_url
        self.phone_number = phone_number
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected: bool = False
        self._rate_limiter = RateLimiter()
        self.reconnection_manager = ReconnectionManager()
        self.message_buffer = MessageBuffer(max_size=100)
        self._reconnect_task: Optional[asyncio.Task] = None
        self.session_synchronizer = SessionSynchronizer()
        self.session_id: Optional[str] = None  # Set by daemon

    async def connect(self) -> None:
        """Establish HTTP connection to Signal API.

        Tests connectivity by making a request to the health endpoint.

        Raises:
            ConnectionError: If connection to Signal API fails
        """
        try:
            self._session = aiohttp.ClientSession()

            # Test connectivity
            async with self._session.get(f"{self.api_url}/v1/health") as resp:
                if resp.status in (200, 204):
                    self._connected = True
                    self.reconnection_manager.transition(ConnectionState.CONNECTED)
                    logger.info(
                        "signal_api_connected",
                        api_url=self.api_url,
                        phone_number=self.phone_number
                    )
                else:
                    raise ConnectionError(f"Signal API returned HTTP {resp.status}")

        except Exception as e:
            if self._session:
                await self._session.close()
                self._session = None
            self._connected = False
            self.reconnection_manager.transition(ConnectionState.DISCONNECTED)
            raise ConnectionError(f"Failed to connect to Signal API at {self.api_url}: {e}")

    async def disconnect(self) -> None:
        """Close HTTP session gracefully."""
        if self._session:
            await self._session.close()
            self._connected = False
            self._session = None
            logger.info("signal_api_disconnected")

    async def auto_reconnect(self) -> None:
        """Automatically reconnect with exponential backoff and state sync."""
        while self.reconnection_manager.state == ConnectionState.DISCONNECTED:
            # Transition to RECONNECTING
            self.reconnection_manager.transition(ConnectionState.RECONNECTING)

            # Calculate backoff delay
            delay = self.reconnection_manager.calculate_backoff()
            logger.info(
                "reconnecting",
                attempt=self.reconnection_manager.attempt_count,
                delay_seconds=delay
            )
            await asyncio.sleep(delay)

            # Attempt reconnection
            try:
                await self.connect()

                # Success - transition to SYNCING state
                self.reconnection_manager.transition(ConnectionState.SYNCING)

                # Synchronize session state (if session_id set)
                if self.session_id:
                    await self._sync_session_state()

                # After sync, transition to CONNECTED
                self.reconnection_manager.transition(ConnectionState.CONNECTED)

                # Drain buffered messages
                await self._drain_buffer()
                break
            except ConnectionError:
                # Failed - will retry
                self.reconnection_manager.transition(ConnectionState.DISCONNECTED)

    async def _sync_session_state(self) -> None:
        """Synchronize session state after reconnection.

        Note: This is a placeholder implementation. Full session state
        synchronization requires SessionManager API access from SignalClient,
        which will be implemented in future work.
        """
        # TODO: Fetch remote session context from SessionManager
        # For now, this is a placeholder - full implementation requires
        # SessionManager API access from SignalClient

        # Placeholder: assume local context is current
        local_context = {}  # Would fetch from SessionManager
        remote_context = {}  # Would fetch from Claude API

        result = await self.session_synchronizer.sync(
            self.session_id,
            local_context,
            remote_context
        )

        if result.changed:
            logger.info(
                "session_state_synchronized",
                session_id=self.session_id,
                changes=len(result.diff)
            )
            # TODO: Update SessionManager with merged context

    async def _drain_buffer(self) -> None:
        """Send all buffered messages after reconnection."""
        messages = self.message_buffer.drain()
        logger.info("draining_message_buffer", count=len(messages))

        for recipient, text in messages:
            try:
                await self.send_message(recipient, text)
            except Exception as e:
                logger.error("failed_to_send_buffered_message", error=str(e))

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
        if not recipient or not text:
            raise ValueError("Recipient and text must not be empty")

        # Buffer message if disconnected
        if self.reconnection_manager.state != ConnectionState.CONNECTED:
            self.message_buffer.enqueue(recipient, text)
            logger.info("message_buffered", recipient=recipient)
            return

        if not self._connected or not self._session:
            raise RuntimeError("Not connected to Signal API. Call connect() first.")

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

        # Send message via HTTP POST
        url = f"{self.api_url}/v2/send"
        payload = {
            "message": text,
            "number": self.phone_number,
            "recipients": [recipient]
        }

        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status not in (200, 201):
                    error_text = await resp.text()
                    raise RuntimeError(
                        f"Failed to send message: HTTP {resp.status}, {error_text}"
                    )

            logger.debug(
                "message_sent",
                recipient=recipient,
                text_length=len(text)
            )
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to send message: {e}")

    async def receive_messages(self) -> AsyncIterator[dict]:
        """Receive incoming messages from Signal API via HTTP long-polling.

        Uses GET long-polling to receive messages. The endpoint blocks until messages
        are available or timeout occurs (typically 30s). Empty responses are normal
        and the loop continues.

        Yields:
            dict: Incoming message data with 'envelope' and 'account' fields

        Raises:
            RuntimeError: If not connected to Signal API

        Note:
            Implements retry logic for connection errors with exponential backoff.
            Timeouts are expected behavior for long-polling and are handled gracefully.
        """
        if not self._connected or not self._session:
            raise RuntimeError("Not connected to Signal API. Call connect() first.")

        url = f"{self.api_url}/v1/receive/{self.phone_number}"
        retry_delay = 5
        max_retry_delay = 60

        while self._connected:
            try:
                # Long-polling request with 35s timeout (signal-cli default is 30s)
                async with self._session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=35)
                ) as resp:
                    if resp.status == 200:
                        # Reset retry delay on success
                        retry_delay = 5

                        messages = await resp.json(content_type=None)

                        # Yield each message in the response
                        if isinstance(messages, list):
                            for msg in messages:
                                logger.debug(
                                    "message_received",
                                    source=msg.get("envelope", {}).get("sourceNumber"),
                                    account=msg.get("account")
                                )
                                yield msg
                        # Empty response is normal for long-polling timeout
                        continue

                    elif resp.status >= 500:
                        # Server error - retry with backoff
                        logger.warning(
                            "signal_api_server_error",
                            status=resp.status,
                            retry_delay=retry_delay
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, max_retry_delay)
                        continue

                    else:
                        # Client error - something is wrong with our request
                        error_text = await resp.text()
                        raise RuntimeError(
                            f"Signal API error: HTTP {resp.status}, {error_text}"
                        )

            except asyncio.TimeoutError:
                # Long-polling timeout is normal, continue
                logger.debug("long_polling_timeout")
                continue

            except aiohttp.ClientError as e:
                # Network/connection error - trigger reconnection
                logger.error("connection_lost", error=str(e))
                self.reconnection_manager.transition(ConnectionState.DISCONNECTED)
                self._reconnect_task = asyncio.create_task(self.auto_reconnect())
                # Stop iteration - will resume after reconnect
                return

            except Exception as e:
                # Unexpected error - log and re-raise
                logger.error(
                    "signal_receive_error",
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to Signal API.

        Returns:
            bool: True if connected, False otherwise
        """
        return self._connected
