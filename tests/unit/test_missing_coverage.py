"""
Retroactive unit tests to close coverage gaps identified in Phase 10-01 audit.

This module targets modules below 80% coverage:
- SignalClient (55% → 85%)
- ClaudeProcess (70% → 85%)
- Daemon Service (71% → 85%)
- ClaudeOrchestrator (73% → 85%)

Focus areas:
- Error paths not tested (exception handling, validation failures)
- Edge cases (timeout, null values, boundary conditions)
- Configuration branches (feature flags, environment variations)
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from aiohttp import ClientError, ClientResponseError, ClientConnectorError
from aiohttp.web import Application

from src.signal.client import SignalClient
from src.signal.reconnection import ConnectionState
from src.claude.process import ClaudeProcess
from src.daemon.service import ServiceDaemon
from src.claude.orchestrator import ClaudeOrchestrator
from src.claude.parser import StreamingParser
from src.claude.responder import SignalResponder


# ============================================================================
# SignalClient Coverage Tests (55% → 85%)
# ============================================================================

class TestSignalClientErrorPaths:
    """Tests for SignalClient error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_connect_http_non_200_status(self):
        """Test connection failure when health endpoint returns non-200 status."""
        client = SignalClient(
            api_url="http://localhost:8080",
            phone_number="+15551234567"
        )

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Mock response with 503 status
            mock_response = AsyncMock()
            mock_response.status = 503
            mock_response.__aenter__.return_value = mock_response
            mock_response.__aexit__.return_value = None
            mock_session.get.return_value = mock_response

            with pytest.raises(ConnectionError, match="Signal API returned HTTP 503"):
                await client.connect()

            # Verify session was closed after error
            mock_session.close.assert_called_once()
            assert client._connected is False
            assert client.reconnection_manager.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_connect_network_error(self):
        """Test connection failure due to network error."""
        client = SignalClient(
            api_url="http://localhost:8080",
            phone_number="+15551234567"
        )

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Simulate network error
            mock_session.get.side_effect = ClientConnectorError(
                connection_key=None,
                os_error=OSError("Network unreachable")
            )

            with pytest.raises(ConnectionError, match="Failed to connect to Signal API"):
                await client.connect()

            assert client._connected is False
            assert client.reconnection_manager.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_connect_timeout(self):
        """Test connection timeout during health check."""
        client = SignalClient(
            api_url="http://localhost:8080",
            phone_number="+15551234567"
        )

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session

            # Simulate timeout
            mock_session.get.side_effect = asyncio.TimeoutError()

            with pytest.raises(ConnectionError, match="Failed to connect to Signal API"):
                await client.connect()

            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_when_already_disconnected(self):
        """Test disconnect when no active session."""
        client = SignalClient(
            api_url="http://localhost:8080",
            phone_number="+15551234567"
        )

        # Should not raise error
        await client.disconnect()
        assert client._session is None
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_auto_reconnect_sync_session_state(self):
        """Test auto_reconnect syncs session state when session_id is set."""
        client = SignalClient(
            api_url="http://localhost:8080",
            phone_number="+15551234567"
        )
        client.session_id = "test-session-123"

        # Mock dependencies
        client.reconnection_manager.state = ConnectionState.DISCONNECTED

        with patch.object(client, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(client, '_sync_session_state', new_callable=AsyncMock) as mock_sync:
                with patch.object(client, '_drain_buffer', new_callable=AsyncMock) as mock_drain:
                    # Make connect succeed
                    async def connect_side_effect():
                        client.reconnection_manager.state = ConnectionState.CONNECTED
                    mock_connect.side_effect = connect_side_effect

                    await client.auto_reconnect()

                    # Verify sync was called
                    mock_sync.assert_called_once()
                    mock_drain.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_reconnect_generates_catchup_summaries(self):
        """Test auto_reconnect generates catch-up summaries for active sessions."""
        client = SignalClient(
            api_url="http://localhost:8080",
            phone_number="+15551234567"
        )

        # Mock session and notification managers
        mock_session_manager = AsyncMock()
        mock_notification_manager = AsyncMock()
        client.session_manager = mock_session_manager
        client.notification_manager = mock_notification_manager

        # Mock active session
        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.thread_id = "thread-456"
        mock_session.status.value = "ACTIVE"
        mock_session_manager.list.return_value = [mock_session]

        # Mock meaningful summary
        mock_session_manager.generate_catchup_summary.return_value = "While disconnected: 2 commands executed"

        client.reconnection_manager.state = ConnectionState.DISCONNECTED

        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, '_sync_session_state', new_callable=AsyncMock):
                with patch.object(client, '_drain_buffer', new_callable=AsyncMock):
                    async def connect_side_effect():
                        client.reconnection_manager.state = ConnectionState.CONNECTED
                    client.connect.side_effect = connect_side_effect

                    await client.auto_reconnect()

                    # Verify notification sent
                    mock_notification_manager.notify.assert_called_once()
                    call_kwargs = mock_notification_manager.notify.call_args[1]
                    assert call_kwargs['event_type'] == 'reconnection'
                    assert 'While disconnected' in call_kwargs['details']['summary']

    @pytest.mark.asyncio
    async def test_auto_reconnect_skips_empty_catchup_summaries(self):
        """Test auto_reconnect skips notification when summary has no activity."""
        client = SignalClient(
            api_url="http://localhost:8080",
            phone_number="+15551234567"
        )

        mock_session_manager = AsyncMock()
        mock_notification_manager = AsyncMock()
        client.session_manager = mock_session_manager
        client.notification_manager = mock_notification_manager

        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.status.value = "ACTIVE"
        mock_session_manager.list.return_value = [mock_session]

        # Mock empty summary
        mock_session_manager.generate_catchup_summary.return_value = "No activity"

        client.reconnection_manager.state = ConnectionState.DISCONNECTED

        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, '_sync_session_state', new_callable=AsyncMock):
                with patch.object(client, '_drain_buffer', new_callable=AsyncMock):
                    async def connect_side_effect():
                        client.reconnection_manager.state = ConnectionState.CONNECTED
                    client.connect.side_effect = connect_side_effect

                    await client.auto_reconnect()

                    # Verify notification NOT sent
                    mock_notification_manager.notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_reconnect_handles_connection_failure(self):
        """Test auto_reconnect handles connection failure and retries."""
        client = SignalClient(
            api_url="http://localhost:8080",
            phone_number="+15551234567"
        )

        client.reconnection_manager.state = ConnectionState.DISCONNECTED

        with patch.object(client, 'connect', new_callable=AsyncMock) as mock_connect:
            # First attempt fails, second succeeds
            call_count = 0
            async def connect_side_effect():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ConnectionError("Network error")
                else:
                    client.reconnection_manager.state = ConnectionState.CONNECTED

            mock_connect.side_effect = connect_side_effect

            with patch.object(client, '_drain_buffer', new_callable=AsyncMock):
                await client.auto_reconnect()

                # Should have tried twice
                assert mock_connect.call_count == 2


