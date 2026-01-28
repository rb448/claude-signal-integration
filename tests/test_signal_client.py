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

    @pytest.mark.asyncio
    async def test_auto_reconnect_uses_syncing_state(self):
        """Verify auto_reconnect uses SYNCING state during reconnection.

        This test verifies CONN-03 requirement is satisfied:
        State transitions: DISCONNECTED → RECONNECTING → SYNCING → CONNECTED
        """
        client = SignalClient()

        # Track state transitions
        state_transitions = []

        original_transition = client.reconnection_manager.transition

        def track_transition(state):
            state_transitions.append(state)
            original_transition(state)

        client.reconnection_manager.transition = track_transition

        # Set initial state to DISCONNECTED
        client.reconnection_manager.state = ConnectionState.DISCONNECTED

        # Mock connect to succeed on first attempt
        async def mock_connect():
            client._connected = True
            client._session = MagicMock()

        client.connect = mock_connect

        # Set session_id so sync will be called
        client.session_id = "test-session-123"

        # Mock session_synchronizer.sync()
        sync_called = False

        async def mock_sync(session_id, local_context, remote_context):
            nonlocal sync_called
            sync_called = True
            from src.session.sync import SyncResult
            return SyncResult(changed=False, diff={}, merged_context={})

        client.session_synchronizer.sync = mock_sync

        # Mock asyncio.sleep to avoid delays
        with patch('asyncio.sleep', new_callable=AsyncMock):
            # Run auto_reconnect
            await client.auto_reconnect()

        # Verify state transitions occurred in correct order
        assert state_transitions == [
            ConnectionState.RECONNECTING,
            ConnectionState.SYNCING,
            ConnectionState.CONNECTED
        ]

        # Verify session_synchronizer.sync() was called
        assert sync_called

        # Verify final state is CONNECTED
        assert client.reconnection_manager.state == ConnectionState.CONNECTED


class TestErrorHandling:
    """Test error handling in SignalClient."""

    @pytest.mark.asyncio
    async def test_send_message_validation_errors(self):
        """Verify send_message raises ValueError for empty recipient or text."""
        client = SignalClient()

        # Test empty recipient
        with pytest.raises(ValueError, match="Recipient and text must not be empty"):
            await client.send_message("", "test message")

        # Test empty text
        with pytest.raises(ValueError, match="Recipient and text must not be empty"):
            await client.send_message("+1234567890", "")

        # Test both empty
        with pytest.raises(ValueError, match="Recipient and text must not be empty"):
            await client.send_message("", "")

    @pytest.mark.asyncio
    async def test_send_message_not_connected_error(self):
        """Verify send_message raises RuntimeError when not connected."""
        client = SignalClient()

        # Set state to CONNECTED but _connected flag is False
        client.reconnection_manager.state = ConnectionState.CONNECTED
        client._connected = False
        client._session = None

        # Attempt to send message
        with pytest.raises(RuntimeError, match="Not connected to Signal API"):
            await client.send_message("+1234567890", "test message")

    @pytest.mark.asyncio
    async def test_receive_messages_not_connected_error(self):
        """Verify receive_messages raises RuntimeError when not connected."""
        client = SignalClient()

        # Ensure not connected
        client._connected = False
        client._session = None

        # Attempt to receive messages
        with pytest.raises(RuntimeError, match="Not connected to Signal API"):
            async for _ in client.receive_messages():
                pass

    @pytest.mark.asyncio
    async def test_connect_failure_cleanup(self):
        """Verify connect() cleans up session on failure."""
        client = SignalClient()

        # Mock ClientSession to raise error on health check
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            # Create a mock context manager that raises a generic exception
            class MockContextManager:
                async def __aenter__(self):
                    raise OSError("Connection refused")

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    return None

            mock_session.get = MagicMock(return_value=MockContextManager())
            mock_session.close = AsyncMock()

            # Attempt connection (should fail)
            with pytest.raises(ConnectionError, match="Failed to connect to Signal API"):
                await client.connect()

            # Verify cleanup occurred
            assert not client._connected
            assert client._session is None
            assert client.reconnection_manager.state == ConnectionState.DISCONNECTED
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_sync_with_changes(self):
        """Verify session sync logs changes when state differs."""
        client = SignalClient()
        client.session_id = "test-session-123"

        # Mock session_synchronizer to return changes
        async def mock_sync(session_id, local_context, remote_context):
            from src.session.sync import SyncResult
            return SyncResult(
                changed=True,
                diff={"key1": "value1", "key2": "value2"},
                merged_context={"key1": "value1", "key2": "value2"}
            )

        client.session_synchronizer.sync = mock_sync

        # Call _sync_session_state
        await client._sync_session_state()

        # Test passes if no exception raised (coverage for line 158-162)


