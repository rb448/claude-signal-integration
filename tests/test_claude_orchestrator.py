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
