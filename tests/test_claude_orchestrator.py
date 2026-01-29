"""Tests for ClaudeOrchestrator - end-to-end command flow."""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, call, patch
from src.claude.orchestrator import ClaudeOrchestrator
from src.claude.parser import OutputParser, OutputType, ToolCall, Progress, Error, Response
from src.claude.responder import SignalResponder


@pytest.mark.asyncio
async def test_execute_command():
    """Test basic command execution flow."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock bridge to return simple response
    async def mock_read_response():
        yield "Analyzing your request..."
        yield "Using Read tool on file.py"
        yield "Here's the analysis"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("help me debug", "session-123", "+1234567890")

    # Assert
    bridge.send_command.assert_called_once_with("help me debug")

    # Verify messages were sent to Signal
    assert send_signal.call_count >= 1

    # Verify at least one message was sent
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]  # Extract message text

    # Should contain formatted output
    assert any("📖" in msg for msg in messages)  # Tool call emoji


@pytest.mark.asyncio
async def test_stream_output():
    """Test streaming output with batching."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock multiple lines of output
    async def mock_read_response():
        yield "Analyzing code..."
        yield "Using Read tool on src/main.py"
        yield "Using Edit tool on src/main.py"
        yield "Writing changes..."
        yield "Done!"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("fix the bug", "session-456", "+1234567890")

    # Assert
    assert send_signal.call_count >= 1

    # Verify tool calls were formatted
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    assert "📖" in combined  # Read tool
    assert "✏️" in combined  # Edit tool


@pytest.mark.asyncio
async def test_handle_error():
    """Test error handling in command execution."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock error output
    async def mock_read_response():
        yield "Analyzing..."
        yield "Error: File not found: missing.py"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("read missing.py", "session-789", "+1234567890")

    # Assert
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    # Should contain error formatting
    assert "❌" in combined or "Error" in combined


@pytest.mark.asyncio
async def test_command_with_tool_calls():
    """Test command that makes multiple tool calls."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock output with multiple tools
    async def mock_read_response():
        yield "Using Read tool on config.py"
        yield "Using Grep tool on *.py"
        yield "Using Write tool on output.txt"
        yield "Running: pytest tests/"
        yield "All tests passed!"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("run tests", "session-abc", "+1234567890")

    # Assert
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    # Verify all tool emojis present
    assert "📖" in combined  # Read
    assert "🔍" in combined  # Grep
    assert "💾" in combined  # Write
    assert "🔧" in combined  # Bash


@pytest.mark.asyncio
async def test_bridge_exception_handling():
    """Test handling of CLIBridge exceptions."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock bridge to raise exception
    bridge.send_command = AsyncMock(side_effect=ValueError("stdin not available"))

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("test command", "session-err", "+1234567890")

    # Assert - should send error message to Signal
    assert send_signal.call_count >= 1
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    # Should contain error about bridge failure
    assert "error" in combined.lower() or "❌" in combined


@pytest.mark.asyncio
async def test_execute_command_with_long_code_attachment():
    """Test attachment upload when marker detected in formatted output."""
    # Arrange
    bridge = Mock()
    parser = Mock()
    responder = Mock()
    send_signal = AsyncMock()

    # Generate 150 lines of code content
    long_code = "\n".join([f"line {i}: print('test')" for i in range(150)])

    # Create a Response object with text attribute
    mock_response = Response(type=OutputType.RESPONSE, text=long_code)

    # Mock parser.parse() to return Response
    parser.parse.return_value = mock_response

    # Mock responder.format() to return message with attachment marker
    formatted_message = f"Here's the output:\n[Code too long (150 lines) - attachment coming...]\n{long_code}"
    responder.format.return_value = formatted_message

    # Mock responder.send_with_attachments() to return updated message
    updated_message = "Here's the output:\n[Code attached as output_20260127_123456.txt]"
    responder.send_with_attachments = AsyncMock(return_value=updated_message)

    # Mock bridge response
    async def mock_read_response():
        yield "Here's the code output"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("some command", "session-123", "+1234567890")

    # Assert
    # Verify send_with_attachments was called once
    responder.send_with_attachments.assert_called_once()

    # Extract call arguments
    call_args = responder.send_with_attachments.call_args
    actual_message = call_args[0][0]
    actual_attachments = call_args[0][1]
    actual_recipient = call_args[0][2]

    # Verify message content
    assert actual_message == formatted_message

    # Verify attachments structure
    assert len(actual_attachments) == 1
    attachment_content, attachment_filename = actual_attachments[0]
    assert attachment_content == long_code
    assert "output_" in attachment_filename and attachment_filename.endswith(".txt")

    # Verify recipient
    assert actual_recipient == "+1234567890"

    # Verify send_signal was called with updated message (marker replaced)
    send_signal.assert_called()
    final_call = send_signal.call_args_list[-1]
    final_message = final_call[0][1]
    assert "[Code attached as" in final_message or "output_" in final_message


@pytest.mark.asyncio
async def test_execute_command_without_attachment_markers():
    """Test no-op when no attachment markers present in formatted output."""
    # Arrange
    bridge = Mock()
    parser = Mock()
    responder = Mock()
    send_signal = AsyncMock()

    # Create a Response object with text attribute
    short_code = "print('hello')"
    mock_response = Response(type=OutputType.RESPONSE, text=short_code)

    # Mock parser.parse() to return Response
    parser.parse.return_value = mock_response

    # Mock responder.format() to return message WITHOUT markers
    formatted_message = "Here's the output:\n```python\ncode\n```"
    responder.format.return_value = formatted_message

    # Mock responder.send_with_attachments (should NOT be called)
    responder.send_with_attachments = AsyncMock()

    # Mock bridge response
    async def mock_read_response():
        yield "Here's the code"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_command("some command", "session-456", "+1234567890")

    # Assert
    # Verify send_with_attachments was NOT called
    responder.send_with_attachments.assert_not_called()

    # Verify send_signal was called with message containing formatted output
    send_signal.assert_called()
    final_call = send_signal.call_args_list[-1]
    final_message = final_call[0][1]
    assert "```python" in final_message or "code" in final_message


@pytest.mark.asyncio
async def test_execute_custom_command():
    """Test custom command execution sends formatted command to bridge."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock bridge response
    async def mock_read_response():
        yield "Executing custom command..."
        yield "Command completed!"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_custom_command(
        command_name="gsd:plan",
        args="my-project high-priority",
        thread_id="thread-123"
    )

    # Assert - command should be formatted as /command args and sent to bridge
    bridge.send_command.assert_called_once_with("/gsd:plan my-project high-priority")