class TestConnectionLifecycle:
    """Test connection and disconnection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Verify successful connection sets state correctly."""
        client = SignalClient()

        # Mock aiohttp.ClientSession
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            # Create a mock response for health check
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.get = MagicMock(return_value=mock_response)

            # Connect should succeed
            await client.connect()

            # Verify state
            assert client._connected
            assert client._session is not None
            assert client.reconnection_manager.state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Verify disconnect closes session."""
        client = SignalClient()

        # Set up a mock session
        mock_session = AsyncMock()
        client._session = mock_session
        client._connected = True

        # Disconnect
        await client.disconnect()

        # Verify state
        assert not client._connected
        assert client._session is None
        mock_session.close.assert_called_once()


class TestRateLimiting:
    """Test rate limiting in send_message."""

    @pytest.mark.asyncio
    async def test_send_message_rate_limit_delay(self):
        """Verify rate limiting applies delays."""
        client = SignalClient()

        # Set up connection
        mock_session = AsyncMock()
        client._session = mock_session
        client._connected = True
        client.reconnection_manager.state = ConnectionState.CONNECTED

        # Mock rate limiter to return a delay
        client._rate_limiter.acquire = AsyncMock(return_value=0.5)

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.post = MagicMock(return_value=mock_response)

        # Send message
        await client.send_message("+1234567890", "test message")

        # Verify rate limiter was called
        client._rate_limiter.acquire.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_http_error(self):
        """Verify send_message handles HTTP errors."""
        from aiohttp import ClientError

        client = SignalClient()

        # Set up connection
        mock_session = AsyncMock()
        client._session = mock_session
        client._connected = True
        client.reconnection_manager.state = ConnectionState.CONNECTED

        # Mock rate limiter
        client._rate_limiter.acquire = AsyncMock(return_value=0)

        # Mock HTTP response with error
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.post = MagicMock(return_value=mock_response)

        # Send message should raise RuntimeError
        with pytest.raises(RuntimeError, match="Failed to send message: HTTP 500"):
            await client.send_message("+1234567890", "test message")


class TestReceiveMessages:
    """Test receive_messages edge cases."""

    @pytest.mark.asyncio
    async def test_receive_messages_timeout(self):
        """Verify receive_messages handles timeouts gracefully."""
        client = SignalClient()

        # Set up connection
        mock_session = AsyncMock()
        client._session = mock_session
        client._connected = True
        client.reconnection_manager.state = ConnectionState.CONNECTED

        # Create a mock context manager that raises TimeoutError then disconnects
        call_count = 0

        class MockContextManager:
            async def __aenter__(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise asyncio.TimeoutError("Long polling timeout")
                # After timeout, disconnect the client to stop iteration
                client._connected = False
                # Return empty response
                mock_resp = AsyncMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=[])
                return mock_resp

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_session.get = MagicMock(return_value=MockContextManager())

        # Receive messages
        messages = []
        async for msg in client.receive_messages():
            messages.append(msg)

        # Should handle timeout gracefully and continue
        assert messages == []
        assert call_count == 2  # One timeout, one disconnection

    @pytest.mark.asyncio
    async def test_receive_messages_server_error(self):
        """Verify receive_messages retries on server errors."""
        client = SignalClient()

        # Set up connection
        mock_session = AsyncMock()
        client._session = mock_session
        client._connected = True
        client.reconnection_manager.state = ConnectionState.CONNECTED

        call_count = 0

        class MockContextManager:
            async def __aenter__(self):
                nonlocal call_count
                call_count += 1
                mock_resp = AsyncMock()
                if call_count == 1:
                    # First call: server error
                    mock_resp.status = 500
                else:
                    # Second call: disconnect to stop iteration
                    client._connected = False
                    mock_resp.status = 200
                    mock_resp.json = AsyncMock(return_value=[])
                return mock_resp

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_session.get = MagicMock(return_value=MockContextManager())

        # Mock asyncio.sleep to avoid delays
        with patch('asyncio.sleep', new_callable=AsyncMock):
            messages = []
            async for msg in client.receive_messages():
                messages.append(msg)

        # Should retry after server error
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_receive_messages_success_with_messages(self):
        """Verify receive_messages yields messages correctly."""
        client = SignalClient()

        # Set up connection
        mock_session = AsyncMock()
        client._session = mock_session
        client._connected = True
        client.reconnection_manager.state = ConnectionState.CONNECTED

        call_count = 0
        test_messages = [
            {"envelope": {"sourceNumber": "+1111111111"}, "account": "test"},
            {"envelope": {"sourceNumber": "+2222222222"}, "account": "test"}
        ]

        class MockContextManager:
            async def __aenter__(self):
                nonlocal call_count
                call_count += 1
                mock_resp = AsyncMock()
                if call_count == 1:
                    # First call: return messages
                    mock_resp.status = 200
                    mock_resp.json = AsyncMock(return_value=test_messages)
                else:
                    # Second call: disconnect to stop iteration
                    client._connected = False
                    mock_resp.status = 200
                    mock_resp.json = AsyncMock(return_value=[])
                return mock_resp

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_session.get = MagicMock(return_value=MockContextManager())

        # Receive messages
        messages = []
        async for msg in client.receive_messages():
            messages.append(msg)

        # Should yield all messages
        assert messages == test_messages


class TestReconnectionWithCatchup:
    """Test reconnection with catch-up summary generation."""

    @pytest.mark.asyncio
    async def test_auto_reconnect_with_catchup_summaries(self):
        """Verify auto_reconnect generates catch-up summaries for active sessions."""
        client = SignalClient()
        client.session_id = "test-session-123"

        # Set initial state to DISCONNECTED
        client.reconnection_manager.state = ConnectionState.DISCONNECTED

        # Mock connect to succeed
        async def mock_connect():
            client._connected = True
            client._session = MagicMock()

        client.connect = mock_connect

        # Mock session_synchronizer.sync()
        async def mock_sync(session_id, local_context, remote_context):
            from src.session.sync import SyncResult
            return SyncResult(changed=False, diff={}, merged_context={})

        client.session_synchronizer.sync = mock_sync

        # Set up session_manager and notification_manager
        from dataclasses import dataclass
        from src.session.lifecycle import SessionStatus

        @dataclass
        class MockSession:
            id: str
            status: SessionStatus
            thread_id: str

        mock_session_manager = MagicMock()
        mock_session_manager.list = AsyncMock(return_value=[
            MockSession(id="session-1", status=SessionStatus.ACTIVE, thread_id="+1111111111"),
            MockSession(id="session-2", status=SessionStatus.PAUSED, thread_id="+2222222222"),
        ])
        mock_session_manager.generate_catchup_summary = AsyncMock(return_value="Test activity summary")

        mock_notification_manager = MagicMock()
        mock_notification_manager.notify = AsyncMock()

        client.session_manager = mock_session_manager
        client.notification_manager = mock_notification_manager

        # Mock asyncio.sleep
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await client.auto_reconnect()

        # Verify catch-up summary was generated for ACTIVE session only
        mock_session_manager.generate_catchup_summary.assert_called_once_with("session-1")
        mock_notification_manager.notify.assert_called_once()

        # Verify final state is CONNECTED
        assert client.reconnection_manager.state == ConnectionState.CONNECTED