# ============================================================================
# ClaudeProcess Coverage Tests (70% → 85%)
# ============================================================================

class TestClaudeProcessErrorPaths:
    """Tests for ClaudeProcess error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_start_subprocess_failure(self):
        """Test start() handles subprocess creation failure."""
        process = ClaudeProcess(
            session_id="test-session",
            project_path="/tmp/test-project"
        )

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_exec.side_effect = FileNotFoundError("claude command not found")

            with pytest.raises(FileNotFoundError):
                await process.start()

    @pytest.mark.asyncio
    async def test_start_permission_denied(self):
        """Test start() handles permission denied error."""
        process = ClaudeProcess(
            session_id="test-session",
            project_path="/tmp/test-project"
        )

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_exec.side_effect = PermissionError("Permission denied")

            with pytest.raises(PermissionError):
                await process.start()

    @pytest.mark.asyncio
    async def test_stop_when_no_process(self):
        """Test stop() when no process exists."""
        process = ClaudeProcess(
            session_id="test-session",
            project_path="/tmp/test-project"
        )

        # Should not raise error
        await process.stop()

    @pytest.mark.asyncio
    async def test_stop_when_already_stopped(self):
        """Test stop() when process already stopped."""
        process = ClaudeProcess(
            session_id="test-session",
            project_path="/tmp/test-project"
        )

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.pid = 12345
            mock_process.returncode = 0  # Already stopped
            mock_exec.return_value = mock_process

            await process.start()

            # Should not attempt termination
            await process.stop()
            mock_process.terminate.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_timeout_forces_kill(self):
        """Test stop() forces kill after timeout."""
        process = ClaudeProcess(
            session_id="test-session",
            project_path="/tmp/test-project"
        )

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = AsyncMock()
            mock_process.pid = 12345
            mock_process.returncode = None  # Still running

            # Simulate timeout on wait()
            mock_process.wait.side_effect = asyncio.TimeoutError()
            mock_exec.return_value = mock_process

            await process.start()
            await process.stop(timeout=0.1)

            # Should have called terminate, then kill
            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_bridge_when_not_started(self):
        """Test get_bridge() raises error when process not started."""
        process = ClaudeProcess(
            session_id="test-session",
            project_path="/tmp/test-project"
        )

        with pytest.raises(RuntimeError, match="Bridge not available"):
            process.get_bridge()

    @pytest.mark.asyncio
    async def test_is_running_when_no_process(self):
        """Test is_running when no process exists."""
        process = ClaudeProcess(
            session_id="test-session",
            project_path="/tmp/test-project"
        )

        assert process.is_running is False


# ============================================================================
# Daemon Service Coverage Tests (71% → 85%)
# ============================================================================

class TestDaemonServiceErrorPaths:
    """Tests for Daemon Service error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_health_check_handler(self):
        """Test health check endpoint returns ok."""
        daemon = ServiceDaemon(
            signal_api_url="http://localhost:8080",
            authorized_phone="+15551234567"
        )

        response = await daemon._health_check_handler(None)
        assert response.status == 200
        assert response.body == b'{"status": "ok"}'

    @pytest.mark.asyncio
    async def test_start_health_server_port_conflict(self):
        """Test health server handles port already in use."""
        daemon = ServiceDaemon(
            signal_api_url="http://localhost:8080",
            authorized_phone="+15551234567"
        )

        with patch('aiohttp.web.TCPSite') as mock_site_class:
            mock_site = AsyncMock()
            mock_site.start.side_effect = OSError("Address already in use")
            mock_site_class.return_value = mock_site

            with pytest.raises(OSError, match="Address already in use"):
                await daemon._start_health_server()

    @pytest.mark.asyncio
    async def test_stop_health_server_when_not_started(self):
        """Test stopping health server when it was never started."""
        daemon = ServiceDaemon(
            signal_api_url="http://localhost:8080",
            authorized_phone="+15551234567"
        )

        # Should not raise error
        await daemon._stop_health_server()

    @pytest.mark.asyncio
    async def test_process_message_unauthorized_sender(self):
        """Test message processing rejects unauthorized sender."""
        daemon = ServiceDaemon(
            signal_api_url="http://localhost:8080",
            authorized_phone="+15551234567"
        )

        # Mock phone verifier to reject
        daemon.phone_verifier.verify = Mock(return_value=False)

        message = {
            "envelope": {
                "sourceNumber": "+15559999999",
                "dataMessage": {"message": "/session list"}
            }
        }

        # Should return early without processing
        await daemon._process_message(message)

        # Verify verify was called
        daemon.phone_verifier.verify.assert_called_once_with("+15559999999")

    @pytest.mark.asyncio
    async def test_process_message_handles_send_error(self):
        """Test message processing handles send failure gracefully."""
        daemon = ServiceDaemon(
            signal_api_url="http://localhost:8080",
            authorized_phone="+15551234567"
        )

        # Mock phone verifier to accept
        daemon.phone_verifier.verify = Mock(return_value=True)

        # Mock session commands to return response
        daemon.session_commands = AsyncMock()
        daemon.session_commands.handle.return_value = "Response text"

        # Mock signal client to fail
        daemon.signal_client = AsyncMock()
        daemon.signal_client.send_message.side_effect = Exception("Network error")

        message = {
            "envelope": {
                "sourceNumber": "+15551234567",
                "dataMessage": {"message": "/session list"}
            }
        }

        # Should not raise exception
        await daemon._process_message(message)

        # Verify send was attempted
        daemon.signal_client.send_message.assert_called_once()