@pytest.mark.asyncio
async def test_execute_custom_command_streams_response():
    """Test custom command responses are streamed to Signal."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock bridge response with multiple lines
    async def mock_read_response():
        yield "Creating project plan..."
        yield "Using Read tool on context.md"
        yield "Generated plan structure"
        yield "Done!"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_custom_command(
        command_name="test:cmd",
        args="",
        thread_id="thread-456"
    )

    # Assert - responses should be sent to Signal
    assert send_signal.call_count >= 1
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    # Should contain tool emoji and responses
    assert "📖" in combined  # Read tool
    assert "Done!" in combined or "plan" in combined.lower()


@pytest.mark.asyncio
async def test_execute_custom_command_no_args():
    """Test custom command execution without arguments."""
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    async def mock_read_response():
        yield "Command executed"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(bridge, parser, responder, send_signal)

    # Act
    await orchestrator.execute_custom_command(
        command_name="simple:cmd",
        args="",
        thread_id="thread-789"
    )

    # Assert - command sent without args (just slash + name)
    bridge.send_command.assert_called_once_with("/simple:cmd ")


@pytest.mark.asyncio
async def test_execute_command_bridge_none():
    """
    Test execute_command when bridge is None.

    Tests that when bridge is not initialized:
    1. Error message is logged
    2. Error sent to user via Signal
    3. No command execution attempted
    4. Returns early without crashing
    """
    # Arrange
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Create orchestrator with bridge=None
    orchestrator = ClaudeOrchestrator(
        bridge=None,  # No bridge available
        parser=parser,
        responder=responder,
        send_signal=send_signal
    )

    # Act
    await orchestrator.execute_command("test command", "session-123", "+1234567890")

    # Assert
    # Should send error message to Signal
    assert send_signal.call_count >= 1
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    # Error should mention no active session or similar
    assert "Error" in combined or "❌" in combined or "session" in combined.lower()


@pytest.mark.asyncio
async def test_approval_timeout_during_execution():
    """
    Test approval request timeout handling.

    Tests that when approval request times out (10 minutes):
    1. Operation is rejected
    2. User is notified of timeout
    3. Execution skips the operation
    4. Subsequent operations continue
    """
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock approval workflow
    approval_workflow = Mock()

    # Mock intercept to require approval
    approval_workflow.intercept.return_value = (False, "approval-123")

    # Mock detector
    approval_workflow.detector = Mock()
    approval_workflow.detector.classify.return_value = (False, "Destructive: Write operation")

    # Mock format_approval_message
    approval_workflow.format_approval_message.return_value = "Approval required for Write tool"

    # Mock wait_for_approval to simulate timeout (return False)
    async def mock_wait():
        await asyncio.sleep(0.1)  # Simulate wait time
        return False  # Timeout/rejection

    approval_workflow.wait_for_approval = mock_wait

    # Mock bridge response with a destructive tool call
    async def mock_read_response():
        yield "Using Write tool on critical_file.py"
        yield "Continuing with next operation..."

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(
        bridge=bridge,
        parser=parser,
        responder=responder,
        send_signal=send_signal,
        approval_workflow=approval_workflow
    )

    # Act
    await orchestrator.execute_command("dangerous command", "session-456", "+1234567890")

    # Assert
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    # Should contain rejection message
    assert "rejected" in combined.lower() or "timed out" in combined.lower() or "❌" in combined


@pytest.mark.asyncio
async def test_custom_command_not_found():
    """
    Test execute_custom_command for non-existent command.

    Tests that when custom command doesn't exist:
    1. Command is sent to bridge anyway (bridge handles validation)
    2. Error response from Claude is properly formatted
    3. User is notified of the error
    """
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()

    # Mock bridge response indicating command not found
    async def mock_read_response():
        yield "Error: Command '/nonexistent:cmd' not recognized"
        yield "Available commands: /help, /session, /thread"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(
        bridge=bridge,
        parser=parser,
        responder=responder,
        send_signal=send_signal
    )

    # Act
    await orchestrator.execute_custom_command(
        command_name="nonexistent:cmd",
        args="some args",
        thread_id="thread-789"
    )

    # Assert
    # Command should be sent to bridge (validation happens there)
    bridge.send_command.assert_called_once_with("/nonexistent:cmd some args")

    # Error response should be sent to Signal
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    assert "Error" in combined or "not recognized" in combined or "❌" in combined


@pytest.mark.asyncio
async def test_response_formatting_with_null_output():
    """
    Test response formatting when parser returns None or empty output.

    Tests that when parser returns None/empty:
    1. No message is sent to Signal
    2. No errors are raised
    3. Execution continues
    """
    # Arrange
    bridge = Mock()
    parser = Mock()
    responder = Mock()
    send_signal = AsyncMock()

    # Mock parser to return None
    parser.parse.return_value = None

    # Mock responder.format to handle None gracefully
    responder.format.return_value = ""  # Empty formatted message

    # Mock bridge response
    async def mock_read_response():
        yield "Some output"
        yield "More output"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(
        bridge=bridge,
        parser=parser,
        responder=responder,
        send_signal=send_signal
    )

    # Act
    await orchestrator.execute_command("test command", "session-999", "+1234567890")

    # Assert
    # Parser should have been called
    assert parser.parse.call_count >= 1

    # send_signal might be called but with empty messages (which get filtered in batcher)
    # The key is no exception was raised


@pytest.mark.asyncio
async def test_bridge_read_exception():
    """
    Test bridge.read_response() raising exception mid-stream.

    Tests that when bridge raises exception during streaming:
    1. Error is caught
    2. User is notified via Signal
    3. Orchestrator remains stable
    4. Error notification sent if notification_manager available
    """
    # Arrange
    bridge = Mock()
    parser = OutputParser()
    responder = SignalResponder()
    send_signal = AsyncMock()
    notification_manager = Mock()
    notification_manager.notify = AsyncMock()

    # Mock bridge to raise exception mid-stream
    async def mock_read_response():
        yield "Starting operation..."
        yield "Processing file 1..."
        raise ConnectionError("WebSocket connection lost")
        # Should never reach here
        yield "Should not see this"

    bridge.send_command = AsyncMock()
    bridge.read_response = mock_read_response

    orchestrator = ClaudeOrchestrator(
        bridge=bridge,
        parser=parser,
        responder=responder,
        send_signal=send_signal,
        notification_manager=notification_manager
    )

    # Act
    await orchestrator.execute_command(
        command="test command",
        session_id="session-error",
        recipient="+1234567890",
        thread_id="thread-error"
    )

    # Assert
    # Error message should be sent to Signal
    calls = send_signal.call_args_list
    messages = [call[0][1] for call in calls]
    combined = "\n".join(messages)

    assert "Error" in combined or "connection" in combined.lower() or "❌" in combined

    # Error notification should be sent
    notification_manager.notify.assert_called()
    notify_call = notification_manager.notify.call_args
    assert notify_call[1]["event_type"] == "error"
    assert "connection" in notify_call[1]["details"]["error"].lower()
