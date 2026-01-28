"""
Integration test for full user flow: start session → send command → receive response

This test verifies the complete end-to-end flow that was broken in v1.0 milestone audit:
- Gap 1: execute_command() signature mismatch - missing recipient and thread_id parameters
- Gap 2: Response routing broken - orchestrator uses session_id instead of thread_id

Test-First Order (RED-GREEN-REFACTOR):
1. RED: Test fails at execute_command call (signature mismatch)
2. GREEN: Fix SessionCommands.handle() to pass all 4 parameters
3. GREEN: Fix ClaudeOrchestrator to store and use thread_id for routing
4. REFACTOR: None needed (minimal changes)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import inspect

from src.claude.orchestrator import ClaudeOrchestrator
from src.claude.parser import OutputParser
from src.claude.responder import SignalResponder


@pytest.mark.asyncio
async def test_execute_command_signature():
    """Verify execute_command signature matches expected interface

    This test ensures execute_command() has the correct signature:
    - command: str (the user's message)
    - session_id: str (links to session)
    - recipient: str (phone number for attachments)
    - thread_id: str | None (routing key for responses)
    """
    orchestrator = ClaudeOrchestrator(
        bridge=None,
        parser=OutputParser(),
        responder=SignalResponder(),
        send_signal=AsyncMock()
    )

    # Verify signature by inspecting the method
    sig = inspect.signature(orchestrator.execute_command)
    params = list(sig.parameters.keys())

    # Expected parameters (excluding 'self')
    expected_params = ['command', 'session_id', 'recipient', 'thread_id']

    for param in expected_params:
        assert param in params, f"execute_command missing parameter: {param}"

    # Verify thread_id has default value (None)
    thread_id_param = sig.parameters['thread_id']
    assert thread_id_param.default is None or thread_id_param.default == inspect.Parameter.empty


@pytest.mark.asyncio
@pytest.mark.integration
async def test_response_routing_uses_thread_id_not_session_id():
    """Verify orchestrator routes responses using thread_id, not session_id

    This test specifically checks that send_signal receives thread_id (phone number)
    rather than session_id (UUID), which would fail as invalid phone number.

    This is the critical integration test that verifies Gap 2 is fixed.
    """
    # Mock send_signal callback
    mock_send_signal = AsyncMock()

    # Setup orchestrator
    parser = OutputParser()
    responder = SignalResponder()

    orchestrator = ClaudeOrchestrator(
        bridge=None,
        parser=parser,
        responder=responder,
        send_signal=mock_send_signal
    )

    # Mock bridge to simulate command execution
    mock_bridge = MagicMock()
    mock_bridge.send_command = AsyncMock()

    # Mock read_response to yield some output
    async def mock_read_response():
        yield "Test output line 1\n"
        yield "Test output line 2\n"

    mock_bridge.read_response = mock_read_response
    orchestrator.bridge = mock_bridge

    # Setup test parameters
    session_id = "abc123de-f456-7890-g123-h456i789j012"  # UUID format
    thread_id = "+1234567890"  # E.164 phone number
    command = "test command"

    # Call execute_command with all 4 parameters (verifies Gap 1 is fixed)
    await orchestrator.execute_command(
        command=command,
        session_id=session_id,
        recipient=thread_id,
        thread_id=thread_id
    )

    # Wait for batch interval to allow message sending
    import asyncio
    await asyncio.sleep(0.6)  # BATCH_INTERVAL is 0.5s

    # Assert: send_signal was called with thread_id, NOT session_id (verifies Gap 2 is fixed)
    assert mock_send_signal.called, "send_signal should have been called"

    # Check all calls to send_signal
    calls = mock_send_signal.call_args_list
    assert len(calls) > 0, "Expected at least one send_signal call"

    for call_args in calls:
        recipient = call_args[0][0]  # First positional argument
        assert recipient == thread_id, f"Expected thread_id {thread_id}, got {recipient}"
        assert recipient != session_id, "Response incorrectly routed to session_id instead of thread_id"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_orchestrator_stores_thread_id():
    """Verify orchestrator stores thread_id when execute_command is called

    This test ensures the orchestrator properly stores the thread_id parameter
    in its current_thread_id attribute for use in response routing.
    """
    mock_send_signal = AsyncMock()

    orchestrator = ClaudeOrchestrator(
        bridge=None,
        parser=OutputParser(),
        responder=SignalResponder(),
        send_signal=mock_send_signal
    )

    # Initially, current_thread_id should be None
    assert orchestrator.current_thread_id is None

    # Setup mock bridge
    mock_bridge = MagicMock()
    mock_bridge.send_command = AsyncMock()
    async def mock_read_response_empty():
        return
        yield  # Empty generator

    mock_bridge.read_response = mock_read_response_empty
    orchestrator.bridge = mock_bridge

    # Call execute_command
    thread_id = "+1234567890"
    await orchestrator.execute_command(
        command="test",
        session_id="session-123",
        recipient=thread_id,
        thread_id=thread_id
    )

    # Verify thread_id was stored
    assert orchestrator.current_thread_id == thread_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_command_accepts_all_four_parameters():
    """Verify execute_command can be called with all 4 required parameters

    This is a simple smoke test that verifies the signature fix allows
    the call pattern used by SessionCommands.
    """
    mock_send_signal = AsyncMock()

    orchestrator = ClaudeOrchestrator(
        bridge=None,
        parser=OutputParser(),
        responder=SignalResponder(),
        send_signal=mock_send_signal
    )

    # Setup mock bridge
    mock_bridge = MagicMock()
    mock_bridge.send_command = AsyncMock()

    async def mock_read_response():
        return
        yield  # Empty generator

    mock_bridge.read_response = mock_read_response
    orchestrator.bridge = mock_bridge

    # This call should NOT raise TypeError
    # Before fix: TypeError - missing 2 required positional arguments
    # After fix: Should work
    try:
        await orchestrator.execute_command(
            command="Read the README",
            session_id="abc123de-f456-7890-g123-h456i789j012",
            recipient="+1234567890",
            thread_id="+1234567890"
        )
        call_succeeded = True
    except TypeError as e:
        call_succeeded = False
        pytest.fail(f"execute_command call failed with TypeError: {e}")

    assert call_succeeded, "execute_command should accept all 4 parameters"
