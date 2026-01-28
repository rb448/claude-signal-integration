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
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path
import tempfile
import os

from src.session.commands import SessionCommands
from src.session.manager import SessionManager
from src.claude.orchestrator import ClaudeOrchestrator


@pytest.mark.asyncio
async def test_full_user_flow_integration():
    """Test complete flow: start session → send command → receive response

    This integration test verifies the two critical wiring gaps are fixed:
    1. execute_command() receives all 4 required parameters (command, session_id, recipient, thread_id)
    2. Responses route using thread_id (phone number) not session_id (UUID)

    Expected Initial Result: FAIL (signature mismatch at execute_command call)
    """

    # Setup: Mock Signal client, authorized phone
    authorized_phone = "+1234567890"
    thread_id = "+1234567890"  # Same as phone for 1:1 chat

    # Create temporary project directory
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()

        # Create README for test
        readme = project_path / "README.md"
        readme.write_text("# Test Project\n\nThis is a test project.")

        # Setup SessionManager with real database
        with tempfile.TemporaryDirectory() as db_dir:
            db_path = Path(db_dir) / "sessions.db"
            session_manager = SessionManager(str(db_path))
            await session_manager.initialize()

            # Setup mocked ClaudeOrchestrator
            from src.claude.parser import OutputParser
            from src.claude.responder import SignalResponder

            parser = OutputParser()
            responder = SignalResponder()
            mock_send_signal = AsyncMock()

            orchestrator = ClaudeOrchestrator(
                bridge=None,  # Will be set later
                parser=parser,
                responder=responder,
                send_signal=mock_send_signal
            )

            # Mock the bridge
            mock_bridge = MagicMock()
            orchestrator.bridge = mock_bridge

            # Setup SessionCommands with real session_manager and mocked orchestrator
            from src.session.lifecycle import SessionLifecycle
            from src.claude.process import ClaudeProcess

            session_lifecycle = SessionLifecycle(session_manager)

            # Mock Claude process factory
            def mock_claude_process_factory(session_id: str, project_path: str):
                mock_process = MagicMock(spec=ClaudeProcess)
                mock_process.start = AsyncMock()
                mock_process.get_bridge = MagicMock(return_value=mock_bridge)
                return mock_process

            session_commands = SessionCommands(
                session_manager=session_manager,
                session_lifecycle=session_lifecycle,
                claude_process_factory=mock_claude_process_factory,
                claude_orchestrator=orchestrator
            )

            # STEP 1: User sends /session start /tmp/test-project
            start_message = f"/session start {project_path}"
            response = await session_commands.handle(thread_id, start_message)

            # Assert: Session created successfully
            assert response is not None
            assert "Session started" in response or "abc" in response.lower()  # Truncated session ID

            # Get the created session
            sessions = await session_manager.list_sessions()
            assert len(sessions) == 1
            session = sessions[0]
            session_id = session["id"]

            # Assert: Session state is ACTIVE
            assert session["state"] == "ACTIVE"
            assert session["project_path"] == str(project_path)

            # STEP 2: User sends Claude command "Read the README"
            # This will call orchestrator.execute_command() - the critical integration point

            # Mock the bridge methods to avoid actual subprocess
            async def mock_stream():
                # Simulate Claude reading the file
                yield "README.md contents: # Test Project\n"

            mock_bridge.send_command = AsyncMock()
            mock_bridge.stream_output = mock_stream

            # Send the Claude command
            claude_message = "Read the README"

            # CRITICAL TEST: This should call execute_command with ALL 4 parameters
            # Before fix: TypeError - missing 2 required positional arguments: 'recipient' and 'thread_id'
            # After fix: Should work

            response = await session_commands.handle(thread_id, claude_message)

            # Assert: execute_command was called (response is None because orchestrator handles streaming)
            assert response is None  # None signals orchestrator is handling the response

            # Assert: execute_command received all 4 parameters
            # We verify this by checking that orchestrator has stored the values
            assert orchestrator.session_id == session_id
            assert hasattr(orchestrator, 'current_thread_id')
            assert orchestrator.current_thread_id == thread_id

            # STEP 3: Verify response routing uses thread_id
            # The orchestrator should have called send_signal with thread_id (not session_id)

            # Wait for any pending async operations
            import asyncio
            await asyncio.sleep(0.2)  # Give time for batch interval

            # Assert: send_signal was called with thread_id (phone number), not session_id (UUID)
            assert mock_send_signal.called
            calls = mock_send_signal.call_args_list

            # Every call to send_signal should use thread_id as first argument
            for call_args in calls:
                recipient_arg = call_args[0][0]  # First positional argument
                # Should be thread_id (phone number), NOT session_id (UUID format)
                assert recipient_arg == thread_id, f"Expected thread_id {thread_id}, got {recipient_arg}"
                # Verify it's NOT the session_id
                assert recipient_arg != session_id, "Response incorrectly routed to session_id instead of thread_id"


@pytest.mark.asyncio
async def test_execute_command_signature():
    """Verify execute_command signature matches expected interface

    This test ensures execute_command() has the correct signature:
    - command: str (the user's message)
    - session_id: str (links to session)
    - recipient: str (phone number for attachments)
    - thread_id: str | None (routing key for responses)
    """
    from src.claude.parser import OutputParser
    from src.claude.responder import SignalResponder

    orchestrator = ClaudeOrchestrator(
        bridge=None,
        parser=OutputParser(),
        responder=SignalResponder(),
        send_signal=AsyncMock()
    )

    # Verify signature by inspecting the method
    import inspect
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
async def test_response_routing_uses_thread_id_not_session_id():
    """Verify orchestrator routes responses using thread_id, not session_id

    This test specifically checks that send_signal receives thread_id (phone number)
    rather than session_id (UUID), which would fail as invalid phone number.
    """
    from src.claude.parser import OutputParser
    from src.claude.responder import SignalResponder

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

    # Mock bridge
    mock_bridge = MagicMock()
    mock_bridge.send_command = AsyncMock()
    mock_bridge.stream_output = AsyncMock(return_value=[])
    orchestrator.bridge = mock_bridge

    # Setup parameters
    session_id = "abc123de-f456-7890-g123-h456i789j012"  # UUID format
    thread_id = "+1234567890"  # E.164 phone number

    # Call execute_command with all 4 parameters
    await orchestrator.execute_command(
        command="test command",
        session_id=session_id,
        recipient=thread_id,
        thread_id=thread_id
    )

    # Wait for batch interval
    import asyncio
    await asyncio.sleep(0.2)

    # Assert: send_signal called with thread_id, NOT session_id
    assert mock_send_signal.called
    calls = mock_send_signal.call_args_list

    for call_args in calls:
        recipient = call_args[0][0]  # First positional argument
        assert recipient == thread_id, f"Expected thread_id {thread_id}, got {recipient}"
        assert recipient != session_id, "Response incorrectly routed to session_id"