# ============================================================================
# ClaudeOrchestrator Coverage Tests (73% → 85%)
# ============================================================================

class TestClaudeOrchestratorErrorPaths:
    """Tests for ClaudeOrchestrator error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_execute_command_no_bridge(self):
        """Test execute_command when bridge is None."""
        parser = StreamingParser()
        responder = SignalResponder(
            signal_client=AsyncMock(),
            attachment_handler=Mock()
        )
        orchestrator = ClaudeOrchestrator(
            bridge=None,  # No bridge
            parser=parser,
            responder=responder,
            recipient="+15551234567"
        )

        mock_send = AsyncMock()
        orchestrator._send_message = mock_send

        await orchestrator.execute_command("test command")

        # Should send error message
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0][0]
        assert "No active Claude CLI session" in call_args

    @pytest.mark.asyncio
    async def test_execute_command_approval_rejected(self):
        """Test execute_command when approval is rejected."""
        mock_bridge = AsyncMock()
        parser = StreamingParser()
        responder = SignalResponder(
            signal_client=AsyncMock(),
            attachment_handler=Mock()
        )

        # Mock approval workflow
        mock_approval = AsyncMock()
        mock_approval.intercept.return_value = (False, "req-123")
        mock_approval.wait_for_approval.return_value = False  # Rejected
        mock_approval.detector.classify.return_value = ("DESTRUCTIVE", "Modifies files")
        mock_approval.format_approval_message.return_value = "Approval needed"

        orchestrator = ClaudeOrchestrator(
            bridge=mock_bridge,
            parser=parser,
            responder=responder,
            recipient="+15551234567",
            approval_workflow=mock_approval
        )

        # Mock bridge to return tool call that needs approval
        async def mock_read_response():
            yield '{"type": "tool_call", "tool": "Edit", "args": {"file": "test.py"}}'

        mock_bridge.read_response.return_value = mock_read_response()

        mock_send = AsyncMock()
        orchestrator._send_message = mock_send

        await orchestrator.execute_command("test command")

        # Should have sent rejection message
        calls = [str(call) for call in mock_send.call_args_list]
        assert any("rejected or timed out" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_execute_command_approval_timeout(self):
        """Test execute_command when approval times out."""
        mock_bridge = AsyncMock()
        parser = StreamingParser()
        responder = SignalResponder(
            signal_client=AsyncMock(),
            attachment_handler=Mock()
        )

        # Mock approval workflow with timeout
        mock_approval = AsyncMock()
        mock_approval.intercept.return_value = (False, "req-123")
        mock_approval.wait_for_approval.return_value = False  # Timeout
        mock_approval.detector.classify.return_value = ("DESTRUCTIVE", "Modifies files")
        mock_approval.format_approval_message.return_value = "Approval needed"

        orchestrator = ClaudeOrchestrator(
            bridge=mock_bridge,
            parser=parser,
            responder=responder,
            recipient="+15551234567",
            approval_workflow=mock_approval
        )

        async def mock_read_response():
            yield '{"type": "tool_call", "tool": "Write", "args": {"file": "new.py"}}'

        mock_bridge.read_response.return_value = mock_read_response()

        mock_send = AsyncMock()
        orchestrator._send_message = mock_send

        await orchestrator.execute_command("test command")

        # Should have sent timeout message
        assert mock_send.call_count >= 2

    @pytest.mark.asyncio
    async def test_execute_command_bridge_communication_failure(self):
        """Test execute_command handles bridge communication failure."""
        mock_bridge = AsyncMock()
        parser = StreamingParser()
        responder = SignalResponder(
            signal_client=AsyncMock(),
            attachment_handler=Mock()
        )

        orchestrator = ClaudeOrchestrator(
            bridge=mock_bridge,
            parser=parser,
            responder=responder,
            recipient="+15551234567"
        )

        # Simulate bridge failure
        mock_bridge.read_response.side_effect = Exception("Pipe broken")

        mock_send = AsyncMock()
        orchestrator._send_message = mock_send

        # Should raise exception
        with pytest.raises(Exception, match="Pipe broken"):
            await orchestrator.execute_command("test command")

    @pytest.mark.asyncio
    async def test_flush_batch_empty_batch(self):
        """Test _flush_batch with empty batch."""
        mock_bridge = AsyncMock()
        parser = StreamingParser()
        responder = SignalResponder(
            signal_client=AsyncMock(),
            attachment_handler=Mock()
        )

        orchestrator = ClaudeOrchestrator(
            bridge=mock_bridge,
            parser=parser,
            responder=responder,
            recipient="+15551234567"
        )

        from src.claude.responder import MessageBatcher
        batcher = MessageBatcher()

        mock_send = AsyncMock()
        orchestrator._send_message = mock_send

        # Should not send anything for empty batch
        await orchestrator._flush_batch(batcher)
        mock_send.assert_not_called()
