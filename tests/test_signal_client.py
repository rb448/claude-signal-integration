"""Integration tests for SignalClient reconnection logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.signal.client import SignalClient
from src.signal.reconnection import ConnectionState


class TestAutoReconnect:
    """Test automatic reconnection after connection failures."""

    @pytest.mark.asyncio
    async def test_auto_reconnect_after_connection_failure(self):
        """Verify auto_reconnect retries with exponential backoff and succeeds."""
        client = SignalClient()

        # Mock connect to fail 2 times, succeed on 3rd
        connect_attempts = 0

        async def mock_connect():
            nonlocal connect_attempts
            connect_attempts += 1
            if connect_attempts < 3:
                raise ConnectionError(f"Connection failed (attempt {connect_attempts})")
            # Success on 3rd attempt
            client._connected = True
            client._session = MagicMock()
            client.reconnection_manager.transition(ConnectionState.CONNECTED)

        client.connect = mock_connect

        # Set initial state to DISCONNECTED
        client.reconnection_manager.state = ConnectionState.DISCONNECTED

        # Mock asyncio.sleep to avoid actual delays
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Run auto_reconnect
            await client.auto_reconnect()

        # Verify reconnection succeeded after 3 attempts
        assert connect_attempts == 3
        assert client.reconnection_manager.state == ConnectionState.CONNECTED
        assert client.reconnection_manager.attempt_count == 0  # Reset on success

        # Verify sleep was called with correct backoff delays
        # Attempt 1: 1s, Attempt 2: 2s, Attempt 3: 4s
        assert mock_sleep.call_count == 3
        sleep_delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_delays == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio
    async def test_auto_reconnect_max_backoff(self):
        """Verify backoff caps at 60 seconds."""
        client = SignalClient()

        # Mock connect to fail many times
        connect_attempts = 0

        async def mock_connect():
            nonlocal connect_attempts
            connect_attempts += 1
            if connect_attempts < 8:
                raise ConnectionError(f"Connection failed (attempt {connect_attempts})")
            # Success on 8th attempt
            client._connected = True
            client._session = MagicMock()
            client.reconnection_manager.transition(ConnectionState.CONNECTED)

        client.connect = mock_connect

        # Set initial state to DISCONNECTED
        client.reconnection_manager.state = ConnectionState.DISCONNECTED

        # Mock asyncio.sleep
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await client.auto_reconnect()

        # Verify backoff delays cap at 60s
        sleep_delays = [call.args[0] for call in mock_sleep.call_args_list]
        # Attempts: 1s, 2s, 4s, 8s, 16s, 32s, 60s, 60s (last one succeeds)
        assert sleep_delays == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]


class TestMessageBuffering:
    """Test message buffering during disconnects."""

    @pytest.mark.asyncio
    async def test_send_message_buffers_when_disconnected(self):
        """Verify messages are buffered when connection is down."""
        client = SignalClient()

        # Set state to DISCONNECTED
        client.reconnection_manager.state = ConnectionState.DISCONNECTED

        # Send a message
        await client.send_message("+1234567890", "test message")

        # Verify message was buffered (not sent)
        assert len(client.message_buffer) == 1
        buffered = client.message_buffer.dequeue()
        assert buffered == ("+1234567890", "test message")

    @pytest.mark.asyncio
    async def test_send_message_buffers_multiple_messages(self):
        """Verify multiple messages are buffered in FIFO order."""
        client = SignalClient()

        # Set state to DISCONNECTED
        client.reconnection_manager.state = ConnectionState.DISCONNECTED

        # Send multiple messages
        await client.send_message("+1111111111", "message 1")
        await client.send_message("+2222222222", "message 2")
        await client.send_message("+3333333333", "message 3")

        # Verify all buffered
        assert len(client.message_buffer) == 3

        # Verify FIFO order
        messages = client.message_buffer.drain()
        assert messages == [
            ("+1111111111", "message 1"),
            ("+2222222222", "message 2"),
            ("+3333333333", "message 3"),
        ]


class TestDrainBuffer:
    """Test buffer draining after reconnection."""

    @pytest.mark.asyncio
    async def test_drain_buffer_sends_all_messages_after_reconnect(self):
        """Verify all buffered messages are sent after reconnection."""
        client = SignalClient()

        # Buffer 3 messages
        client.message_buffer.enqueue("+1111111111", "message 1")
        client.message_buffer.enqueue("+2222222222", "message 2")
        client.message_buffer.enqueue("+3333333333", "message 3")

        assert len(client.message_buffer) == 3

        # Mock send_message to track calls
        sent_messages = []

        async def mock_send(recipient, text):
            sent_messages.append((recipient, text))

        # Replace send_message temporarily
        original_send = client.send_message
        client.send_message = mock_send

        # Drain buffer
        await client._drain_buffer()

        # Restore original method
        client.send_message = original_send

        # Verify all messages were sent
        assert sent_messages == [
            ("+1111111111", "message 1"),
            ("+2222222222", "message 2"),
            ("+3333333333", "message 3"),
        ]

        # Verify buffer is empty
        assert len(client.message_buffer) == 0
        assert client.message_buffer.is_empty()

    @pytest.mark.asyncio
    async def test_drain_buffer_handles_send_failures(self):
        """Verify drain_buffer continues even if some messages fail to send."""
        client = SignalClient()

        # Buffer 3 messages
        client.message_buffer.enqueue("+1111111111", "message 1")
        client.message_buffer.enqueue("+2222222222", "message 2")
        client.message_buffer.enqueue("+3333333333", "message 3")

        # Mock send_message to fail on message 2
        sent_messages = []

        async def mock_send(recipient, text):
            if recipient == "+2222222222":
                raise RuntimeError("Send failed")
            sent_messages.append((recipient, text))

        client.send_message = mock_send

        # Drain buffer (should not raise exception)
        await client._drain_buffer()

        # Verify messages 1 and 3 were sent (2 failed)
        assert sent_messages == [
            ("+1111111111", "message 1"),
            ("+3333333333", "message 3"),
        ]

        # Buffer should still be empty
        assert client.message_buffer.is_empty()


class TestReceiveMessagesReconnection:
    """Test receive_messages reconnection trigger."""

    @pytest.mark.asyncio
    async def test_receive_messages_triggers_reconnect_on_client_error(self):
        """Verify receive_messages triggers auto_reconnect on aiohttp.ClientError."""
        from aiohttp import ClientError

        client = SignalClient()

        # Mock session and connection
        mock_session = MagicMock()
        client._session = mock_session
        client._connected = True
        client.reconnection_manager.state = ConnectionState.CONNECTED

        # Create a mock context manager that raises ClientError
        class MockContextManager:
            async def __aenter__(self):
                raise ClientError("Connection lost")

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        # Mock session.get to return our context manager
        mock_session.get = MagicMock(return_value=MockContextManager())

        # Mock auto_reconnect to track if it was called
        reconnect_called = False

        async def mock_auto_reconnect():
            nonlocal reconnect_called
            reconnect_called = True

        client.auto_reconnect = mock_auto_reconnect

        # Run receive_messages (should trigger reconnection and return)
        messages = []
        async for msg in client.receive_messages():
            messages.append(msg)

        # Verify state transitioned to DISCONNECTED
        assert client.reconnection_manager.state == ConnectionState.DISCONNECTED

        # Verify auto_reconnect task was created
        assert client._reconnect_task is not None

        # Wait for task to complete
        await client._reconnect_task

        # Verify auto_reconnect was called
        assert reconnect_called


class TestConnectionStateTransitions:
    """Test connection state transitions in SignalClient."""

    @pytest.mark.asyncio
    async def test_connect_transitions_to_connected_on_success(self):
        """Verify successful connect transitions to CONNECTED state."""
        client = SignalClient()

        # Mock the entire connect process
        async def mock_connect():
            client._connected = True
            client._session = MagicMock()
            client.reconnection_manager.transition(ConnectionState.CONNECTED)

        client.connect = mock_connect
        await client.connect()

        # Verify state is CONNECTED
        assert client.reconnection_manager.state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_transitions_to_disconnected_on_failure(self):
        """Verify failed connect transitions to DISCONNECTED state."""
        client = SignalClient()

        # Mock connect to fail
        async def mock_connect():
            client.reconnection_manager.transition(ConnectionState.DISCONNECTED)
            raise ConnectionError("Connection failed")

        client.connect = mock_connect

        # Attempt connection (should fail)
        with pytest.raises(ConnectionError):
            await client.connect()

        # Verify state is DISCONNECTED
        assert client.reconnection_manager.state == ConnectionState.DISCONNECTED
